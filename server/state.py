import aiohttp
import asyncio
import logging

from messages.action import Action, ActionType
from messages.rooms import Role
from messages import state_sync
from hex import HecsCoord
from queue import Queue
from map_provider import HardcodedMapProvider
from card import CardSelectAction
from util import IdAssigner
from datetime import datetime, timedelta
from messages.turn_state import TurnState, GameOverMessage, TurnUpdate

import math
import time
import dataclasses

class State(object):
    def __init__(self, room_id):
        self._room_id = room_id
        self._recvd_log = logging.getLogger(f'room_{room_id}.recv')
        self._record_log = logging.getLogger(f'room_{room_id}.log')
        self._sent_log = logging.getLogger(f'room_{room_id}.sent')
        self._recvd_log.info("State created.")
        self._record_log.info("State created.")
        self._sent_log.info("State created.")
        self._actors = {}
        
        self._message_history = {}
        self._synced = {}
        self._id_assigner = IdAssigner()
        self._action_history = {}
        self._start_time = datetime.now()
        self._last_tick = datetime.now() # Used to time 100ms ticks for turn state updates.
        self._last_desync = datetime.now() # Used to periodically force all clients to statesync. (every 10s)
        initial_turn = TurnUpdate(Role.LEADER, 1000, datetime.now() +
                                  timedelta(minutes=1), self._start_time, 0, 0)
        self._turn_history = {}
        self.record_turn_state(initial_turn)

        # Map props and actors share IDs from the same pool, so the ID assigner
        # is shared to prevent overlap.
        self._map_provider = HardcodedMapProvider(self._id_assigner)
        self._done = False

    def record_turn_state(self, turn_state):
        # Record a copy of the current turn state.
        self._record_log.info(turn_state)
        self._turn_state = turn_state
        for actor_id in self._actors:
            if not actor_id in self._turn_history:
                self._turn_history[actor_id] = Queue()
            self._turn_history[actor_id].put(
                dataclasses.replace(turn_state))

    def drain_turn_state(self, actor_id):
        if not actor_id in self._turn_history:
            self._turn_history[actor_id] = Queue()
        if self._turn_history[actor_id].empty():
            return None
        turn = self._turn_history[actor_id].get()
        self._sent_log.info(f"to: {actor_id} turn_state: {turn}")
        return turn

    def end_game(self):
        logging.info(f"Game ending.")
        self._done = True

    def record_action(self, action):
        # Marks an action as validated (i.e. it did not conflict with other actions).
        # Queues this action to be sent to each user.
        self._record_log.info(action)
        for id in self._actors:
            actor = self._actors[id]
            self._action_history[actor.actor_id()].append(action)

    def record_text(self, actor, message):
        if not actor.actor_id() in self._message_history:
            self._message_history[actor.actor_id()] = []
        self._message_history[actor.actor_id()].append(message)

    def map(self):
        return self._map_provider.map()

    def cards(self):
        self._map_provider.cards()

    async def update(self):
        last_loop = time.time()
        while not self._done:
            await asyncio.sleep(0.01)
            poll_period = time.time() - last_loop
            if (poll_period) > 0.1:
                logging.warn(
                    f"Game {self._room_id} slow poll period of {poll_period}s")
            last_loop = time.time()

            # Check to see if the game is out of time.
            if datetime.now() > self._turn_state.game_end_date:
                logging.info(
                    f"Game {self._room_id} is out of time. Game over!")
                game_over_message = GameOverMessage(
                    self._start_time, self._turn_state.sets_collected, self._turn_state.score)
                self.record_turn_state(game_over_message)
                self.end_game()
                continue

            # Recalculate the turn state with the remaining game time.
            if datetime.now() > self._last_tick + timedelta(milliseconds=1000):
                self._last_tick = datetime.now()
                turn_update = TurnUpdate(self._turn_state.turn,
                                         self._turn_state.moves_remaining, self._turn_state.game_end_date,
                                         self._start_time, self._turn_state.sets_collected,
                                         self._turn_state.score)
                self.record_turn_state(turn_update)
            
            if datetime.now() > self._last_desync + timedelta(seconds=10):
                self._last_desync = datetime.now()
                self.desync_all()

            for actor_id in self._actors:
                actor = self._actors[actor_id]

                # Handle actor actions.
                if actor.has_actions():
                    logging.info(f"Actor {actor_id} has pending actions.")
                    action = actor.peek()
                    if not self._turn_state.role == actor.role():
                        actor.drop()
                        self.desync_all()
                        logging.info(
                            f"Actor {actor_id} is not the current role. Dropping pending action.")
                        continue
                    if self.valid_action(actor_id, action):
                        actor.step()
                        self.record_action(action)
                        self.check_for_stepped_on_cards(actor_id, action)
                        opposite_role = Role.LEADER if self._turn_state.role == Role.FOLLOWER else Role.FOLLOWER
                        next_role = opposite_role if self._turn_state.moves_remaining == 0 else self._turn_state.role
                        moves_remaining = self.moves_per_turn(
                            next_role) if self._turn_state.moves_remaining == 0 else self._turn_state.moves_remaining - 1
                        turn_update = TurnUpdate(self._turn_state.role, moves_remaining, self._turn_state.game_end_date,
                                                 self._start_Time, self._turn_state.sets_collected, self._turn_state.score)
                        self.record_turn_state(turn_update)
                    else:
                        actor.drop()
                        self.desync_all()
                        print("Found invalid action. Resyncing...")
                        continue

                # Handle any pending text messages.
                messages = actor.drain_messages()
                if len(messages) > 0:
                    logging.info(
                        f"Actor {actor_id} has message {messages[0]} pending for them")
                    self._record_log.info(messages[0])
                    self.record_text(actor, messages[0])

            selected_cards = list(self._map_provider.selected_cards())
            if len(selected_cards) >= 3:
                logging.info("3 cards collected.")
                # Determine if the cards are unique.
                shapes = set()
                colors = set()
                counts = set()
                for card in selected_cards:
                    shapes.add(card.shape)
                    colors.add(card.color)
                    counts.add(card.count)

                if len(shapes) == len(colors) == len(counts) == 3:
                    logging.info("Unique set collected. Awarding points.")
                    new_turn_state = TurnUpdate(
                        self._turn_state.role, self._turn_state.moves_remaining + 10, self._turn_state.end_time + timedelta(minutes=1), self._start_time, self._turn_state.sets_collected + 1, self._turn_state.score + 10)
                    self.record_turn_state(new_turn_state)
                    self.desync_all()

                # Clear card state.
                logging.info("Clearing selected cards")
                for card in selected_cards:
                    self._map_provider.set_selected(card.id, False)
                    card_select_action = CardSelectAction(card.id, False)
                    self.record_action(card_select_action)

    def calculate_moves_per_turn(self, role):
        return 5 if role == Role.LEADER else 10

    def calculate_score(self):
        self._turn_state.score = self._turn_state.sets_collected * 100

    def check_for_stepped_on_cards(self, actor_id, action):
        actor = self._actors[actor_id]
        stepped_on_card = self._map_provider.card_by_location(
            actor.location())
        # If the actor just moved and stepped on a card, mark it as selected.
        if (action.action_type == ActionType.TRANSLATE) and (stepped_on_card is not None):
            logging.info(
                f"Player {actor.actor_id()} stepped on card {str(stepped_on_card)}.")
            selected = not stepped_on_card.selected
            self._map_provider.set_selected(
                stepped_on_card.id, selected)
            card_select_action = CardSelectAction(stepped_on_card.id, selected)
            self.record_action(card_select_action)

    def handle_action(self, actor_id, action):
        if (action.id != actor_id):
            self.desync(actor_id)
            return
        self._recvd_log.info(action)
        self._actors[actor_id].add_action(action)

    def handle_text(self, id, message):
        if self._actors[id].role() != Role.LEADER:
            logging.warn(
                f'Warning, text message received from non-leader ID: {str(id)}')
            return
        self._recvd_log.info(message)
        for a in self._actors:
            self._actors[a].add_message(message)

    def create_actor(self, role):
        actor = Actor(self._id_assigner.alloc(), 0, role)
        self._actors[actor.actor_id()] = actor
        self._action_history[actor.actor_id()] = []
        self._synced[actor.actor_id()] = False
        # Mark clients as desynced.
        self.desync_all()
        return actor.actor_id()

    def free_actor(self, actor_id):
        del self._actors[actor_id]
        del self._action_history[actor_id]
        self._id_assigner.free(actor_id)
        # Mark clients as desynced.
        self.desync_all()

    def get_actor(self, player_id):
        return self._actors[player_id]

    def desync(self, actor_id):
        self._synced[actor_id] = False

    def desync_all(self):
        for a in self._actors:
            actor = self._actors[a]
            self._synced[actor.actor_id()] = False

    def is_synced(self, actor_id):
        return self._synced[actor_id]

    def is_synced_all(self):
        for a in self._actors:
            if not self.synced(self._actors[a].actor_id()):
                return False
        return True

    def drain_actions(self, actor_id):
        if not actor_id in self._action_history:
            return []
        action_history = self._action_history[actor_id]
        # Log actions sent to client.
        for action in action_history:
            self._sent_log.info(f"to: {actor_id} action: {action}")
        self._action_history[actor_id] = []
        return action_history

    def drain_messages(self, actor_id):
        if not actor_id in self._message_history:
            return []
        message_history = self._message_history[actor_id]
        # Log actions sent to client.
        for message in message_history:
            self._sent_log.info(f"to: {actor_id} message: {message}")
        self._message_history[actor_id] = []
        return message_history

    # Returns the current state of the game.
    def state(self, actor_id=-1):
        actor_states = []
        for a in self._actors:
            actor = self._actors[a]
            actor_states.append(actor.state())
        return state_sync.StateSync(len(self._actors), actor_states, actor_id)

    # Returns the current state of the game.
    # Calling this message comes with the assumption that the response will be transmitted to the clients.
    # Once this function returns, the clients are marked as synchronized.
    def sync_message_for_transmission(self, actor_id):
        # This won't do... there might be some weird oscillation where an
        # in-flight invalid packet triggers another sync. need to communicate
        # round trip.
        sync_message = self.state(actor_id)
        self._synced[actor_id] = True
        return sync_message

    def valid_action(self, actor_id, action):
        if (action.action_type == ActionType.TRANSLATE):
            cartesian = action.displacement.cartesian()
            # Add a small delta for floating point comparison.
            if (math.sqrt(cartesian[0]**2 + cartesian[1]**2) > 1.001):
                return False
        if (action.action_type == ActionType.ROTATE):
            if (action.rotation > 60.01):
                return False
        return True


