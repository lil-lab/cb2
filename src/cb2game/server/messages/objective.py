from dataclasses import dataclass

from mashumaro.mixins.json import DataClassJSONMixin

from cb2game.server.messages.rooms import Role


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

        Renders the pos and neg feedback into a string using thumbs up/down signs like:

        <pos_feedback> 👍 <neg_feedback> 👎

        For now, we use a Unity sprite map instead of emoji. This is because
        the emoji don't seem to be well supported. The sprite map is stored in
        game/Assets/Resources/text_sprites and has two entities: thumbs_up and
        thumbs_down (index 1 and index 0, respectively).
        """
        pos = self.pos_feedback
        neg = self.neg_feedback
        if pos == 0 and neg == 0:
            self.feedback_text = ""
            return
        self.feedback_text = f"{pos} <sprite index=1> {neg} <sprite index=0>"


@dataclass(frozen=True)
class ObjectiveCompleteMessage(DataClassJSONMixin):
    uuid: str = ""
