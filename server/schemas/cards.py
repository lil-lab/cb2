from peewee import *

from schemas.base import *
from schemas.game import *


class CardSets(BaseModel):
    game = ForeignKeyField(Game, backref='card_sets')
    move = ForeignKeyField(Move, backref='card_sets')
    score = IntegerField()

class Card(BaseModel):
    count = IntegerField()
    color = TextField()
    shape = TextField()
    location = HecsCoordField()
    result = TextField()
    sets = ForeignKeyField(CardSets, backref='cards')

class CardSelections(BaseModel):
    game = ForeignKeyField(Game, backref='card_selections')
    move = ForeignKeyField(Move, backref='card_selections')
    card = ForeignKeyField(Card, backref='card_selections')
    game_time = DateTimeField()