class Actor(object):
    def __init__(self, actor_id, asset_id, role):
        self._actor_id = actor_id
        self._asset_id = asset_id
        self._actions = Queue()
        self._messages = []
        self._location = HecsCoord(0, 0, 0)
        self._heading_degrees = 0
        self._role = role

    def turn():
        pass

    def actor_id(self):
        return self._actor_id

    def asset_id(self):
        return self._asset_id

    def role(self):
        return self._role

    def add_action(self, action):
        self._actions.put(action)

    def add_message(self, message):
        self._messages.append(message)
        logging.info(
            f"Actor {self._actor_id} received message {message}. messages pending: {len(self._messages)}")

    def drain_messages(self):
        messages = self._messages
        self._messages = []
        return messages

    def has_actions(self):
        return not self._actions.empty()

    def location(self):
        return self._location

    def heading_degrees(self):
        return int(self._heading_degrees)

    def state(self):
        return state_sync.Actor(self.actor_id(), self.asset_id(),
                                self._location, self._heading_degrees)

    def peek(self):
        """ Peeks at the next action without consuming it. """
        return self._actions.queue[0]

    def step(self):
        """ Executes & consumes an action from the queue."""
        if not self.has_actions():
            return
        action = self._actions.get()
        self._location = HecsCoord.add(self._location, action.displacement)
        self._heading_degrees += action.rotation

    def drop(self):
        """ Drops an action instead of acting upon it."""
        if not self.has_actions():
            return
        _ = self._actions.get()
