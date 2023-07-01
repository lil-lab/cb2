from cb2game.server.schemas.base import *
from cb2game.server.schemas.cards import *
from cb2game.server.schemas.client_exception import *
from cb2game.server.schemas.clients import *
from cb2game.server.schemas.event import *
from cb2game.server.schemas.game import *
from cb2game.server.schemas.google_user import *
from cb2game.server.schemas.leaderboard import *
from cb2game.server.schemas.map import *
from cb2game.server.schemas.mturk import *
from cb2game.server.schemas.prop import *

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


def ListDefaultTables():
    return TABLES
