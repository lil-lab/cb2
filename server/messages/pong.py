from dataclasses import dataclass

from mashumaro.mixins.json import DataClassJSONMixin


@dataclass(frozen=True)
class Pong(DataClassJSONMixin):
    ping_receive_time: str = ""
