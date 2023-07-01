from dataclasses import dataclass

from mashumaro.mixins.json import DataClassJSONMixin


@dataclass(frozen=True)
class GoogleAuth(DataClassJSONMixin):
    token: str = ""


@dataclass(frozen=True)
class GoogleAuthConfirmation(DataClassJSONMixin):
    success: bool = False
    user_name: str = ""
    user_id: int = -1
