import aiohttp
import asyncio

from messages.action import Action
from messages import state_sync
from hex import HecsCoord
from queue import Queue

MAX_ID = 1000000

# Note... you can do better via a BST of tuples of unallocated values.
class IdAssigner(object):
    def __init__(self):
        self._last_id = 0
    def alloc(self):
        if self._last_id >= MAX_ID:
            return -1
        
        id = self._last_id
        self._last_id += 1
        return id
    
    def free(self, id):
        pass

class State(object):
    def __init__(self):
        self._actors = {}
        self._synced = {}
        self._id_assigner = IdAssigner()
        self._action_history = {}
        self._done = False
    
    def end_game(self):
        self._done = True

    def record_action(self, action):
        for id in self._actors:
            actor = self._actors[id]
            self._action_history[actor.actor_id()].append(action)       
    
    async def update(self):
        while not self._done:
            await asyncio.sleep(0.001)
            for actor_id in self._actors:
                actor = self._actors[actor_id]
                if actor.empty():
                    continue
                action = actor.peek()
                if not self.valid_action(actor_id, action):
                    self.desync()
                    print("Found invalid action. Resyncing...")
                    continue
                self.record_action(action)
                actor.step()
    
    def handle_action(self, actor_id, action):
        self._actors[actor_id].add_action(action)
    
    def create_actor(self):
        actor = Actor(self._id_assigner.alloc(), 0)
        self._actors[actor.actor_id()] = actor
        self._action_history[actor.actor_id()] = []
        self._synced[actor.actor_id()] = False
        # Mark clients as desynced.
        self.desync_all()
        return actor.actor_id()
    
    def free_actor(self, actor_id):
        del self._actors[actor_id]
        del self._action_history[actor_id]
        self._id_assigner.free(actor_id)
        # Mark clients as desynced.
        self.desync()
    
    def desync(self, actor_id):
        self._synced[actor_id] = False
    
    def desync_all(self):
        for a in self._actors:
            actor = self._actors[a]
            self._synced[actor.actor_id()] = False
            
    def is_synced(self, actor_id):
        return self._synced[actor_id]

    def is_synced_all(self):
        for a in self._actors:
            if not self.synced(a.actor_id()):
                return False
        return True

    def drain_actions(self, actor_id):
        if not actor_id in self._action_history:
            return []
        action_history = self._action_history[actor_id]
        self._action_history[actor_id] = []
        return action_history
    
    # Returns the current state of the game.
    def state(self, actor_id=-1):
        actor_states = []
        for a in self._actors:
            actor = self._actors[a]
            actor_states.append(actor.state())
        return state_sync.StateSync(actor_states, actor_id)
        
    # Returns the current state of the game.
    # Calling this message comes with the assumption that the response will be transmitted to the clients.
    # Once this function returns, the clients are marked as synchronized. 
    def sync_message_for_transmission(self, actor_id):
        # This won't do... there might be some weird oscillation where an
        # in-flight invalid packet triggers another sync. need to communicate
        # round trip.
        sync_message = self.state(actor_id)
        self._synced[actor_id] = True
        return sync_message
    
    def valid_action(self, actor_id, action):
        return True

class Actor(object):
    def __init__(self, actor_id, asset_id):
        self._actor_id = actor_id
        self._asset_id = asset_id
        self._actions = Queue()
        self._location = HecsCoord(0, 0, 0)
        self._heading_degrees = 0
    
    def actor_id(self):
        return self._actor_id

    def asset_id(self):
        return self._asset_id
    
    def add_action(self, action):
        self._actions.put(action)

    def empty(self):
        return self._actions.empty()
    
    def location(self):
        return self._location

    def heading_degrees(self):
        return int(self._heading_degrees)
    
    def peek(self):
        return self._actions.queue[0]

    def state(self):
        return state_sync.Actor(self.actor_id(), self.asset_id(),
                                self._location, self._heading_degrees)

    def step(self):
        if self.empty():
            return 
        action = self._actions.get()
        self._location = action.destination
        self._heading_degrees = int(action.destination_heading)