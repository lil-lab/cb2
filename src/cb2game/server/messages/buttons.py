"""Game button presses.

CB2 doesn't stream all keyboard button presses from the client -- that would be
a privacy issue.

Instead, it only streams button presses that are relevant to the game state. For example, if the
client is in the lobby, it will not stream any button presses. If the client is in the game, it
will stream button presses that are relevant to the game state, such as Left/Right/Up/Down for
moving the player, or other keyboard shortcuts that are relevant to the game
(and not when the text box is selected).
"""

from dataclasses import dataclass
from enum import Enum

from mashumaro.mixins.json import DataClassJSONMixin

from cb2game.server.messages.util import Role


class KeyCode(Enum):
    NONE = 0
    LEFT = 1
    RIGHT = 2
    UP = 3
    DOWN = 4
    # The following are all keyboard shortcuts.
    C = 5  # Change camera view.
    T = 6  # Select text box for typing.
    N = 7  # End the turn.
    G = 8  # Positive feedback.
    B = 9  # Negative feedback.
    P = 10  # Show hecs coordinates in bottom right. Only works in scenario mode.
    # Usual gaming keys. In this case, A and D are used to steer the camera.
    # We include WASD for completeness.
    W = 14
    A = 15
    S = 16
    D = 17
    # These keys are just for completeness. Not necessarily implemented by the client.
    TAB = 11
    ESCAPE = 12
    ENTER = 13


class ButtonPressEvent(Enum):
    """The type of button press. The client currently only supports KEY_DOWN."""

    NONE = 0
    # May be simulated -- if a key is held down but triggers an underlying
    # event multiple times, then it's sent on the event. For example if you
    # hold down the "UP" key and your character moves 3 times, 3 UP
    # keydowns will be sent.
    KEY_DOWN = 1
    # Not implemented by client yet.
    KEY_UP = 2
    # Not implemented by client yet.
    HOLD = 3


@dataclass(frozen=True)
class ButtonPress(DataClassJSONMixin):
    """A button press from the client.

    A ButtonPress message is only sent if the button press is relevant to the game state.
    For example, if the client is in the lobby, it will not stream any button presses.
    If the client is in the game, it will stream button presses that are relevant to the game
    state, such as Left/Right/Up/Down for moving the player, or other keyboard shortcuts that are
    relevant to the game (and not when the text box is selected).
    If the button press is not relevant to the game state, the following fields will be None.

    Args:
        role: The role of the player that pressed the button.
        button_code: The button that was pressed.
    """

    role: Role
    button_code: KeyCode
    is_down: bool
    press_event: ButtonPressEvent
