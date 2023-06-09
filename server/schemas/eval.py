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
from enum import IntEnum

from peewee import (
    BooleanField,
    DateTimeField,
    ForeignKeyField,
    IntegerField,
    TextField,
    UUIDField,
)

from server.schemas.base import BaseModel


class RunSource(IntEnum):
    """
    Enum for the source of the eval run.
    """

    NONE = 0
    LOCAL = 1
    REMOTE = 2


class Eval(BaseModel):
    """
    Eval result record.

    Each eval is given a unique UUID. Evals are tagged with local commit
    version and the date, to help recreate the environment in which the
    eval was run. We also store the agent configuration that was used to
    run the eval.

    An evaluation consists of running an agent against a number of
    instructions, demarcated by their event UUID. For accessing evaluation
    results, see InstructionEvaluation."""

    id = UUIDField(primary_key=True, default=uuid.uuid4, unique=True)
    run_source = IntegerField(default=RunSource.NONE)
    client_hash = TextField()
    commit_version = TextField()
    run_date = DateTimeField(default=datetime.datetime.now)
    agent_config = TextField()
    agent_role = TextField()  # 'LEADER' or 'FOLLOWER'.
    server_config = TextField()


class InstructionEvaluation(BaseModel):
    """An eval run consists of many instructions which are evaluated.

    Each entry in this table represents the results of evaluating a single
    instruction.
    """

    id = UUIDField(primary_key=True, default=uuid.uuid4, unique=True)
    eval_run = ForeignKeyField(Eval, backref="events")
    # UUID of the event from which eval started. For example if it was
    # a follower eval, it's the event before the follower's first move for this
    # instruction. The leader might have made subsequent moves during their
    # turn, so the board state might have changed.
    instruction_uuid = TextField()
    instruction_text = TextField()
    # Comma-separated list of actions agent took to complete the instruction.
    agent_actions = TextField()
    event_uuid = TextField()
    # A serialized GameState struct.
    agent_outcome = TextField()
    # A serialized GameState struct.
    baseline_outcome = TextField()
    # Whether or not the evaluation is considered successful.
    success = BooleanField()
