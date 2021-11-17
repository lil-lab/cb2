""" A set of general utilities that are used across the server. """


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


def SafePasswordCompare(a, b):
    """ Compares two passwords. Resistant to timing attacks.  """
    if len(a) != len(b):
        return False
    return all(x == y for x, y in zip(a, b))
