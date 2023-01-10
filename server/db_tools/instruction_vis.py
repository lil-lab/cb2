# Creates a set of graphics where an instruction is displayed on the left, and
# the follower's pathway is displayed on the right.
import json
import logging
import pathlib

import fire
import peewee
import pygame
import pygame.freetype

import server.config.config as config
import server.db_tools.db_utils as db_utils
import server.messages.live_feedback as live_feedback_msg
import server.messages.map_update as map_update_msg
import server.messages.prop as prop_msg
import server.schemas.defaults as defaults_db
from server.card import Card
from server.hex import HecsCoord
from server.map_tools import visualize
from server.messages.action import Action
from server.messages.objective import ObjectiveMessage
from server.schemas import base
from server.schemas.event import Event, EventType

pygame.freetype.init()
INSTRUCTION_FONT = pygame.freetype.SysFont("Times New Roman", 30)

# The below imports are used to import pygame in a headless setup, to render map
# updates as images for game recordings.
import os

# set SDL to use the dummy NULL video driver,
#   so it doesn't need a windowing system.
os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame.transform

if 1:
    # some platforms might need to init the display for some parts of pygame.
    import pygame.display

    pygame.display.init()
    screen = pygame.display.set_mode((1, 1))

SCREEN_SIZE = 800


def draw_wrapped(display, instruction_text, max_width=50):
    words = instruction_text.split(" ")
    lines = []
    current_line = ""
    for word in words:
        if len(current_line) + len(word) > max_width:
            lines.append(current_line)
            current_line = word
        else:
            current_line += " " + word
    lines.append(current_line)
    for i, line in enumerate(lines):
        (line_text, _) = INSTRUCTION_FONT.render(line, pygame.Color(90, 90, 90))
        display._screen.blit(
            line_text,
            (
                SCREEN_SIZE * 0.5 - line_text.get_width() / 2,
                SCREEN_SIZE * 0.75 + i * 30,
            ),
        )


def draw_instruction(
    instruction, moves, feedbacks, map_update, filename, game_id, props
):
    display = visualize.GameDisplay(SCREEN_SIZE)
    display.set_map(map_update)
    display.set_props(props)
    trajectory = [(move.location, move.orientation) for move in moves]
    if len(moves) > 0:
        first_action = Action.from_json(moves[-1].data)
        final_position = HecsCoord.add(moves[-1].location, first_action.displacement)
        final_orientation = moves[-1].orientation + first_action.rotation
        trajectory.append((final_position, final_orientation))
    display.set_trajectory(trajectory)
    positive_markers = []
    negative_markers = []
    for event in feedbacks:
        feedback_obj = live_feedback_msg.LiveFeedback.from_json(event.data)
        if feedback_obj.signal == live_feedback_msg.FeedbackType.POSITIVE:
            positive_markers.append((event.location, event.orientation))
        elif feedback_obj.signal == live_feedback_msg.FeedbackType.NEGATIVE:
            negative_markers.append((event.location, event.orientation))
        else:
            print(f"Ignoring unknown feedback type: {feedback_obj.signal}")
            print(f"Original data: {event.data}")
    display.set_positive_markers(positive_markers)
    display.set_negative_markers(negative_markers)
    display.draw()
    draw_wrapped(display, f'"{instruction.text}"')

    # Draw the game ID in the bottom left corner.
    (text, _) = INSTRUCTION_FONT.render(f"Game {game_id}", pygame.Color(120, 120, 120))
    display._screen.blit(
        text, (SCREEN_SIZE * 0.5 - text.get_width() / 2, SCREEN_SIZE * 0.90)
    )

    pygame.display.flip()
    pygame.image.save(display.screen(), filename)


