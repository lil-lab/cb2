"""This class is used to properly handle exceptions that are streamed over the network from the client side.

It makes a number of tradeoffs:
1. We can't freely log all exceptions received. But newer exceptions are more useful than old ones. So we keep a
   rolling buffer of the last N exceptions.
2. We don't want this system to slow down the server, so we wait until shutdown to write the exceptions to database.
"""

from typing import List

from server.messages.client_exception import ClientException
from server.schemas.client_exception import ClientException as ClientExceptionSchema

DEFAULT_MAX_EXCEPTIONS = 0


class ClientExceptionLogger(object):
    def __init__(self):
        self._max_exceptions = DEFAULT_MAX_EXCEPTIONS
        self._exceptions = []

    def set_config(self, config):
        self._max_exceptions = config.max_client_exceptions

    def queue_exception(self, exception: ClientException):
        self._exceptions.append(exception)
        if len(self._exceptions) > self._max_exceptions:
            self._exceptions.pop(0)

    def pending_exceptions(self) -> List[ClientException]:
        return list(self._exceptions)

    def save_exceptions_to_db(self):
        for exception in self._exceptions:
            db_exception = ClientExceptionSchema(
                game_id=exception.game_id,
                role=exception.role,
                bug_report=exception.bug_report.to_json(),
                condition=exception.condition,
                stack_trace=exception.stack_trace,
            )
            db_exception.save(force_insert=True)
        # If there's more than self._max_exceptions in the database, delete the oldest ones.
        # This is a bit inefficient, but it runs once at the end of the server.
        num_exceptions = ClientExceptionSchema.select().count()
        if num_exceptions > self._max_exceptions:
            num_to_delete = num_exceptions - self._max_exceptions
            # Delete the oldest ones.
            oldest_exceptions = (
                ClientExceptionSchema.select()
                .order_by(ClientExceptionSchema.date.asc())
                .limit(num_to_delete)
            )
            for exception in oldest_exceptions:
                exception.delete_instance()
