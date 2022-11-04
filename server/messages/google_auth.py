from dataclasses import dataclass

from mashumaro.mixins.json import DataClassJSONMixin


@dataclass
class GoogleAuth(DataClassJSONMixin):
    token: str = ""


@dataclass
class GoogleAuthConfirmation(DataClassJSONMixin):
    success: bool = False
    user_name: str = ""
    user_id: int = -1
