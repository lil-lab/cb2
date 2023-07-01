""" Run on an eval to generate graphics visualizing the result of each instruction. """

import pygame
import pygame.freetype
from tqdm import tqdm

from cb2game.server.schemas import base
from cb2game.server.schemas.eval import Eval

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


def main(eval_db: str, eval_id, server_config: str, output_dir: str = ""):
    base.SetDatabase(eval_db)
    base.ConnectDatabase()

    # Load all instructions
    eval = Eval.get(Eval.id == eval_id)
    instructions = eval.events

    for instruction in tqdm(instructions):
        ...
