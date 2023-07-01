""" This file defines the Eval run schema, which is used to store the results of
    an evaluation run.

    Evals can either be remote or local. Each eval is associated with a run
    source, to know if it was run locally or remotely.

    Each eval is a list of scenarios, which are stored in the Game table. Although
    an eval can consist of many different scenarios within the same game, we
    evaluate each as a separate scenario game.

    We anticipate many eval runs, and eval runs are resource intensive. Firstly,
    evals may require many calls to the GPT API or use of a GPU. Secondly, eval
    outputs must be saved to disk, and this takes up disk space. To mitigate this,
    we default to local eval runs, and only run remote evals when specified.
"""
import datetime
import uuid
from dataclasses import dataclass, field
from enum import IntEnum
from typing import List

from mashumaro.config import BaseConfig
from mashumaro.mixins.json import DataClassJSONMixin

from cb2game.server.messages.rooms import Role
from cb2game.server.util import GetCommitHash


class RunSource(IntEnum):
    """
    Enum for the source of the eval run.

    Right now, we only support local eval.
    """

    NONE = 0
    LOCAL = 1
    REMOTE = 2


@dataclass
class InstructionEvaluation(DataClassJSONMixin):
    """An eval run consists of many instructions which are evaluated.

    Each entry in this table represents the results of evaluating a single
    instruction.
    """

    # UUID of the event from which eval started. For example if it was
    # a follower eval, it's the event before the follower's first move for this
    # instruction. The leader might have made subsequent moves during their
    # turn, so the board state might have changed.
    instruction_uuid: str
    # Comma-separated list of actions agent took to complete the instruction.
    agent_actions: str
    # UUID of the exact event where evaluation began. This is likely the event
    # where the instruction was activated (though in some cases, it might be
    # when the follower turn started, if the instruction activated during the
    # leader's turn. Say if it was the first instruction sent).
    event_uuid: str
    # Whether or not the evaluation is considered successful.
    success: bool
    # If an error occurred during evaluation, this is the error message.
    # If no error occurred, this is an empty string.
    error: str = ""


@dataclass
class Eval(DataClassJSONMixin):
    """
    Eval result record.

    Each eval is given a unique UUID. Evals are tagged with local commit
    version and the date, to help recreate the environment in which the
    eval was run. We also store the agent configuration that was used to
    run the eval.

    An evaluation consists of running an agent against a number of
    instructions, demarcated by their event UUID. For accessing evaluation
    results, see InstructionEvaluation."""

    class Config(BaseConfig):
        debug = False

    id: str = uuid.uuid4().hex
    run_source: RunSource = RunSource.NONE
    commit_version: str = GetCommitHash()
    run_date: datetime.datetime = datetime.datetime.utcnow()
    agent_name: str = ""
    agent_type: str = "NONE"
    agent_config: str = "{}"
    agent_role: Role = (Role.NONE,)
    server_config: str = "{}"
    percent_passed: float = float(0)
    total_instructions = 0
    instruction_evals: List[InstructionEvaluation] = field(default_factory=list)
