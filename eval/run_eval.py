import logging

import fire
from tqdm import tqdm

from agents.agent import Agent, CreateAgent, Role
from agents.config import ReadAgentConfigOrDie
from py_client.game_endpoint import GameState
from py_client.local_game_coordinator import LocalGameCoordinator
from server.card import Card
from server.config.config import ReadServerConfigOrDie
from server.db_tools.db_utils import ListAnalysisGames
from server.lobbies.open_lobby import OpenLobby
from server.lobby_consts import LobbyInfo, LobbyType
from server.messages.prop import PropType
from server.scenario_util import GameStateFromScenario, ReconstructScenarioFromEvent
from server.schemas import base
from server.schemas.eval import Eval, RunSource
from server.schemas.event import Event, EventType
from server.util import GetCommitHash

logger = logging.getLogger(__name__)

# This is the default lobby name. Should equal the eval lobby defined in
# server/config/config.py. Must match the eval lobby on the remote server.
REMOTE_LOBBY_NAME = "eval-lobby"


def SwitchToDatabase(db):
    base.SetDatabaseByPath(db)
    base.ConnectDatabase()


def follower_eval_start(instruction: Event) -> Event:
    first_follower_move = (
        Event.select()
        .where(
            (Event.type == EventType.ACTION) & (Event.parent_event_id == instruction.id)
        )
        .order_by(Event.time)
        .first()
    )
    if first_follower_move is None:
        logger.info("No follower move found.")
        return None
    event_before = (
        Event.select()
        .where(
            (Event.game == first_follower_move)
            & (Event.time < first_follower_move.time)
        )
        .order_by(Event.time)
        .last()
    )
    return event_before


def eval_follower(
    coordinator: LocalGameCoordinator, agent: Agent, instruction: Event
) -> GameState:
    first_follower_move = (
        Event.select()
        .where(
            (Event.type == EventType.ACTION) & (Event.parent_event_id == instruction.id)
        )
        .order_by(Event.time)
        .first()
    )
    if first_follower_move is None:
        logger.info("No follower move found.")
        return None
    event_before = (
        Event.select()
        .where(
            (Event.game == first_follower_move)
            & (Event.time < first_follower_move.time)
        )
        .order_by(Event.time)
        .last()
    )
    ReconstructScenarioFromEvent(event_before.id)
    coordinator.CreateGameFromDatabase


def final_follower_move(instruction: Event) -> Event:
    last_follower_move = (
        Event.select()
        .where(
            (Event.type == EventType.ACTION) & (Event.parent_event_id == instruction.id)
        )
        .order_by(Event.time)
        .last()
    )
    # Get the event after this one.
    event_after = (
        Event.select()
        .where(
            (Event.game == last_follower_move.game)
            & (Event.time > last_follower_move.time)
        )
        .order_by(Event.time)
        .first()
    )
    return event_after


def CompareCardSelections(a: list[Card], b: list[Card]) -> bool:
    selected_ids_a = set([card.id for card in a if card.selected])
    selected_ids_b = set([card.id for card in b if card.selected])
    return selected_ids_a == selected_ids_b


def main(
    agent_config: str,
    server_config: str,
    eval_output: str = "./output.db",
    remote: bool = False,
    remote_address: str = None,
):
    agent_config = ReadAgentConfigOrDie(agent_config)
    config = ReadServerConfigOrDie(server_config)

    base.SetDatabase(config)
    base.ConnectDatabase()

    games = ListAnalysisGames(server_config)
    game_ids = [game.id for game in games]
    instructions = Event.select().where(
        (Event.type == EventType.INSTRUCTION_SENT)
        & (Event.lobby_name == LOBBY_NAME)
        & (Event.game_id << game_ids)
    )

    if instructions.count() == 0:
        print("No instructions found.")
        return

    if remote:
        print("Remote eval not yet supported.")
        return

    # Create an eval run entry in the database.
    eval_run = Eval(
        run_source=RunSource.LOCAL,
        client_hash=agent_config.client_hash,
        commit_version=GetCommitHash(),
    )

    # This object will help us launch local games.
    coordinator = LocalGameCoordinator(
        config,
        render_leader=True,
        render_follower=False,
    )

    eval_lobby = OpenLobby(
        LobbyInfo(
            name="eval virtual lobby",
            type=LobbyType.OPEN,
            comment="Ephemeral lobby used for eval runs.",
            game_capacity=1,
            sound_clip_volume=0,
        )
    )

    agent = CreateAgent(agent_config)
    for instruction in tqdm(instructions):
        if agent.role() == Role.LEADER:
            # Leader eval not yet supported.
            logger.info(f"Leader eval not yet supported.")
            return
        elif agent.role() == Role.FOLLOWER:
            eval_start_event = follower_eval_start(instruction)
            final_baseline_state = final_follower_move(instruction)

        # Create a local game to run the eval.
        if remote:
            logger.info(f"Remote eval not yet supported.")
            return
        else:
            game_name = coordinator.CreateGameFromDatabase(
                eval_start_event, log_to_db=log_to_db, lobby=eval_lobby
            )
            game_endpoint = coordinator.JoinSinglePlayerGame(game_name, agent.role())
            game_endpoint.Initialize()
            coordinator.StepGame(game_name)

        game_state = game_endpoint.initial_state()
        if game_state.turn_state.turn != agent.role():
            logger.error(
                f"Agent role {agent.role()} does not match turn eval run state {game_state.turn_state.turn}"
            )
            continue

        # Keep running until the current turn is over. We check for this inside
        # the loop because the game state may change in the middle of the loop.
        while not game_endpoint.over():
            # If the turn is over, then the eval for this instruction is done.
            if game_state.turn_state.turn != agent.role():
                break
            action = agent.choose_action(game_state)
            game_state = game_endpoint.step(action)

        # Now we have the agent's completed game state. We must compare it to
        # the baseline. Fetch the final game state after this instruction was
        # completed in the baseline game in the database.
        scenario = ReconstructScenarioFromEvent(final_baseline_state.id)
        final_baseline_state = GameStateFromScenario(scenario)

        # Compare the final game state to the human game state. See if the card
        # selections and scores match.
        final_agent_props = game_state.props
        final_agent_cards = [
            Card.FromProp(prop)
            for prop in final_agent_props
            if prop.prop_type == PropType.CARD
        ]
        final_baseline_props = final_baseline_state.props
        final_baseline_cards = [
            Card.FromProp(prop)
            for prop in final_baseline_props
            if prop.prop_type == PropType.CARD
        ]
        card_selections_match = CompareCardSelections(
            final_agent_cards, final_baseline_cards
        )
        if card_selections_match:
            # TODO finish eval...
            pass


if __name__ == "__main__":
    fire.Fire(main)
