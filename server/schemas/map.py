from schemas.game import *
from schemas.mturk import *
from peewee import *
import messages.map_update

class MapUpdateField(TextField):
    def db_value(self, value):
        return value.to_json()
    
    def python_value(self, db_val):
        return messages.map_update.MapUpdate.from_json(db_val)

class MapUpdate(BaseModel):
    world_seed = TextField()
    map_data = MapUpdateField()
    game = ForeignKeyField(Game, backref='map_updates', null=True)
    map_update_number = IntegerField()
    time = DateTimeField(default=datetime.datetime.now)