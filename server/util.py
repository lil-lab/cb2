""" A set of general utilities that are used across the server. """

import pathlib
import subprocess
import time

MAX_ID = 1000000


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
    return (
        subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=pathlib.Path(__file__).parent
        )
        .decode("utf-8")
        .strip()
    )


class CountDownTimer(object):
    """A timer used to track if a certain duration has elapsed.

    Pass in a duration in seconds. Call start() to start the timer.
    Call expired() to check if the timer has expired.
    clear() stops the timer, resetting all state. If the timer is not
    started, expired() will return False.

    """

    def __init__(self, duration_s: float):
        self._duration_s = duration_s
        self._end_time = None

    def start(self):
        """Starts the timer. Does nothing if the timer is already started"""
        if self._end_time is not None:
            return
        self._end_time = time.time() + self._duration_s

    def clear(self):
        """Stops the timer. Resets all state."""
        self._end_time = None

    def expired(self):
        """Returns true if the timer has expired."""
        if self._end_time is None:
            return False
        return time.time() > self._end_time
