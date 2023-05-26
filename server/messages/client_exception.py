"""Extension of BugReport for uploading exceptions from the client."""

from dataclasses import dataclass

from mashumaro.mixins.json import DataClassJSONMixin

from server.messages.bug_report import BugReport


@dataclass(frozen=True)
class ClientException(DataClassJSONMixin):
    bug_report: BugReport
    condition: str
    stack_trace: str
    game_id: str
    role: str
    type: str
