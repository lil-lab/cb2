from dataclasses import dataclass

from mashumaro.mixins.json import DataClassJSONMixin

from server.messages.rooms import Role


@dataclass
class ObjectiveMessage(DataClassJSONMixin):
    sender: Role = Role.NONE
    text: str = ""
    uuid: str = ""
    completed: bool = False
    cancelled: bool = False
    feedback_text: str = ""
    pos_feedback: int = 0
    neg_feedback: int = 0

    def update_feedback_text(self):
        """Helper to fully populate ObjectiveMessage.

        This function uses the pos_feedback and neg_feedback integer fields of
        ObjectiveMessage to populate the feedback_text field with a summary of
        the feedback.

        Renders the pos and neg feedback into a string using thumbs up/down emoji:

        <pos_feedback> 👍 <neg_feedback> 👎

        For now, we use unicode characters ✔✘ instead of emoji. This is because
        the emoji are not supported in the version of unity currently used.
        """
        pos = self.pos_feedback
        neg = self.neg_feedback
        if pos == 0 and neg == 0:
            self.feedback_text = ""
            return
        self.feedback_text = f"Feedback: {pos} Positive, {neg} Negative"


@dataclass(frozen=True)
class ObjectiveCompleteMessage(DataClassJSONMixin):
    uuid: str = ""
