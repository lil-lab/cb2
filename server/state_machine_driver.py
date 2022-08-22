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
        self._recvd_log = logging.getLogger(f'room_{room_id}.recv')
        self._record_log = logging.getLogger(f'room_{room_id}.log')
        self._sent_log = logging.getLogger(f'room_{room_id}.sent')
        self._recvd_log.info("State created.")
        self._record_log.info("State created.")
        self._sent_log.info("State created.")
        self._room_id = room_id

        # Message output. Each iteration loop, messages are serialized into per-player queues for sending.
        self._messages_out = {} # Player ID -> Queue() of messages
        # Linear message input. As network packets come in, they are placed in a queue for processing.
        self._messages_in = Queue() # Queue() of (player_id, message) tuples
    
    def state_machine(self):
        return self._state_machine
    
    def handle_packet(self, id, message):
        """
        Handles a packet from a player.
        """
        self._messages_in.put((id, message))

    def drain_message(self, player_id):
        """ Returns a MessageFromServer object to send to the indicated player.

            If no message is available, returns None.
        """
        if player_id not in self._messages_out:
            return None
        try:
            message = self._messages_out[player_id].get(block=False)
            return message
        except queue.Empty:
            return None
    
    async def run(self):
        last_loop = time.time()
        while not self._state_machine.done():
            self._process_incoming_messages()
            await self._state_machine.update()
            self._serialize_outgoing_messages()
            poll_period = time.time() - last_loop
            if (poll_period) > 0.1:
                logging.warn(
                    f"Game {self._room_id} slow poll period of {poll_period}s")
            last_loop = time.time()
            await asyncio.sleep(0)
        self._state_machine.on_game_over()
    
    def done(self):
        return self._state_machine.done()
    
    def end_game(self):
        self._state_machine.end_game()

    def _process_incoming_messages(self):
        # Process all available messages.
        while True:
            try:
                player_id, message = self._messages_in.get_nowait()
                self._state_machine.handle_packet(player_id, message)
            except queue.Empty:
                break

    def _serialize_outgoing_messages(self):
        for player_id in self._state_machine.player_ids():
            if player_id not in self._messages_out:
                self._messages_out[player_id] = Queue()
            message = self._state_machine.drain_message(player_id)
            while message != None:
                self._messages_out[player_id].put(message)
                message = self._state_machine.drain_message(player_id)
