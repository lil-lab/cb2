from schemas.game import *
from schemas.mturk import *
from peewee import *
from messages.map_update import MapUpdate

class MapUpdateField(Field):
    field_type = 'map'

    def db_value(self, value):
        value.to_json()
    
    def python_value(self, db_val):
        return MapUpdate.from_json(db_val)

class Map(BaseModel):
    world_seed = TextField()
    map_data = MapUpdateField()
    game = ForeignKeyField(Game, backref='map_updates')
    map_update_number = IntegerField()
    time = DateTimeField()