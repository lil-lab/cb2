# Creates a set of graphics where an instruction is displayed on the left, and
# the follower's pathway is displayed on the right.
from map_tools import visualize
from playhouse.sqlite_ext import CSqliteExtDatabase
import peewee
import schemas.defaults
import schemas.game

from hex import HecsCoord
from schemas.game import Turn
from schemas.game import Game
from schemas.game import Instruction
from schemas.game import Move
from schemas.game import LiveFeedback
from schemas.map import MapUpdate
from schemas import base
from config.config import Config

import db_tools.db_utils as db_utils
import config.config as config

import fire
import itertools
import pathlib
import random
import pygame
import pygame.freetype

pygame.freetype.init()
INSTRUCTION_FONT = pygame.freetype.SysFont('Times New Roman', 30)

# The below imports are used to import pygame in a headless setup, to render map
# updates as images for game recordings.
import os, sys
# set SDL to use the dummy NULL video driver, 
#   so it doesn't need a windowing system.
os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame.transform
if 1:
    #some platforms might need to init the display for some parts of pygame.
    import pygame.display
    pygame.display.init()
    screen = pygame.display.set_mode((1,1))

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
        display._screen.blit(line_text, (SCREEN_SIZE * 0.5 - line_text.get_width() / 2, SCREEN_SIZE * 0.75 + i * 30))

def draw_instruction(instruction, moves, feedbacks, map_update, filename, game_id):
    display = visualize.GameDisplay(SCREEN_SIZE)
    display.set_map(map_update)
    trajectory = [(move.position_before, move.orientation_before) for move in moves]
    if len (moves) > 0:
        final_position = HecsCoord.add(moves[-1].position_before, moves[-1].action.displacement)
        final_orientation = moves[-1].orientation_before + moves[-1].action.rotation
        trajectory.append((final_position, final_orientation))
    display.set_trajectory(trajectory)
    positive_markers = []
    negative_markers = []
    for feedback in feedbacks:
        if feedback.feedback_type == "POSITIVE":
            positive_markers.append((feedback.follower_position, feedback.follower_orientation))
        elif feedback.feedback_type == "NEGATIVE":
            negative_markers.append((feedback.follower_position, feedback.follower_orientation))
        else:
            print(f"Ignoring unknown feedback type: {feedback.feedback_type}")
    display.set_positive_markers(positive_markers)
    display.set_negative_markers(negative_markers)
    display.draw()
    draw_wrapped(display, f'"{instruction.text}"')

    # Draw the game ID in the bottom left corner.
    (text, _) = INSTRUCTION_FONT.render(f"Game {game_id}", pygame.Color(120, 120, 120))
    display._screen.blit(text, (SCREEN_SIZE * 0.5 - text.get_width() / 2, SCREEN_SIZE * 0.90))

    pygame.display.flip()
    pygame.image.save(display.screen(), filename)
    
def main(max_instructions=-1, config_filepath="config/server-config.json", output_dir="output"):
    cfg = config.ReadConfigOrDie(config_filepath)

    print(f"Reading database from {cfg.database_path()}")
    # Setup the sqlite database used to record game actions.
    base.SetDatabase(cfg.database_path())
    base.ConnectDatabase()
    base.CreateTablesIfNotExists(schemas.defaults.ListDefaultTables())

    output_dir = pathlib.Path(output_dir).expanduser()
    # Create the directory if it doesn't exist.
    output_dir.mkdir(parents=False, exist_ok=True)

    words = set()
    instruction_list = []

    games = db_utils.ListMturkGames()
    if len(cfg.analysis_game_id_ranges) > 0:
        valid_ids = set(itertools.chain(*[range(x, y) for x,y in cfg.analysis_game_id_ranges]))
        games = games.select().where(Game.id.in_(valid_ids))
        print(f"Filtering to games {valid_ids}")
        print(f"{games.count()} games remaining")
    # For each game.
    for game in games:
        # Create a directory for the game.
        game_dir = (output_dir / str(game.id))
        game_dir.mkdir(parents=False, exist_ok=True)
        maps = MapUpdate.select().join(Game).where(MapUpdate.game == game)
        instructions = Instruction.select().join(Game).where(Instruction.game == game)
        for instruction in instructions:
            moves = Move.select().join(Game).where(Move.game == game, Move.instruction == instruction).order_by(Move.id)
            feedbacks = LiveFeedback.select().join(Game).where(LiveFeedback.game == game, LiveFeedback.instruction == instruction).order_by(LiveFeedback.id)
            map = maps.where(MapUpdate.time <= instruction.time).order_by(MapUpdate.id.desc()).get()
            filepath = game_dir / f"instruction_vis_{instruction.id}.png"
            draw_instruction(instruction, moves, feedbacks, map.map_data, filepath, game.id)
            instruction_list.append(instruction.text)
            for word in instruction.text.split(" "):
                words.add(word)
            if max_instructions == 0:
                break
            max_instructions -= 1

    # print how many instructions and unique words there are.
    print(f"{len(instruction_list)} instructions")
    print(f"{len(words)} unique words")


if __name__ == "__main__":
    fire.Fire(main)
