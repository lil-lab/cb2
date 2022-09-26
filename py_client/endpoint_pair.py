""" A wrapper for two game endpoints that allows them to play against each other in the same game. """
from py_client.game_endpoint import GameEndpoint, FollowAction, LeadAction, Role

import logging

logger = logging.getLogger(__name__)

class EndpointPair(object):
    def __init__(self, coordinator, game_name):
        """ Creates & manages two endpoints which are connected to the same local game. """
        self._leader = coordinator.JoinGame(game_name)
        self._follower = coordinator.JoinGame(game_name)
        coordinator.StartGame(game_name)
        self.coordinator = coordinator
        self.game_name = game_name 
        self._initial_state = None
        self.turn = None
    
    def initialize(self):
        self._leader.Initialize()
        self._follower.Initialize()
        assert self._leader.initialized(), "Leader failed to initialize."
        assert self._follower.initialized(), "Follower failed to initialize."
        initial_state = self._leader.initial_state()
        map, cards, turn_state, instructions, (leader, follower), live_feedback = initial_state
        if turn_state.turn == Role.LEADER:
            self._initial_state = initial_state
        else:
            self._initial_state = self._follower.initial_state()
        self.turn = turn_state.turn
    
    def leader(self):
        return self._leader
    
    def follower(self):
        return self._follower
    
    def over(self):
        return self._leader.over() or self._follower.over()
    
    def score(self):
        return self._leader.score()
    
    def duration(self):
        return self._leader.game_duration()
    
    def initial_state(self):
        """ Returns the initial state of the game once. If already previously called, returns None. """
        state = self._initial_state
        self._initial_state = None
        return state

    def step(self, action):
        """ Takes a single step in the game. """
        if self.turn == Role.LEADER:
            leader_result = self._leader.step(action, wait_for_turn=False)
            map, cards, turn_state, instructions, actors, live_feedback = leader_result
            follower_result = self._follower.step(FollowAction(FollowAction.ActionCode.NONE), wait_for_turn=False)
            self.turn = turn_state.turn
        elif self.turn == Role.FOLLOWER:
            follower_result = self._follower.step(action, wait_for_turn=False)
            map, cards, turn_state, instructions, actors, live_feedback = follower_result
            leader_result = self._leader.step(LeadAction(LeadAction.ActionCode.NONE), wait_for_turn=False)
            self.turn = turn_state.turn
        else:
            raise Exception(f"Invalid turn state {self.turn}.")
        if self.turn == Role.LEADER:
            return leader_result
        else:
            return follower_result