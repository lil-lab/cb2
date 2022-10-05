import logging

from dataclasses import dataclass
from dataclasses_json import dataclass_json 
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass_json
@dataclass
class GameRecord(object):
  id: int = 0
  type: str = ""
  leader: str = ""
  leader_id: str = ""
  follower: str = ""
  follower_id: str = ""
  score: int = 0
  turns: int = 0
  start_time: str = ""
  duration: str = ""
  completed: bool = False

  CSV_HEADER = "Id, Leader ID, Follower ID, Score, Award ($), Turns, Start Time, Duration"

  def parse_duration(self):
    try:
      ts = datetime.strptime(self.duration, "%H:%M:%S.%f")
      duration = timedelta(hours=ts.hour, minutes=ts.minute, seconds=ts.second, microseconds=ts.microsecond)
      return duration
    except ValueError:
      return timedelta(seconds=0)

  # Calculated by https://cerealbar2.com/rules
  def follower_cost(self):
    amt = 0.30
    awards = [0.15, 0.25, 0.25, 0.30, 0.30, 0.35, 0.35, 0.40, 0.40, 0.40, 0.40, 0.50, 0.50, 0.60]
    for i in range(self.score):
      if i < len(awards):
        amt += awards[i]
      if i >= len(awards):
        amt += awards[-1]
    return amt

  # Calculated by https://cerealbar2.com/rules
  def follower_bonus(self):
    amt = 0.0
    awards = [0.15, 0.25, 0.25, 0.30, 0.30, 0.35, 0.35, 0.40, 0.40, 0.40, 0.40, 0.50, 0.50, 0.60]
    for i in range(self.score):
      if i < len(awards):
        amt += awards[i]
      if i >= len(awards):
        amt += awards[-1]
    return amt

  # Leaders get 10% more award.
  def leader_cost(self):
    return 1.10 * self.follower_cost()

  def leader_bonus(self):
    return 1.10 * self.follower_bonus()

  def total_cost(self):
    return self.leader_cost() + self.follower_cost()

  def leader_rate(self):
    """ Returns the effective pay rate of the leader per hour. """
    leader_hours = self.parse_duration().total_seconds() / 3600
    if leader_hours < 0.016:
      logger.info(f"Game {self.id} was too short to pay {self.duration}.")
      return 0.0
    return self.leader_award() / leader_hours
  
  def follower_rate(self):
    """ Returns the effective pay rate of the follower per hour. """
    follower_hours = self.parse_duration().total_seconds() / 3600
    if follower_hours < 0.016:
      logger.info(f"Game {self.id} was too short to pay {self.duration}.")
      return 0.0
    return self.award() / follower_hours

  def __str__(self):
    return f"{self.id}| l_id: {self.leader_id}, f_id: {self.follower_id}, score: {self.score}, award: ${self.award()}, turns: {self.turns}, start: {self.start_time}, dur: {self.duration}"

  def csvline(self):
    return f"{self.id}, {self.leader_id}, {self.follower_id}, {self.score}, {self.award():0.2f}, {self.turns}, {self.start_time}, {self.duration}"