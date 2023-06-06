from server.schemas.base import *
from server.schemas.cards import *
from server.schemas.client_exception import *
from server.schemas.clients import *
from server.schemas.eval import *
from server.schemas.event import *
from server.schemas.game import *
from server.schemas.google_user import *
from server.schemas.leaderboard import *
from server.schemas.map import *
from server.schemas.mturk import *
from server.schemas.prop import *

TABLES = [
    CardSets,
    Card,
    CardSelections,
    Remote,
    ConnectionEvents,
    Game,
    Turn,
    Instruction,
    Move,
    LiveFeedback,
    InitialState,
    MapUpdate,
    PropUpdate,
    Worker,
    Assignment,
    WorkerExperience,
    Leaderboard,
    Username,
    GoogleUser,
    Event,
    ClientException,
]

EVAL_TABLES = [Eval, InstructionEvaluation]


def ListDefaultTables():
    return TABLES


def ListEvalTables():
    return EVAL_TABLES
