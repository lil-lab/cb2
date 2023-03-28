from dataclasses import dataclass, field
from enum import Enum

from mashumaro.mixins.json import DataClassJSONMixin


# Must keep in sync with C# SoundClipType enum in game/Assets/Scripts/Network/Messages/SoundTrigger.cs
class SoundClipType(Enum):
    NONE = 0
    INSTRUCTION_RECEIVED = 1
    INSTRUCTION_SENT = 2
    INVALID_SET = 3
    NEGATIVE_FEEDBACK = 4
    POSITIVE_FEEDBACK = 5
    VALID_SET = 6
    # Add more sound clip types here as needed


@dataclass(frozen=True)
class SoundTrigger(DataClassJSONMixin):
    sound_clip: SoundClipType = SoundClipType.NONE
    volume: float = field(default=1.0)  # Range: 0.0 (mute) to 1.0 (loudest)


def SoundTriggerFromType(sound_clip_type, volume=1.0):
    return SoundTrigger(sound_clip_type, volume)
