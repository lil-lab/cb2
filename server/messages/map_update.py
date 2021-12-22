from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from datetime import datetime
from hex import HexCell, HecsCoord
from marshmallow import fields
from typing import List

import datetime
import dateutil.parser
import typing
import messages.prop


@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class Tile:
    asset_id: int
    cell: HexCell
    rotation_degrees: int


@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class MapUpdate:
    rows: int
    cols: int
    tiles: List[Tile]
    props: List[messages.prop.Prop]
