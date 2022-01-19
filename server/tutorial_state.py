from actor import Actor
from assets import AssetId
from messages.action import Action, Color, ActionType
from messages.rooms import Role
from messages import message_from_server
from messages import message_to_server
from messages import state_sync
from messages.objective import ObjectiveMessage
from hex import HecsCoord
from queue import Queue
from map_provider import MapProvider, MapType
from card import CardSelectAction
from util import IdAssigner
from datetime import datetime, timedelta
from messages.turn_state import TurnState, GameOverMessage, TurnUpdate
from messages.tutorials import TutorialRequestType, TutorialResponseFromStep, TutorialCompletedResponse, RoleFromTutorialName, TooltipType
from tutorial_steps import LoadTutorialSteps

import aiohttp
import asyncio
import dataclasses
import logging
import math
import random
import time
import uuid

LEADER_MOVES_PER_TURN = -1
FOLLOWER_MOVES_PER_TURN = -1

logger = logging.getLogger()

class TutorialGameState(object):
    def __init__(self, room_id, tutorial_name):
        self._room_id = room_id
        self._id_assigner = IdAssigner()

        self._player_role = RoleFromTutorialName(tutorial_name)

        # Logging init.
        self._recvd_log = logging.getLogger(f'room_{room_id}.recv')
        self._record_log = logging.getLogger(f'room_{room_id}.log')
        self._sent_log = logging.getLogger(f'room_{room_id}.sent')
        self._recvd_log.info("Tutorial State created.")
        self._record_log.info("Tutorial State created.")
        self._sent_log.info("Tutorial State created.")

        self._tutorial_name = tutorial_name
        self._tutorial_steps = LoadTutorialSteps(tutorial_name)
        self._tutorial_step_index = 0
        self._tutorial_responses = Queue()

        self._step_indicator_done = True

        # Maps from actor_id (prop id) to actor object (see definition below).
        self._actors = {}

        # Map props and actors share IDs from the same pool, so the ID assigner
        # is shared to prevent overlap.
        self._map_provider = MapProvider(MapType.HARDCODED, self._id_assigner)
        
        self._objectives = []
        self._objectives_stale = {}  # Maps from player_id -> bool if their objective list is stale.

        self._map_update = self._map_provider.map()
        self._map_stale = {} # Maps from player_id -> bool if their map is stale.

        self._synced = {}
        self._action_history = {}
        self._last_tick = datetime.now() # Used to time 1s ticks for turn state updates.
        initial_turn = TurnUpdate(
            self._player_role, LEADER_MOVES_PER_TURN, 6,
            datetime.now() + self.turn_duration(self._player_role),
            datetime.now(), 0, 0)
        self._turn_history = {}
        self.record_turn_state(initial_turn)

        self._spawn_points = [HecsCoord(1, 1, 0), HecsCoord(1, 2, 2)]
        self._done = False

        if (self._player_role == Role.LEADER):
            self._dummy_character = self.create_actor(Role.FOLLOWER)
        elif (self._player_role == Role.FOLLOWER):
            self._dummy_character = self.create_actor(Role.LEADER)

    def turn_duration(self, role):
        return timedelta(seconds=60) if role == Role.LEADER else timedelta(seconds=45)

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
        self.free_actor(self._dummy_character)
        self._done = True

    def record_action(self, action):
        # Marks an action as validated (i.e. it did not conflict with other actions).
        # Queues this action to be sent to each user.
        self._record_log.info(action)
        for id in self._actors:
            actor = self._actors[id]
            self._action_history[actor.actor_id()].append(action)

    def map(self):
        return self._map_provider.map()

    def cards(self):
        self._map_provider.cards()
    
    def done(self):
        return self._done

    async def update(self):
        last_loop = time.time()
        current_set_invalid = False
        while not self._done:
            await asyncio.sleep(0.001)
            poll_period = time.time() - last_loop
            if (poll_period) > 0.1:
                logging.warn(
                    f"Game {self._room_id} slow poll period of {poll_period}s")
            last_loop = time.time()

            # Check to see if the game is out of time.
            if self._turn_state.turns_left == -1:
                logging.info(
                    f"Game {self._room_id} is out of turns. Game over!")
                game_over_message = GameOverMessage(
                    self._turn_state.game_start, self._turn_state.sets_collected, self._turn_state.score)
                self.record_turn_state(game_over_message)
                self.end_game()
                continue
            
            # Handle actor actions.
            for actor_id in self._actors:
                actor = self._actors[actor_id]
                if actor.has_actions():
                    logger.info(f"Actor {actor_id} has pending actions.")
                    proposed_action = actor.peek()
                    if not self._turn_state.turn == actor.role():
                        actor.drop()
                        self.desync(actor_id)
                        logger.info(
                            f"Actor {actor_id} is not the current role. Dropping pending action.")
                        continue
                    if self._turn_state.moves_remaining == 0:
                        actor.drop()
                        self.desync(actor_id)
                        logger.info(
                            f"Actor {actor_id} is out of moves. Dropping pending action.")
                        continue
                    if self.valid_action(actor_id, proposed_action):
                        actor.step()
                        self.record_action(proposed_action)
                        color = Color(0, 0, 1, 1) if not current_set_invalid else Color(1, 0, 0, 1)
                        self.check_for_stepped_on_cards(actor_id, proposed_action, color)
                        if self._tutorial_step_index > 0:
                            current_step = self._tutorial_steps[self._tutorial_step_index - 1]
                            if (current_step.indicator is not None) and (current_step.indicator.location == actor.location()):
                                logger.info("STEPPED ON INDICATOR!!")
                                self._step_indicator_done = True
                    else:
                        actor.drop()
                        self.desync(actor_id)
                        self._record_log.error(f"Resyncing {actor_id} after invalid action.")
                        continue

            # Check to see if the indicator has been reached.
            if self._tutorial_step_index > 0:
                current_step = self._tutorial_steps[self._tutorial_step_index - 1]
                # Check to see if instructions have been followed.
                if (current_step.indicator is not None) and self._step_indicator_done:
                    if current_step.tooltip.type == TooltipType.UNTIL_INDICATOR_REACHED:
                        logger.info("INDICATOR REACHED")
                        self.send_next_tutorial_step()
                # Check to see if instructions have been followed.
                if current_step.tooltip.type == TooltipType.UNTIL_OBJECTIVES_COMPLETED:
                    objectives_completed = True
                    for objective in self._objectives:
                        if not objective.completed:
                            logger.info(f"INSTRUCTIONS NOT COMPLETE. WAITING ON {objective.text}")
                            objectives_completed = False
                            break
                    next_step_ready = objectives_completed
                    if current_step.indicator is not None:
                        next_step_ready &= self._step_indicator_done
                    if next_step_ready:
                        self.send_next_tutorial_step()


            selected_cards = list(self._map_provider.selected_cards())
            cards_changed = False
            if self._map_provider.selected_cards_collide() and not current_set_invalid:
                current_set_invalid = True
                self._record_log.info("Invalid set detected.")
                cards_changed = True
                # Indicate invalid set.
                for card in selected_cards:
                    # Outline the cards in red.
                    card_select_action = CardSelectAction(card.id, True, Color(1, 0, 0, 1))
                    self.record_action(card_select_action)
            
            if not self._map_provider.selected_cards_collide() and current_set_invalid:
                logger.info("Marking set as clear (not invalid) because it is smaller than 3.")
                current_set_invalid = False
                cards_changed = True
                for card in selected_cards:
                    # Outline the cards in blue.
                    card_select_action = CardSelectAction(card.id, True, Color(0, 0, 1, 1))
                    self.record_action(card_select_action)

            if self._map_provider.selected_valid_set():
                self._record_log.info("Unique set collected. Awarding points.")
                current_set_invalid = False
                added_turns = 0
                cards_changed = True
                if self._turn_state.sets_collected == 0:
                    added_turns = 5
                elif self._turn_state.sets_collected in [1, 2]:
                    added_turns = 4
                elif self._turn_state.sets_collected in [3, 4]:
                    added_turns = 3
                new_turn_state = TurnUpdate(
                    self._turn_state.turn,
                    self._turn_state.moves_remaining,
                    self._turn_state.turns_left + added_turns,
                    self._turn_state.turn_end,
                    self._turn_state.game_start,
                    self._turn_state.sets_collected + 1,
                    self._turn_state.score + 1)
                self.record_turn_state(new_turn_state)
                # Clear card state and remove the cards in the winning set.
                logging.info("Clearing selected cards")
                for card in selected_cards:
                    self._map_provider.set_selected(card.id, False)
                    card_select_action = CardSelectAction(card.id, False)
                    self.record_action(card_select_action)
                    self._map_provider.remove_card(card.id)
                # If the tutorial was waiting for a set, advance the tutorial.
                if self._tutorial_step_index > 0:
                    current_step = self._tutorial_steps[self._tutorial_step_index - 1]
                    if current_step.tooltip.type == TooltipType.UNTIL_SET_COLLECTED:
                        self.send_next_tutorial_step()

            if cards_changed:
                # We've changed cards, so we need to mark the map as stale for all players.
                self._map_update = self._map_provider.map()
                for actor_id in self._actors:
                    self._map_stale[actor_id] = True
        # Before quitting, sleep for a bit to ensure that all messages have been sent.
        await asyncio.sleep(1)

    def moves_per_turn(self, role):
        return LEADER_MOVES_PER_TURN if role == Role.LEADER else FOLLOWER_MOVES_PER_TURN
    
    def turn_state(self):
        return self._turn_state

    def calculate_score(self):
        self._turn_state.score = self._turn_state.sets_collected * 100

    def selected_cards(self):
        return list(self._map_provider.selected_cards())

    def check_for_stepped_on_cards(self, actor_id, action, color):
        actor = self._actors[actor_id]
        stepped_on_card = self._map_provider.card_by_location(
            actor.location())
        # If the actor just moved and stepped on a card, mark it as selected.
        if (action.action_type == ActionType.TRANSLATE) and (stepped_on_card is not None):
            logger.info(
                f"Player {actor.actor_id()} stepped on card {str(stepped_on_card)}.")
            selected = not stepped_on_card.selected
            self._map_provider.set_selected(
                stepped_on_card.id, selected)
            card_select_action = CardSelectAction(stepped_on_card.id, selected, color)
            self.record_action(card_select_action)

    def handle_packet(self, id, message):
        if message.type == message_to_server.MessageType.ACTIONS:
            logger.info(f'Actions received. Room: {self._room_id}')
            for action in message.actions:
                logger.info(f'{action.id}:{action.displacement}')
                self.handle_action(id, action)
        elif message.type == message_to_server.MessageType.OBJECTIVE:
            logger.info(
                f'Objective received. Room: {self._room_id}, Text: {message.objective.text}')
            self.handle_objective(id, message.objective)
        elif message.type == message_to_server.MessageType.OBJECTIVE_COMPLETED:
            logger.info(
                f'Objective Compl received. Room: {self._room_id}, Text: {message.objective_complete.uuid}')
            self.handle_objective_complete(id, message.objective_complete)
        elif message.type == message_to_server.MessageType.TURN_COMPLETE:
            logger.info(f'Turn Complete received. Ignoring -- this is a tutorial.')
            return
        elif message.type == message_to_server.MessageType.STATE_SYNC_REQUEST:
            logger.info(
                f'Sync request recvd. Room: {self._room_id}, Player: {id}')
            self.desync(id)
        elif message.type == message_to_server.MessageType.TUTORIAL_REQUEST:
            logger.info(f'Tutorial request. Room: {self._room_id}, Player: {id}')
            self.handle_tutorial_request(id, message.tutorial_request)
        else:
            logger.warn(f'Received unknown packet type: {message.type}')

    def handle_action(self, actor_id, action):
        if (action.id != actor_id):
            self.desync(actor_id)
            return
        self._recvd_log.info(action)
        self._actors[actor_id].add_action(action)

    def handle_objective(self, id, objective):
        if self._actors[id].role() != Role.LEADER:
            logger.warn(
                f'Warning, objective received from non-leader ID: {str(id)}')
            return
        # TODO: Make UUID and non-UUID'd objectives separate message types.
        objective.uuid = uuid.uuid4().hex
        self._recvd_log.info(objective)
        self._objectives.append(objective)
        for actor_id in self._actors:
            self._objectives_stale[actor_id] = True
        # Check to see if the current step can be dismissed by a sent message.
        if self._tutorial_step_index > 0:
            current_step = self._tutorial_steps[self._tutorial_step_index - 1]
            if current_step.tooltip.type == TooltipType.UNTIL_MESSAGE_SENT:
                self.send_next_tutorial_step()


    def handle_objective_complete(self, id, objective_complete):
        if self._actors[id].role() != Role.FOLLOWER:
            logger.warn(
                f'Warning, obj complete received from non-follower ID: {str(id)}')
            return
        self._recvd_log.info(objective_complete)
        for i, objective in enumerate(self._objectives):
            if objective.uuid == objective_complete.uuid:
                self._record_log.info(objective_complete)
                self._objectives[i].completed = True
                break
        for actor_id in self._actors:
            self._objectives_stale[actor_id] = True
    
    def handle_tutorial_request(self, id, tutorial):
        if tutorial.type == TutorialRequestType.REQUEST_NEXT_STEP:
            if self._tutorial_step_index > 0:
                current_step = self._tutorial_steps[self._tutorial_step_index - 1]
                if (current_step.indicator is not None) and not self._step_indicator_done:
                    logger.warn(f"Received request for next step, but the player hasn't visited the indicator. ID: {id}, Indicator location: {current_step.indicator.location}, Player location: {self._actors[id].location()}")
                    return
                if (current_step.tooltip.type == TooltipType.UNTIL_MESSAGE_SENT):
                    logger.warn(f"Received request for next step, but the player hasn't sent a message yet. ID: {id}")
                    return
                if (current_step.tooltip.type == TooltipType.UNTIL_OBJECTIVES_COMPLETED):
                    for objective in self._objectives:
                        if not objective.completed:
                            logger.warn(f"Received request for next step, but the player hasn't completed the objective. ID: {id}, Objective: {objective}")
                            return
            self.send_next_tutorial_step()
        else:
            logger.warn(f"Received invalid tutorial request type {tutorial.type}")
    
    def send_next_tutorial_step(self):
        if self._tutorial_step_index >= len(self._tutorial_steps):
            self._tutorial_responses.put(TutorialCompletedResponse(self._tutorial_name))
            self.end_game()
            return
        next_step = self._tutorial_steps[self._tutorial_step_index]
        logger.info(f"Preparing step {self._tutorial_step_index + 1} of {len(self._tutorial_steps)}.")
        self._tutorial_responses.put(TutorialResponseFromStep(self._tutorial_name, next_step))
        instruction = next_step.instruction
        if instruction is not None:
            objective = ObjectiveMessage()
            objective.text = instruction.text
            objective.completed = False
            objective.uuid = uuid.uuid4().hex
            self._objectives.append(objective)
            for actor_id in self._actors:
                self._objectives_stale[actor_id] = True
        if next_step.indicator is not None:
            self._step_indicator_done = False
        self._tutorial_step_index += 1

    def create_actor(self, role):
        spawn_point = self._spawn_points.pop() if self._spawn_points else HecsCoord(0, 0, 0)
        print(spawn_point)
        asset_id = AssetId.PLAYER if role == Role.LEADER else AssetId.FOLLOWER_BOT
        actor = Actor(self._id_assigner.alloc(), asset_id, role, spawn_point)
        self._actors[actor.actor_id()] = actor
        self._action_history[actor.actor_id()] = []
        self._synced[actor.actor_id()] = False
        # Mark clients as desynced.
        self.desync_all()

        # Send a TurnState with unlimited moves, time left.
        turn_update = TurnUpdate(self._player_role,
                                    10,
                                    10,
                                    datetime.now() + timedelta(minutes=1),
                                    self._turn_state.game_start,
                                    self._turn_state.sets_collected,
                                    self._turn_state.score)
        self.record_turn_state(turn_update)

        return actor.actor_id()

    def free_actor(self, actor_id):
        if actor_id in self._actors:
            del self._actors[actor_id]
        if actor_id in self._action_history:
            del self._action_history[actor_id]
        if actor_id in self._objectives_stale:
            del self._objectives_stale[actor_id]
        if actor_id in self._turn_history:
            del self._turn_history[actor_id]
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
    
    def has_pending_messages(self):
        for actor_id in self._actors:
            if not self.is_synced(actor_id):
                return True
            if len(self._action_history[actor_id]) > 0:
                logger.info("Pending actions")
                return True
            if self._objectives_stale[actor_id]:
                logger.info("Pending objectives")
                return True
            if not self._turn_history[actor_id].empty():
                logger.info("Pending turn history")
                return True
            if not self._tutorial_responses.empty():
                return True
        return False

    def drain_message(self, player_id):
        """ Returns a MessageFromServer object to send to the indicated player.

            If no message is available, returns None.
        """
        map_update = self.drain_map_update(player_id)
        if map_update is not None:
            logger.info(
                f'Room {self._room_id} drained map update {map_update} for player_id {player_id}')
            return message_from_server.MapUpdateFromServer(map_update)

        if not self.is_synced(player_id):
            state_sync = self.sync_message_for_transmission(player_id)
            logger.info(
                f'Room {self._room_id} drained state sync: {state_sync} for player_id {player_id}')
            msg = message_from_server.StateSyncFromServer(state_sync)
            return msg

        actions = self.drain_actions(player_id)
        if len(actions) > 0:
            logger.info(
                f'Room {self._room_id} drained {len(actions)} actions for player_id {player_id}')
            msg = message_from_server.ActionsFromServer(actions)
            return msg

        objectives = self.drain_objectives(player_id)
        if len(objectives) > 0:
            logger.info(
                f'Room {self._room_id} drained {len(objectives)} texts for player_id {player_id}')
            msg = message_from_server.ObjectivesFromServer(objectives)
            return msg
        
        turn_state = self.drain_turn_state(player_id)
        if not turn_state is None:
            logger.info(
                f'Room {self._room_id} drained ts {turn_state} for player_id {player_id}')
            msg = message_from_server.GameStateFromServer(turn_state)
            return msg
        
        tutorial_response = self.drain_tutorial_response(player_id)
        if not tutorial_response is None:
            logger.info(
                f'Room {self._room_id} drained tr {tutorial_response} for player_id {player_id}')
            msg = message_from_server.TutorialResponseFromServer(tutorial_response)
            return msg

        # Nothing to send.
        return None

    def drain_actions(self, actor_id):
        if not actor_id in self._action_history:
            return []
        action_history = self._action_history[actor_id]
        # Log actions sent to client.
        for action in action_history:
            self._sent_log.info(f"to: {actor_id} action: {action}")
        self._action_history[actor_id] = []
        return action_history

    def drain_objectives(self, actor_id):
        if not actor_id in self._objectives_stale:
            self._objectives_stale[actor_id] = True
        
        if not self._objectives_stale[actor_id]:
            return []
        
        # Send the latest objective list and mark as fresh for this player.
        self._objectives_stale[actor_id] = False
        self._sent_log.info(f"to: {actor_id} objectives: {self._objectives}")
        return self._objectives
    
    def drain_map_update(self, actor_id):
        if not actor_id in self._map_stale:
            self._map_stale[actor_id] = True
        
        if not self._map_stale[actor_id]:
            return None
        
        # Send the latest map and mark as fresh for this player.
        self._map_stale[actor_id] = False
        self._sent_log.info(f"to: {actor_id} map: {self._map_update}")
        return self._map_update

    def drain_tutorial_response(self, actor_id):
        if self._tutorial_responses.empty():
            return None
        return self._tutorial_responses.get()


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