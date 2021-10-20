from hex import HecsCoord
from queue import Queue

class State(object):
    def __init__(self, map, actors):
        self._map = map
        self._actors = actors
        self._synced = False
    
    def update(self):
        sync_needed = False
        for i in range(len(self._actors)):
            actor = self._actors[i]
            if not self.valid_action(actor.peek()):
                sync_needed = True
                continue
            actor.step()
        if sync_needed:
            print("Found invalid action. Resyncing...")
            self._synced = False
            
    def is_synced():
        return self._synced
    
    # Calling this message comes with the assumption that the response will be transmitted to the clients.
    def sync_message_for_transmission(self):
        # This won't do... there might be some weird oscillation where an
        # in-flight invalid packet triggers another sync. need to communicate
        # round trip.
        self._synced = True
        return None
    
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
        return self._heading_degrees
    
    def peek(self):
        return self._actions.queue[0]

    def step(self):
        if self.empty():
            return 
        action = self._actions.get()
        self._location = action.destination
        self._heading_degrees = action.destination_heading