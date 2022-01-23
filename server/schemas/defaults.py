from schemas.base import *
from schemas.cards import *
from schemas.clients import *
from schemas.game import *
from schemas.map import *
from schemas.mturk import *

TABLES = [
    CardSets, Card, CardSelections,
    Remote, ConnectionEvents,
    Game, Turn, Instruction, Move,
    MapUpdate,
    Worker, Assignment,
]

def ListDefaultTables():
    return TABLES