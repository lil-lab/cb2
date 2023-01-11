import dataclasses
import json
import logging
from collections import deque
from datetime import datetime, timedelta
from typing import List

import server.actor as actor
from server.assets import AssetId
from server.card import Card, CardSelectAction
from server.messages import (
    live_feedback,
    message_from_server,
    message_to_server,
    objective,
    state_sync,
)
from server.messages.action import Action
from server.messages.map_update import MapUpdate
from server.messages.prop import PropUpdate
from server.messages.replay_messages import (
    Command,
    ReplayInfo,
    ReplayRequestType,
    ReplayResponse,
    ReplayResponseType,
)
from server.messages.rooms import Role
from server.messages.turn_state import TurnState
from server.schemas.event import Event, EventType
from server.schemas.util import InitialState
from server.util import CountDownTimer, IdAssigner

LEADER_MOVES_PER_TURN = 5
FOLLOWER_MOVES_PER_TURN = 10

LEADER_SECONDS_PER_TURN = 50
FOLLOWER_SECONDS_PER_TURN = 15

FOLLOWER_TURN_END_DELAY_SECONDS = 1

logger = logging.getLogger(__name__)


# The Cerealbar2 Replay State Machine. This is the state machine that is used to
# drive the replay mechanism. Game events are loaded from the database and
# played back to the client.
#
# This class contains methods to consume and produce messages from/for the
# state machine. It consumes play/pause/rewind commands. It also contains a
# state machine update loop.  Produce messages and send them to the state
# machine with drain_messages().  Consume messages from the state machine with
# fill_messages().  You must call drain_messages() before each update() call and
# fill_messages() after each update() call.  It is recommended to use
# StateMachineDriver to run this class -- see server/state_machine_driver.py for
# details.
#
# In the process of renaming objective -> instruction. You may see the two terms
# used interchangeably here.
class ReplayState(object):
    def __init__(
        self,
        room_id,
        game_record,
    ):
        self._start_time = datetime.utcnow()
        self._room_id = room_id
        self._game_record = game_record

        # Which iteration the current replay is on.
        self._done = False
        self._initialized = False
        self._events = []
        self._event_index = 0
        self._starting_index = 0
        self._paused = True
        self._event_timer = CountDownTimer()

        self._player_ids = []

        self._id_assigner = IdAssigner()

        self._props = []
        self._instructions = []

        self._message_queue = {}
        self._command_queue = deque()

        self._last_replay_info = datetime.min

        self._num_turns = 0

        self._speed = 1.0

        initial_state_event = (
            Event.select()
            .where(
                Event.game_id == self._game_record.id,
                Event.type == EventType.INITIAL_STATE,
            )
            .get()
        )
        initial_state = InitialState.from_json(initial_state_event.data)
        self._leader_id = initial_state.leader_id

    def has_pending_messages(self):
        # Make sure all lists in self._message_queue are empty.
        return any([len(l) > 0 for l in self._message_queue.values()])

    def MessageFromEvent(
        self, player_id, event: Event, instructions, noduration: bool = False
    ):
        """Converts a database Event to a MessageFromServer to send to the replay client.

        When rewinding, events need to be processed immediately. This is
        accomplished by setting noduration to True. This will cause any
        action objects to have their duration set to 0.
        """
        if event.type == EventType.MAP_UPDATE:
            map_update = MapUpdate.from_json(event.data)
            return message_from_server.MapUpdateFromServer(map_update)
        elif event.type == EventType.INITIAL_STATE:
            initial_state = InitialState.from_json(event.data)
            leader_state = state_sync.Actor(
                initial_state.leader_id,
                AssetId.PLAYER,
                initial_state.leader_position,
                initial_state.leader_rotation_degrees,
                Role.LEADER,
            )
            follower_state = state_sync.Actor(
                initial_state.follower_id,
                AssetId.FOLLOWER_BOT,
                initial_state.follower_position,
                initial_state.follower_rotation_degrees,
                Role.FOLLOWER,
            )
            actor_states = [leader_state, follower_state]
            return message_from_server.StateSyncFromServer(
                state_sync.StateSync(2, actor_states, player_id, Role.LEADER)
            )
        elif event.type == EventType.TURN_STATE:
            turn_state = TurnState.from_json(event.data)
            # Rewrite the turn end. Calculate the time remaining for the turn by
            # subtracting turn_end from event.server_time. Then, add that to the
            # current time. This is so that the "Time left in turn" window
            # renders correctly.
            time_remaining = turn_state.turn_end - event.server_time
            turn_state = dataclasses.replace(
                turn_state, turn_end=datetime.utcnow() + time_remaining
            )
            return message_from_server.GameStateFromServer(turn_state)
        elif event.type == EventType.START_OF_TURN:
            turn_state = TurnState.from_json(event.data)
            return message_from_server.GameStateFromServer(turn_state)
        elif event.type == EventType.PROP_UPDATE:
            prop_update = PropUpdate.from_json(event.data)
            return message_from_server.PropUpdateFromServer(prop_update)
        elif event.type == EventType.CARD_SPAWN:
            card = Card.from_json(event.data)
            prop = card.prop()
            return message_from_server.PropSpawnFromServer(prop)
        elif event.type == EventType.CARD_SELECT:
            try:
                card = Card.from_json(event.data)
            except AttributeError:
                pass

                logger.info(f"Card select event ID: {event.id.hex}")
                import sys

                sys.exit()
            action = CardSelectAction(
                card.id,
                card.selected,
                card.border_color,
            )
            return message_from_server.ActionsFromServer([action])
        elif event.type == EventType.CARD_SET:
            card_set_data = json.loads(event.data)
            cards = [Card.from_dict(card_obj) for card_obj in card_set_data["cards"]]
            props = [card.prop() for card in cards]
            return message_from_server.PropDespawnFromServer(props)
        elif event.type in [
            EventType.INSTRUCTION_SENT,
            EventType.INSTRUCTION_ACTIVATED,
            EventType.INSTRUCTION_CANCELLED,
            EventType.INSTRUCTION_DONE,
        ]:
            return message_from_server.ObjectivesFromServer(instructions)
        elif event.type == EventType.ACTION:
            action_obj = Action.from_json(event.data)
            action_obj = dataclasses.replace(
                action_obj,
                expiration=datetime.utcnow() + timedelta(seconds=10),
                duration_s=(action_obj.duration_s / self._speed),
            )
            if noduration:
                action_obj = dataclasses.replace(
                    action_obj, duration_s=0, expiration=datetime.min
                )
            return message_from_server.ActionsFromServer([action_obj])
        elif event.type == EventType.LIVE_FEEDBACK:
            feedback = live_feedback.LiveFeedback.from_json(event.data)
            return message_from_server.LiveFeedbackFromServer(feedback)
        else:
            raise Exception("Unknown event type: {}".format(event.type))

    def end_game(self):
        logger.debug("Game ending.")
        self._done = True

    def mark_player_disconnected(self, id):
        return None

    def map(self):
        return None

    def cards(self):
        return None

    def done(self):
        return self._done

    def player_ids(self):
        return self._player_ids

    def player_role(self, id):
        return Role.LEADER

    def start(self):
        self._start_time = datetime.utcnow()

    def _update_instructions(self, instructions, event):
        if event.type == EventType.INSTRUCTION_SENT:
            instruction = objective.ObjectiveMessage.from_json(event.data)
            instructions.append(instruction)
        elif event.type == EventType.INSTRUCTION_ACTIVATED:
            i_uuid = event.short_code
            for i, instruction in enumerate(instructions):
                if instruction.uuid == i_uuid:
                    instructions[i].activated = True
                    break
        elif event.type == EventType.INSTRUCTION_CANCELLED:
            i_uuid = event.short_code
            for i, instruction in enumerate(instructions):
                if instruction.uuid == i_uuid:
                    instructions[i].cancelled = True
                    instructions[i].activated = False
                    break
        elif event.type == EventType.INSTRUCTION_DONE:
            i_uuid = event.short_code
            for i, instruction in enumerate(instructions):
                if instruction.uuid == i_uuid:
                    instructions[i].completed = True
                    instructions[i].activated = False
                    break

    def advance_event(self):
        # Send the current event.
        if self._event_index >= len(self._events):
            return
        self._update_instructions(self._instructions, self._events[self._event_index])
        for actor_id in self._message_queue:
            message = self.MessageFromEvent(
                actor_id, self._events[self._event_index], self._instructions
            )
            self._message_queue[actor_id].append(message)
        # Advance the event index.
        self._event_index += 1
        # If we haven't reached the end of the events, set the timer for the next event.
        if self._event_index < len(self._events):
            self.time_to_next_event()
            self._event_timer = CountDownTimer(
                self.time_to_next_event().total_seconds()
            )
            if not self._paused:
                self._event_timer.start()

    def recalculate_timer(self):
        """Updates the remaining time on the timer in response to a recent change in self._speed."""
        if self._event_timer is not None:
            time_remaining = self._event_timer.time_remaining()
            self._event_timer = CountDownTimer(
                (time_remaining / self._speed).total_seconds()
            )
            if not self._paused:
                self._event_timer.start()

    def time_to_next_event(self):
        """Calculates the amount of time until the next event. Uses self._speed to scale the time. Returns a timedelta."""
        if self._event_index == 0:
            return timedelta(second=0)
        if self._event_index >= len(self._events):
            # Maximum time.
            return timedelta(days=365)
        time_difference = (
            self._events[self._event_index].server_time
            - self._events[self._event_index - 1].server_time
        )
        return time_difference / float(self._speed)

    def rewind_event(self):
        """Replays all events up to the previous event, integrating state on the server and then sends state to the client."""
        if (self._event_index <= self._starting_index) or (self._event_index <= 0):
            return
        start_time = datetime.utcnow()
        self._event_index -= 1
        self._instructions = []
        # Map update is preserved across rewind. Actor, instruction and prop state are not. Iterate through all messages, integrating actor and prop positions across actions.
        # Then, send a prop update and state sync update.
        # Quickly resend all events leading up to the previous event.
        instructions = []
        actors = []
        props = []
        for i in range(0, self._event_index):
            self._update_instructions(instructions, self._events[i])
            if self._events[i].type == EventType.PROP_UPDATE:
                props = PropUpdate.from_json(self._events[i].data).props
            elif self._events[i].type == EventType.INITIAL_STATE:
                initial_state_obj = InitialState.from_json(self._events[i].data)
                leader = actor.Actor(
                    initial_state_obj.leader_id,
                    AssetId.PLAYER,
                    Role.LEADER,
                    initial_state_obj.leader_position,
                    False,
                    initial_state_obj.leader_rotation_degrees,
                )
                follower = actor.Actor(
                    initial_state_obj.follower_id,
                    AssetId.FOLLOWER_BOT,
                    Role.FOLLOWER,
                    initial_state_obj.follower_position,
                    False,
                    initial_state_obj.follower_rotation_degrees,
                )
                actors = [leader, follower]
            elif self._events[i].type == EventType.ACTION:
                action = Action.from_json(self._events[i].data)
                for agent in actors:
                    if agent.actor_id() == action.id:
                        agent.add_action(action)
                        agent.step()
                        break
            elif self._events[i].type == EventType.TURN_STATE:
                TurnState.from_json(self._events[i].data)
            elif self._events[i].type == EventType.CARD_SELECT:
                card = Card.from_json(self._events[i].data)
                for prop in props:
                    if prop.id == card.id:
                        prop.card_init.selected = card.selected
                        prop.prop_info.border_color = card.border_color
                        break
            elif self._events[i].type == EventType.CARD_SPAWN:
                card = Card.from_json(self._events[i].data)
                props.append(card.prop())
            elif self._events[i].type == EventType.CARD_SET:
                data = json.loads(self._events[i].data)
                cards_ids = set([int(card_dict["id"]) for card_dict in data["cards"]])
                props = [prop for prop in props if prop.id not in cards_ids]
        self._instructions = instructions
        # Now send messages updating the accumulated state to the client.
        # We send a state sync, an objectives message, and a prop update.
        for actor_id in self._message_queue:
            # Actor state.
            role = Role.LEADER if actor_id == self._leader_id else Role.FOLLOWER
            actor_state = state_sync.StateSync(
                2, [actor.state() for actor in actors], actor_id, role
            )
            self._message_queue[actor_id].append(
                message_from_server.StateSyncFromServer(actor_state)
            )

            # Objectives.
            self._message_queue[actor_id].append(
                message_from_server.ObjectivesFromServer(self._instructions)
            )

            # Prop state.
            self._message_queue[actor_id].append(
                message_from_server.PropUpdateFromServer(PropUpdate(props))
            )

        # Log how long this took.
        end_time = datetime.utcnow()
        logging.info("Rewind took {}".format(end_time - start_time))

        # Pause the game on rewind.
        self._paused = True
        self._event_timer.pause()

    def prime_replay(self):
        """The first few events contain the map and initial state. Until these load, the display will be blank. Call this method after a reset() to skip to these so that they are displayed immediately."""
        map_event_index = -1
        prop_update_index = -1
        for i, event in enumerate(self._events):
            if event.type == EventType.MAP_UPDATE:
                map_event_index = i
            if event.type == EventType.PROP_UPDATE:
                prop_update_index = i
            if prop_update_index != -1 and map_event_index != -1:
                break
        if map_event_index == -1 and prop_update_index == -1:
            return
        skip_to_index = max(map_event_index, prop_update_index)
        # Quickly send all events leading up to the map event.
        for i in range(0, skip_to_index + 1):
            self._update_instructions(self._instructions, self._events[i])
            for actor_id in self._message_queue:
                message = self.MessageFromEvent(
                    actor_id, self._events[i], self._instructions, noduration=True
                )
                self._message_queue[actor_id].append(message)
        self._event_index = skip_to_index
        self._starting_index = skip_to_index

    def reset(self):
        self._event_index = 0
        self._done = False
        self._paused = True
        self._instructions = []
        if len(self._events) > 1:
            # No pause before starting the first event.
            self._event_timer = CountDownTimer(0)
        # Repopulate all message queues with empty lists.
        for actor_id in self._message_queue:
            self._message_queue[actor_id] = deque()
        self._command_queue = deque()
        self._num_turns = 0

    def update(self):
        send_replay_state = False

        # Wait for someone to join in order to init.
        if not self._initialized and len(self._message_queue.keys()) > 0:
            self._initialized = True
            send_replay_state = True
            logger.info("Replay initialized.")
            self._events = list(
                Event.select()
                .where(Event.game_id == self._game_record.id)
                .order_by(Event.server_time)
            )
            self.reset()
            logger.info(f"Found {len(self._events)} events.")
            turn_states = [
                x
                for x in self._events
                if x.type in [EventType.START_OF_TURN, EventType.TURN_STATE]
            ]
            self._num_turns = max(
                [
                    x.turn_number
                    for x in filter(
                        lambda event: event.type
                        in [EventType.START_OF_TURN, EventType.TURN_STATE],
                        self._events,
                    )
                ],
                default=0,
            )
            self.prime_replay()

        if self._event_timer.expired() and self._event_index < len(self._events):
            send_replay_state = True
            self.advance_event()

        if len(self._command_queue) > 0:
            request = self._command_queue.popleft()
            command = request.command
            logger.info(f"Received command: {command}")
            send_replay_state = True
            if command == Command.PLAY:
                logger.info("Playing replay.")
                self._paused = False
                self._event_timer.start()
            elif command == Command.PAUSE:
                logger.info("Pausing replay.")
                self._paused = True
                self._event_timer.pause()
            elif command == Command.NEXT:
                self.advance_event()
            elif command == Command.PREVIOUS:
                self.rewind_event()
            elif command == Command.RESET:
                self.reset()
            elif command == Command.REPLAY_SPEED:
                logger.info(f"Setting replay speed to {request.replay_speed}.")
                self._speed = request.replay_speed
                if not self._event_timer.expired():
                    logger.info(
                        f"Respeed Time remaining: {self._event_timer.time_remaining()}"
                    )
                    self._event_timer.clear()
                    self._event_timer = CountDownTimer(
                        self.time_to_next_event().total_seconds()
                    )
                    self._event_timer.start()
                    logger.info(
                        f"Respeed recalculated time remaining: {self._event_timer.time_remaining()}"
                    )
            else:
                logger.info("Invalid command received.")

        if datetime.utcnow() > self._last_replay_info + timedelta(seconds=5):
            send_replay_state = True
            self._last_replay_info = datetime.utcnow()

        if send_replay_state:
            previous_event = (
                self._events[self._event_index - 1]
                if self._event_index > 0
                else self._events[0]
            )

            # Calculate percent completion. We can't calculate this from time
            # elapsed, as we may have replayed the game with speedups. Instead
            # calculate the time remaining by subtracting the current event's
            # time from the last event's time.  Then add the time remaining on
            # the current event, and multiply by the speed to adjust for the
            # current speedup.
            duration = self._events[-1].server_time - self._events[0].server_time
            if self._event_index < len(self._events):
                remaining = (
                    self._events[-1].server_time
                    - self._events[self._event_index].server_time
                )
            else:
                remaining = timedelta(seconds=0)
            current_event_remaining = (
                self._event_timer.time_remaining() * self._speed
                if not self._event_timer.expired()
                else timedelta(seconds=0)
            )
            total_remaining = remaining + current_event_remaining
            percent_complete = 1 - (total_remaining / duration)

            turn = previous_event.turn_number if previous_event.turn_number else -1

            replay_state = ReplayInfo(
                self._game_record.id,
                self._game_record.start_time,
                self._paused,
                previous_event.tick,
                self._events[-1].tick,
                turn,
                self._num_turns,
                previous_event.server_time,
                percent_complete,
            )
            response = ReplayResponse(ReplayResponseType.REPLAY_INFO, replay_state)
            message = message_from_server.ReplayResponseFromServer(response)
            for actor_id in self._message_queue:
                self._message_queue[actor_id].append(message)

    def on_game_over(self):
        logger.info(f"Game {self._room_id} is over.")

    def game_time(self):
        return datetime.utcnow() - self._start_time

    def turn_state(self):
        return Role.LEADER

    def calculate_score(self):
        return 0

    def selected_cards(self):
        return []

    def drain_messages(self, id, messages):
        for message in messages:
            self._drain_message(id, message)

    def _drain_message(self, id, message):
        if message.type == message_to_server.MessageType.REPLAY_REQUEST:
            replay_request = message.replay_request
            if replay_request is None:
                logger.warning("Received replay request with no replay request.")
                return
            if replay_request.type == ReplayRequestType.START_REPLAY:
                logger.warning(
                    f"Received start replay request. Room: {self._room_id}. Replay already started."
                )
                return
            if replay_request.type == ReplayRequestType.REPLAY_COMMAND:
                self._command_queue.append(replay_request)
                return
        else:
            logger.warning(f"Received unknown packet type: {message.type}")

    def create_actor(self, role):
        logger.info(f"create_actor() Role: {role}")
        # Replay actor. Just used to receive messages.
        actor_id = self._leader_id
        if actor_id not in self._message_queue:
            self._message_queue[actor_id] = deque()
        self._player_ids.append(actor_id)
        return actor_id

    def free_actor(self, actor_id):
        if actor_id in self._message_queue:
            del self._message_queue[actor_id]

    def fill_messages(
        self, player_id, out_messages: List[message_from_server.MessageFromServer]
    ) -> bool:
        """Serializes all messages to one player into a linear history.

        If any messages have been generated this iteration, caps those
        messages with a StateMachineTick. This lets us separate logic
        iterations on the receive side.
        """
        message = self._next_message(player_id)
        messages_added = 0
        while message != None:
            out_messages.append(message)
            messages_added += 1
            message = self._next_message(player_id)
        if messages_added == 0:
            return False
        return True

    def _next_message(self, player_id):
        if player_id not in self._message_queue:
            return None
        if len(self._message_queue[player_id]) == 0:
            return None
        message = self._message_queue[player_id].popleft()
        return message

    # Returns the current state of the game.
    def state(self, player_id=-1):
        return state_sync.StateSync(0, [], player_id, Role.LEADER)
