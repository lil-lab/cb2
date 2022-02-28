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
from schemas.map import MapUpdate
from schemas import base
from config.config import Config

import fire
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

def draw_instruction(instruction, moves, map_update, filename):
    display = visualize.GameDisplay(SCREEN_SIZE)
    display.set_map(map_update)
    trajectory = [move.position_before for move in moves]
    if len (moves) > 0:
        final_position = HecsCoord.add(moves[-1].position_before, moves[-1].action.displacement)
        trajectory.append(final_position)
    display.set_trajectory(trajectory)
    display.draw()
    draw_wrapped(display, f'"{instruction.text}"')
    pygame.display.flip()
    pygame.image.save(display.screen(), filename)
    
# Attempts to parse the config file. If there's any parsing or file errors,
# doesn't handle the exceptions.
def ReadConfigOrDie(config_path):
    with open(config_path, 'r') as cfg_file:
        config = Config.from_json(cfg_file.read())
        return config

def main(from_id=119, to_id=139, max_instructions=-1, config_path="config/server-config.json", output_dir="output"):
    config = ReadConfigOrDie(config_path)

    print(f"Reading database from {config.database_path()}")
    # Setup the sqlite database used to record game actions.
    base.SetDatabase(config.database_path())
    base.ConnectDatabase()
    base.CreateTablesIfNotExists(schemas.defaults.ListDefaultTables())

    output_dir = pathlib.Path(output_dir).expanduser()
    # Create the directory if it doesn't exist.
    output_dir.mkdir(parents=False, exist_ok=True)

    instructions = Instruction.select().join(Game, join_type=peewee.JOIN.LEFT_OUTER).where(Game.id >= from_id, Game.id <= to_id)
    print(f"Found {instructions.count()} instructions.")
    words = set()
    instruction_list = []
    for instruction in instructions:
        for word in instruction.text.split(" "):
            words.add(word)
        instruction_list.append(instruction.text)
    print(f"Found {len(words)} unique words.")

    games = Game.select().where(Game.id >= from_id, Game.id <= to_id).order_by(Game.id)
    # For each game.
    for game in games:
        # Create a directory for the game.
        game_dir = (output_dir / str(game.id))
        game_dir.mkdir(parents=False, exist_ok=True)
        maps = MapUpdate.select().join(Game).where(MapUpdate.game == game)
        instructions = Instruction.select().join(Game).where(Instruction.game == game)
        for instruction in instructions:
            moves = Move.select().join(Game).where(Move.game == game, Move.instruction == instruction).order_by(Move.id)
            map = maps.where(MapUpdate.time <= instruction.time).order_by(MapUpdate.id.desc()).get()
            filepath = game_dir / f"instruction_vis_{instruction.id}.png"
            draw_instruction(instruction, moves, map.map_data, filepath)
            if max_instructions == 0:
                break
            max_instructions -= 1


if __name__ == "__main__":
    fire.Fire(main)