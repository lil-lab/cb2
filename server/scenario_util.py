""" Utilities used for working with scenarios and game data."""
import logging
from datetime import datetime, timedelta

import orjson

import server.messages.action as action_module
import server.messages.objective as objective
import server.schemas.game as game_db
from server.actor import Actor
from server.card import Card
from server.messages.map_update import MapUpdate
from server.messages.prop import PropType, PropUpdate
from server.messages.rooms import Role
from server.messages.scenario import Scenario
from server.messages.state_sync import StateSync
from server.messages.turn_state import TurnState, TurnUpdate
from server.schemas.event import Event, EventOrigin, EventType
from server.schemas.util import InitialState

logger = logging.getLogger(__name__)

LEADER_MOVES_PER_TURN = 5
FOLLOWER_MOVES_PER_TURN = 10
LEADER_SECONDS_PER_TURN = 50
FOLLOWER_SECONDS_PER_TURN = 15


def TurnDuration(role):
    return (
        timedelta(seconds=LEADER_SECONDS_PER_TURN)
        if role == Role.LEADER
        else timedelta(seconds=FOLLOWER_SECONDS_PER_TURN)
    )


def ReconstructScenarioFromEvent(event_uuid: str) -> Scenario:
    """Looks up a given event in the database.

    Returns:
        A tuple of (Scenario, None) if the scenario was found, or (None, error_message) if not.

    """
    # Get the event matching this UUID, make sure it's unique.
    event_query = (
        Event.select().join(game_db.Game).where(Event.id == event_uuid).limit(1)
    )
    if event_query.count() != 1:
        return (
            None,
            f"1 Event {event_uuid} not found. ({event_query.count()} found)",
        )
    event = event_query.get()
    game_record = event.game

    # Get all events from the same game that happened before this event.
    game_events = (
        Event.select()
        .where(Event.game == game_record, Event.server_time <= event.server_time)
        .order_by(Event.server_time)
    )

    # Get the game map.
    map_event = game_events.where(Event.type == EventType.MAP_UPDATE).get()
    map_update = MapUpdate.from_json(map_event.data)

    card_events = game_events.where(
        Event.type
        << [
            EventType.CARD_SET,
            EventType.CARD_SPAWN,
            EventType.CARD_SELECT,
            EventType.PROP_UPDATE,
        ]
    ).order_by(Event.server_time)

    # Integrate all prop, cardset and card spawn events up to the given event, to get the current card state
    cards = []
    cards_by_loc = {}
    for event in card_events:
        if event.type == EventType.CARD_SET:
            data = orjson.loads(event.data)
            set_cards = [Card.from_dict(card) for card in data["cards"]]
            # Clear cards that were in the set
            for card in set_cards:
                cards_by_loc[card.location] = None
        if event.type == EventType.CARD_SPAWN:
            data = orjson.loads(event.data)
            card = Card.from_dict(data)
            cards_by_loc[card.location] = card
        if event.type == EventType.CARD_SELECT:
            card = Card.from_json(event.data)
            cards_by_loc[card.location] = card
        elif event.type == EventType.PROP_UPDATE:
            # Regen props from the prop update
            prop_update = PropUpdate.from_json(event.data)
            cards = [
                Card.FromProp(prop)
                for prop in prop_update.props
                if prop.prop_type == PropType.CARD
            ]
            cards_by_loc = {}
            for card in cards:
                cards_by_loc[card.location] = card

    cards = cards_by_loc.values()
    # Filter out None values
    cards = [card for card in cards if card is not None]
    logger.debug(f"Detected {len(cards)} cards in the game. at this point.")

    turn_record_query = game_events.where(
        Event.type << [EventType.TURN_STATE, EventType.START_OF_TURN]
    ).order_by(Event.server_time.desc())
    turn_state = None
    if turn_record_query.count() == 0:
        # Initial turn.
        turn_state = TurnUpdate(
            Role.LEADER,
            LEADER_MOVES_PER_TURN,
            6,
            datetime.utcnow()
            + TurnDuration(Role.LEADER),  # pylint: disable=protected-access
            datetime.utcnow(),
            0,
            0,
            0,
        )
    else:
        turn_record = turn_record_query.get()
        turn_state = TurnState.from_json(turn_record.data)

    # Integrate all instruction events up to the given event, to get the current instruction state
    instruction_list = []
    instruction_events = game_events.where(
        Event.type
        << [
            EventType.INSTRUCTION_SENT,
            EventType.INSTRUCTION_ACTIVATED,
            EventType.INSTRUCTION_CANCELLED,
            EventType.INSTRUCTION_DONE,
        ]
    ).order_by(Event.server_time)
    instr_list_debug = []
    for event in instruction_events:
        if event.type == EventType.INSTRUCTION_SENT:
            instr_list_debug.append(event.short_code[0:5])
        if event.type == EventType.INSTRUCTION_DONE:
            # Delete the instruction from the list.
            if len(instr_list_debug) > 0:
                instr_list_debug = instr_list_debug[1:]
        if event.type == EventType.INSTRUCTION_CANCELLED:
            # Delete the instruction from the list.
            if len(instr_list_debug) > 0:
                instr_list_debug = instr_list_debug[1:]
        logger.info(
            f"{EventType(event.type).name}: UUID: {event.id.hex[0:5]} instr UUID: {event.short_code[0:5]} instrs list: {instr_list_debug}"
        )
    instruction_list = []
    for event in instruction_events:
        if event.type == EventType.INSTRUCTION_SENT:
            instruction_list.append(objective.ObjectiveMessage.from_json(event.data))
            logger.info(f"Sent: {instruction_list[-1].uuid}")
        if event.type == EventType.INSTRUCTION_ACTIVATED:
            parent_instruction_event = event.parent_event
            instruction = objective.ObjectiveMessage.from_json(
                parent_instruction_event.data
            )
            logger.info(f"Activated: {instruction.uuid}")
            if instruction_list[0].uuid != instruction.uuid:
                for instruction in instruction_list:
                    logger.info(f"Instruction: {instruction.uuid}")
                return (
                    None,
                    f"Activated instruction {instruction.uuid} not found in instruction list.",
                )
        if event.type == EventType.INSTRUCTION_CANCELLED:
            parent_instruction_event = event.parent_event
            instruction = objective.ObjectiveMessage.from_json(
                parent_instruction_event.data
            )
            try:
                if instruction_list[0].uuid != instruction.uuid:
                    return (
                        None,
                        f"Cancelled instruction {event.data} not found in instruction list.",
                    )
            except IndexError:
                # Print the list of instructions.
                logger.info(
                    f"Instruction list is empty. ================ cancelled: {instruction.uuid}"
                )
                for instruction in instruction_list:
                    logger.info(f"Instruction: {instruction.uuid}")
                # raise e
            if len(instruction_list) > 0:
                logger.info(f"Cancelled: {instruction_list[0].uuid}")
                # Delete the instruction from the list.
                instruction_list = instruction_list[1:]
        if event.type == EventType.INSTRUCTION_DONE:
            parent_instruction_event = event.parent_event
            instruction = objective.ObjectiveMessage.from_json(
                parent_instruction_event.data
            )
            logger.info(f"Done: {instruction_list[0].uuid}")
            # Make sure this instruction is at the head of the list.
            if instruction_list[0].uuid != instruction.uuid:
                return (
                    None,
                    f"Done instruction {event.data} not found in instruction list.",
                )
            # Delete the instruction from the list.
            instruction_list = instruction_list[1:]

    initial_state_event = game_events.where(
        Event.type == EventType.INITIAL_STATE,
    )
    if initial_state_event.count() != 1:
        return (
            None,
            f"Single initial state event not found. ({initial_state_event.count()} found)",
        )
    initial_state_event = initial_state_event.get()
    initial_state = InitialState.from_json(initial_state_event.data)

    leader = Actor(
        21,
        0,
        Role.LEADER,
        initial_state.leader_position,
        False,
        initial_state.leader_rotation_degrees,
    )
    follower = Actor(
        22,
        0,
        Role.FOLLOWER,
        initial_state.follower_position,
        False,
        initial_state.follower_rotation_degrees,
    )

    moves = game_events.where(Event.type == EventType.ACTION)
    logger.debug(f"Found {moves.count()} moves before event {event_uuid}")
    for move in moves:
        action = action_module.Action.from_json(move.data)
        if action.action_type not in [
            action_module.ActionType.INIT,
            action_module.ActionType.INSTANT,
            action_module.ActionType.ROTATE,
            action_module.ActionType.TRANSLATE,
        ]:
            continue
        if move.origin == EventOrigin.LEADER:
            leader.add_action(action)
            leader.step()
        elif move.origin == EventOrigin.FOLLOWER:
            follower.add_action(action)
            follower.step()
        else:
            return None, f"Unknown event origin: {move.origin}"
    state_sync_msg = StateSync(2, [leader.state(), follower.state()], -1, Role.NONE)
    import sys

    sys.exit()
    return (
        Scenario(
            "",
            map_update,
            PropUpdate(props=[card.prop() for card in cards]),
            turn_state,
            instruction_list,
            state_sync_msg,
        ),
        None,
    )
