from schemas.base import *
from schemas.cards import *
from schemas.clients import *
from schemas.game import *
from schemas.map import *
from schemas.mturk import *
from schemas.leaderboard import *
from schemas.prop import *

TABLES = [
    CardSets, Card, CardSelections,
    Remote, ConnectionEvents,
    Game, Turn, Instruction, Move, LiveFeedback,
    MapUpdate, PropUpdate,
    Worker, Assignment, WorkerExperience,
    Leaderboard, Username
]

def ListDefaultTables():
    return TABLES