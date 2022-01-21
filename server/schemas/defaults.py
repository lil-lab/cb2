from schemas.base import *
from schemas.cards import *
from schemas.clients import *
from schemas.game import *
from schemas.map import *
from schemas.mturk import *
from schemas.tutorial import *

TABLES = [
    CardSets, Card, CardSelections,
    Remote, ConnectionEvents,
    Game, Turn, Instruction, Move,
    Map,
    Worker, Assignment,
    FollowerTutorial, LeaderTutorial,
]

def ListDefaultTables():
    return TABLES