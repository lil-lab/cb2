""" A set of general utilities that are used across the server. """

import contextvars
import functools
import pathlib
import subprocess
import sys
import time
import traceback
from asyncio import events
from datetime import datetime, timedelta
from typing import List

import git
import orjson

MAX_ID = 1000000

# Constants which determine server behavior.
HEARTBEAT_TIMEOUT_S = 20.0


def JsonSerialize(x, pretty=True):
    options = orjson.OPT_NAIVE_UTC | orjson.OPT_PASSTHROUGH_DATETIME
    if pretty:
        options |= orjson.OPT_INDENT_2
    object_dumper = lambda x: orjson.dumps(
        x,
        option=options,
        default=datetime.isoformat,
    ).decode("utf-8")
    return object_dumper(x)


class IdAssigner(object):
    def __init__(self):
        self._last_id = 0

    def alloc(self):
        # Note... you can do better via a BST of tuples of unallocated values.
        if self._last_id >= MAX_ID:
            return -1

        id = self._last_id
        self._last_id += 1
        return id

    def free(self, id):
        pass

    def num_allocated(self):
        return self._last_id


def SafePasswordCompare(a, b):
    """Compares two passwords. Resistant to timing attacks."""
    if len(a) != len(b):
        return False
    return all(x == y for x, y in zip(a, b))


def GetCommitHash():
    """Returns the git commit hash of the system software.
    Use __file__ to get the path to the git repo.
    """
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=pathlib.Path(__file__).parent
            )
            .decode("utf-8")
            .strip()
        )
    except subprocess.CalledProcessError:
        # This is the more cross platform way.
        repo = git.Repo(pathlib.Path(__file__).parent.parent)
        return repo.head.object.hexsha


class CountDownTimer(object):
    """A timer used to track if a certain duration has elapsed.

    Pass in a duration in seconds. Call start() to start the timer.
    Call expired() to check if the timer has expired.
    clear() stops the timer, resetting all state. If the timer is not
    started, expired() will return False.

    """

    def __init__(self, duration_s: float = 0):
        self._duration_s = duration_s
        self._end_time = None
        self._remaining_duration_s = None

    def start(self):
        """Starts the timer. Does nothing if the timer is already started"""
        if self._end_time is not None:
            return
        if self._remaining_duration_s is None:
            self._end_time = time.time() + self._duration_s
            return
        self._end_time = time.time() + self._remaining_duration_s

    def pause(self):
        """Pauses the timer -- stores the currently elapsed time in _base_elapsed and sets _end_time to None."""
        if self._end_time is not None:
            self._remaining_duration_s = self._end_time - time.time()
        self._end_time = None

    def clear(self):
        """Stops the timer. Resets all state."""
        self._end_time = None
        self._remaining_duration_s = None

    def time_remaining(self):
        """Returns the remaining time. If the timer is not started, returns 0."""
        if self._end_time is None:
            return timedelta(seconds=0)
        return timedelta(seconds=(self._end_time - time.time()))

    def expired(self):
        """Returns true if the timer has expired."""
        if self._end_time is None:
            return False
        return time.time() > self._end_time


# Btw, everything in class LatencyMonitor (including the class and method
# docstring comments) was written by ChatGPT. It took about 10-15 minutes of
# interactive code review between me and ChatGPT to get to this point. Amazing!
# ChatGPT also wrote the unit tests, however some extensive handholding and
# human editing was needed there.
class LatencyMonitor(object):
    """
    A class for monitoring and aggregating latency data.

    Latency data is accumulated into buckets of fixed duration. The total latency for each
    bucket is recorded and can be retrieved as a time series.
    """

    def __init__(self, bucket_size_s: float = 60.0):
        self.bucket_size_s = bucket_size_s
        self.buckets = []
        self.current_bucket = 0.0
        self.last_bucket_time = time.time()

    def accumulate_latency(self, latency_s: float):
        """
        Adds the specified latency (in seconds) to the current bucket. If the current bucket
        duration has been exceeded, save it to history and start accumulating in a new bucket.
        """
        current_time = time.time()
        elapsed_time = current_time - self.last_bucket_time

        if elapsed_time >= self.bucket_size_s:
            self.buckets.append((self.current_bucket, self.last_bucket_time))
            self.current_bucket = 0.0
            self.last_bucket_time = current_time

        self.current_bucket += latency_s

    def bucket_latencies(self) -> List[float]:
        """
        Returns a list of the total latency (in seconds) for each bucket.
        """
        return [bucket[0] for bucket in self.buckets]

    def bucket_timestamps(self) -> List[float]:
        """
        Returns a list of the timestamps (in seconds since the epoch) for each bucket.
        """
        return [bucket[1] for bucket in self.buckets]


# Asyncio.to_thread is a feature of python 3.9, however, we are using python 3.8
# This is a backport of the function from python 3.9.
async def to_thread(func, /, *args, **kwargs):
    """Asynchronously run function *func* in a separate thread.
    Any *args and **kwargs supplied for this function are directly passed
    to *func*. Also, the current :class:`contextvars.Context` is propagated,
    allowing context variables from the main thread to be accessed in the
    separate thread.
    Return a coroutine that can be awaited to get the eventual result of *func*.
    """
    loop = events.get_running_loop()
    ctx = contextvars.copy_context()
    func_call = functools.partial(ctx.run, func, *args, **kwargs)
    return await loop.run_in_executor(None, func_call)


def exc_info_plus():
    """
    Print the usual traceback information, followed by a listing of all the
    local variables in each frame.
    Shamelessly taken from oreilly and modified.
    """
    output = ""
    tb = sys.exc_info()[2]
    while 1:
        if not tb.tb_next:
            break
        tb = tb.tb_next
    stack = []
    f = tb.tb_frame
    while f:
        stack.append(f)
        f = f.f_back
    stack.reverse()
    output += traceback.format_exc()
    output += "Locals by frame, innermost last\n"
    for frame in stack:
        output += "\n"
        output += "Frame %s in %s at line %s\n" % (
            frame.f_code.co_name,
            frame.f_code.co_filename,
            frame.f_lineno,
        )
        for key, value in frame.f_locals.items():
            output += "\t%20s = " % key
            # We have to be VERY careful not to cause a new error in our error
            # printer! Calling str(  ) on an unknown object could cause an
            # error we don't want, so we must use try/except to catch it --
            # we can't stop it from happening, but we can and should
            # stop it from propagating if it does happen!
            try:
                output += value
            except:
                output += "<ERROR WHILE PRINTING VALUE>"
    return output
