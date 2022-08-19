from peewee import *

from server.schemas.base import *
from server.schemas.game import *


class CardSets(BaseModel):
    game = ForeignKeyField(Game, backref='card_sets')
    move = ForeignKeyField(Move, backref='card_sets')
    score = IntegerField()

class Card(BaseModel):
    game = ForeignKeyField(Game, backref='cards')
    count = IntegerField()
    color = TextField()
    shape = TextField()
    location = HecsCoordField()
    set = ForeignKeyField(CardSets, backref='cards', null=True)
    turn_created = IntegerField()

class CardSelections(BaseModel):
    game = ForeignKeyField(Game, backref='card_selections')
    move = ForeignKeyField(Move, backref='card_selections')
    card = ForeignKeyField(Card, backref='card_selections')
    type = TextField() # "select" or "unselect"
    game_time = DateTimeField(default=datetime.datetime.utcnow)