def main(
    max_instructions=-1,
    config_filepath="config/server-config.json",
    output_dir="output",
    research_only=True,
):
    logging.basicConfig(level=logging.INFO)
    cfg = config.ReadConfigOrDie(config_filepath)

    print(f"Reading database from {cfg.database_path()}")
    # Setup the sqlite database used to record game actions.
    base.SetDatabase(cfg)
    base.ConnectDatabase()
    base.CreateTablesIfNotExists(defaults_db.ListDefaultTables())

    output_dir = pathlib.Path(output_dir).expanduser()
    # Create the directory if it doesn't exist.
    output_dir.mkdir(parents=False, exist_ok=True)

    words = set()
    instruction_list = []

    if research_only:
        games = db_utils.ListAnalysisGames(cfg)
    else:
        games = [
            game for game in db_utils.ListGames() if db_utils.IsConfigGame(cfg, game)
        ]
    print(f"Found {len(games)} games.")
    ParentEvent = Event.alias()
    # For each game.
    for game in games:
        # Create a directory for the game.
        game_dir = output_dir / str(game.id)
        game_dir.mkdir(parents=False, exist_ok=True)
        # Do a self-join to link parent events. ParentEvent is an alias of Event defined above.
        game_events = (
            Event.select()
            .join(
                ParentEvent,
                peewee.JOIN.LEFT_OUTER,
                on=(Event.parent_event == ParentEvent.id),
            )
            .where(Event.game_id == game.id)
            .order_by(Event.server_time)
        )
        map_events = (
            game_events.select()
            .where(Event.type == EventType.MAP_UPDATE)
            .order_by(Event.server_time)
        )
        if map_events.count() == 0:
            print(f"Skipping game {game.id} because it has no map update events.")
            continue
        prop_updates = game_events.where(Event.type == EventType.PROP_UPDATE).order_by(
            Event.server_time
        )
        if not prop_updates.exists():
            print(f"Skipping game {game.id} because it has no prop update events.")
            continue
        first_map_update = map_update_msg.MapUpdate.from_json(map_events.get().data)
        first_prop_update = prop_msg.PropUpdate.from_json(prop_updates.get().data)
        initial_cards = [Card.FromProp(prop) for prop in first_prop_update.props]
        instructions = game_events.where(Event.type == EventType.INSTRUCTION_SENT)
        for instruction in instructions:
            activation_query = instruction.children.where(
                Event.type == EventType.INSTRUCTION_ACTIVATED
            )
            if not activation_query.exists():
                print(
                    f"Skipping instruction {instruction.id} because it was never activated."
                )
                continue
            activation = activation_query.get()

            cards_by_location = {card.location: card for card in initial_cards}
            card_events = game_events.where(
                Event.type
                << [
                    EventType.CARD_SPAWN,
                    EventType.CARD_SET,
                    Event.server_time <= activation.server_time,
                ]
            ).order_by(Event.server_time)
            for event in card_events:
                if event.type == EventType.CARD_SPAWN:
                    card = Card.from_json(event.data)
                    cards_by_location[card.location] = card
                elif event.type == EventType.CARD_SET:
                    data_obj = json.loads(event.data)
                    cards = [Card.from_dict(card) for card in data_obj["cards"]]
                    for card in cards:
                        cards_by_location[card.location] = None
            props = [
                card.prop() for card in cards_by_location.values() if card is not None
            ]

            moves = instruction.children.where(Event.type == EventType.ACTION)
            feedbacks = (
                game_events.select()
                .where(
                    Event.parent_event << moves, Event.type == EventType.LIVE_FEEDBACK
                )
                .order_by(Event.server_time)
            )

            dt_string = instruction.server_time.strftime("%Y-%m-%d_%H-%M-%S")
            filepath = game_dir / f"instruction_vis_{dt_string}.png"
            instruction_obj = ObjectiveMessage.from_json(instruction.data)
            draw_instruction(
                instruction_obj,
                moves,
                feedbacks,
                first_map_update,
                filepath,
                game.id,
                props,
            )
            instruction_list.append(instruction_obj.text)
            for word in instruction_obj.text.split(" "):
                words.add(word)
            if max_instructions == 0:
                break
            max_instructions -= 1

    # print how many instructions and unique words there are.
    print(f"{len(instruction_list)} instructions")
    print(f"{len(words)} unique words")


if __name__ == "__main__":
    fire.Fire(main)
