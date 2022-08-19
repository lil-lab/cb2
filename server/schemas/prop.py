from server.schemas.game import *
from server.schemas.mturk import *
from peewee import *
import server.messages.prop

import orjson

class PropUpdateField(TextField):
    def db_value(self, value):
        return orjson.dumps(value, option=orjson.OPT_NAIVE_UTC).decode('utf-8')
    
    def python_value(self, db_val):
        return server.messages.prop.PropUpdate.from_json(db_val)

class PropUpdate(BaseModel):
    prop_data = PropUpdateField()
    game = ForeignKeyField(Game, backref='prop_updates', null=True)
    time = DateTimeField(default=datetime.datetime.utcnow)