from dataclasses import dataclass
from enum import IntEnum

from mashumaro.mixins.json import DataClassJSONMixin


class UserType(IntEnum):
    NONE = 0
    MTURK = 1
    OPEN = 2
    GOOGLE = 3
    BOT = 4


@dataclass(frozen=True)
class UserInfo(DataClassJSONMixin):
    user_name: str = ""
    user_type: UserType = UserType.NONE
