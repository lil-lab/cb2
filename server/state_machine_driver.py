import asyncio
import logging
import queue
import time
from queue import Queue

logger = logging.getLogger(__name__)


class StateMachineDriver(object):
    """
    StateMachineDriver is a class that is responsible for managing the game state machine
    """

    def __init__(self, state_machine, room_id):
        """
        Initializes the state machine driver.
        """
        self._state_machine = state_machine

        # Logging init.
        self._recvd_log = logging.getLogger(f"sm_driver_{room_id}.recv")
        self._record_log = logging.getLogger(f"sm_driver_{room_id}.log")
        self._sent_log = logging.getLogger(f"sm_driver_{room_id}.sent")
        self._room_id = room_id

        # Message output. Each iteration loop, messages are serialized into per-player queues for sending.
        self._messages_out = {}  # Player ID -> Queue() of messages
        # Linear message input. As network packets come in, they are placed in a queue for processing.
        self._messages_in = Queue()  # Queue() of (player_id, message) tuples

    def state_machine(self):
        return self._state_machine

    def drain_messages(self, id, messages):
        for m in messages:
            self._messages_in.put((id, m))

    def fill_messages(self, player_id, out_messages):
        """Fills out_messages with MessageFromServer objects to send to the
        indicated player and returns True.

            If no message is available, returns False.
        """
        if player_id not in self._messages_out:
            return False
        packets_added = False
        while True:
            try:
                message = self._messages_out[player_id].get_nowait()
                logger.debug(
                    f"Sent message type {message.type} for player {player_id}."
                )
                out_messages.append(message)
                packets_added = True
            except queue.Empty:
                break
        return packets_added

    async def run(self):
        last_loop = time.time()
        self._state_machine.start()  # Initialize the state machine.
        while not self._state_machine.done():
            self.step()
            poll_period = time.time() - last_loop
            if (poll_period) > 0.1:
                logging.warn(f"Game {self._room_id} slow poll period of {poll_period}s")
            last_loop = time.time()
            await asyncio.sleep(0)
        self._state_machine.on_game_over()

    def step(self):
        self._process_incoming_messages()
        self._state_machine.update()
        self._serialize_outgoing_messages()

    def done(self):
        return self._state_machine.done()

    def end_game(self):
        self._state_machine.end_game()

    def _process_incoming_messages(self):
        # Process all available messages.
        messages = {}  # player_id -> message
        while True:
            try:
                player_id, message = self._messages_in.get_nowait()
                if player_id not in messages:
                    messages[player_id] = []
                messages[player_id].append(message)
            except queue.Empty:
                break
        for player_id in messages:
            self._state_machine.drain_messages(player_id, messages[player_id])

    def _serialize_outgoing_messages(self):
        for player_id in self._state_machine.player_ids():
            if player_id not in self._messages_out:
                self._messages_out[player_id] = Queue()
            out_messages = []
            if self._state_machine.fill_messages(player_id, out_messages):
                for message in out_messages:
                    self._messages_out[player_id].put(message)
