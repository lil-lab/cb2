from server.schemas.game import *
from server.schemas.mturk import *
from peewee import *
import server.messages.map_update

import orjson

class MapUpdateField(TextField):
    def db_value(self, value):
        return orjson.dumps(value, option=orjson.OPT_NAIVE_UTC).decode('utf-8')
    
    def python_value(self, db_val):
        return server.messages.map_update.MapUpdate.from_json(db_val)

class MapUpdate(BaseModel):
    world_seed = TextField()
    map_data = MapUpdateField()
    game = ForeignKeyField(Game, backref='map_updates', null=True)
    map_update_number = IntegerField()
    time = DateTimeField(default=datetime.datetime.utcnow)