from dataclasses import dataclass
from typing import List

from mashumaro.mixins.json import DataClassJSONMixin

from cb2game.server.hex import HecsCoord
from cb2game.server.messages.rooms import Role


@dataclass(frozen=True)
class Actor(DataClassJSONMixin):
    actor_id: int
    asset_id: int
    location: HecsCoord
    rotation_degrees: float
    actor_role: Role


@dataclass(frozen=True)
class StateSync(DataClassJSONMixin):
    population: int
    actors: List[Actor]
    player_id: int = -1
    player_role: Role = Role.NONE


# This message indicates that the state machine has "processed" a single
# iteration of the state update loop. This is used to group together messages
# for simultaneous events. For example, if a player moves forwards and then that
# move causes a card to be selected, it'll result in two messages: one for the
# move and one for the card selection. Humans will see them simultaneously so
# its not important, but bot players won't know if the two are part of 1 update
# loop. So between each logic iteration, we send this message with an
# incrementing iteration ID. Note that it does not get sent if no updates were
# made (to save bandwidth).
@dataclass(frozen=True)
class StateMachineTick(DataClassJSONMixin):
    iter: int = -1  # Increments each frame. Rolls over at 2**32. This should be safe.
