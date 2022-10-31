""" This file defines an API for querying game information directly from the server.

This is used by clients to query the server's game records. For performance,
if you're doing anything serious, it's recommended to directly download the
database ('/data/download' endpoint defined in main.py) and query it locally.

Python fire is used to make the API automatically. Right now, it's set up specifically for the instruction query class.

Example usage:
# Fetch information about instruction 091788715c99495682bcaa3c8a3d814a
python3 -m server.db_tools.game_query --i_uuid=091788715c99495682bcaa3c8a3d814a --base_url="http://localhost:8080" fetch instruction

# Fetch live feedback for instruction 091788715c99495682bcaa3c8a3d814a
python3 -m server.db_tools.game_query --i_uuid=091788715c99495682bcaa3c8a3d814a --base_url="http://localhost:8080" fetch live_feedback

# Fetch move information for instruction 091788715c99495682bcaa3c8a3d814a
python3 -m server.db_tools.game_query --i_uuid=091788715c99495682bcaa3c8a3d814a --base_url="http://localhost:8080" fetch moves

You can also import this file and use the classes directly.
"""
import hashlib
import json
import logging
import urllib.request

import colorhash
import fire
import matplotlib.pyplot as plt
import numpy as np
from dateutil import parser

from server.db_tools.game_record import GameRecord

logger = logging.getLogger(__name__)


class TurnQuery(object):
    TURN_FETCH_URL = "https://cerealbar2.com/data/turns/{}"

    def __init__(self, game_id):
        self._game_id = game_id
        self._data = {}

    def query(self):
        if self._data != {}:
            logger.info(f"Already fetched data for game {self._game_id}.")
            return
        url = self.TURN_FETCH_URL.format(self._game_id)
        response = urllib.request.urlopen(url)
        logger.info(f"Fetched {url}")
        data = json.loads(response.read())
        self._data = data
        return self

    def roles(self):
        return np.array([turn["role"] for turn in self._data])

    def durations_s(self):
        end_times = [parser.isoparse(turn["time"]) for turn in self._data]
        durations = [end_times[i] - end_times[i - 1] for i in range(1, len(end_times))]
        durations_s = [d.total_seconds() for d in durations]

        # This is hacky but... get the game's start time to calculate the first turn's duration.
        # Always guaranteed to exist if this class was generated within GameQuery.
        if len(self._data) == 0:
            return np.array(durations_s)
        game_record = (
            GameQuery.QueryFromId(self._game_id).query().record_from_id(self._game_id)
        )
        start_time = parser.parse(game_record.start_time)
        first_turn_duration = parser.parse(self._data[0]["time"]) - start_time
        durations_s.insert(0, first_turn_duration.total_seconds())

        return np.array(durations_s)


class MoveQuery(object):
    MOVE_FETCH_URL = "https://cerealbar2.com/data/moves/{}"

    def __init__(self, turn_id):
        self._turn_id = turn_id
        self._data = {}

    def fetch(self):
        url = self.MOVE_FETCH_URL.format(self._turn_id)
        response = urllib.request.urlopen(url)
        logger.info(f"Fetched {url}")
        data = json.loads(response.read())
        self._data = data
        return self


class InstructionQuery(object):
    INSTRUCTION_FETCH_URL = "{}/data/instruction/{}"
    MOVE_FETCH_URL = "{}/data/moves_for_instruction/{}"
    LIVE_FEEDBACK_FETCH_URL = "{}/data/live_feedback/{}"

    def __init__(self, base_url, i_uuid=""):
        self._base_url = base_url
        self._instruction_uuid = i_uuid
        self._instruction = {}
        self._moves = []
        self._live_feedback = []

    def instruction(self):
        return self._instruction

    def moves(self):
        return self._moves

    def live_feedback(self):
        return self._live_feedback

    def fetch(self):
        self._instruction = self._fetch_json(
            self.INSTRUCTION_FETCH_URL.format(self._base_url, self._instruction_uuid)
        )
        self._moves = self._fetch_json(
            self.MOVE_FETCH_URL.format(self._base_url, self._instruction_uuid)
        )
        self._live_feedback = self._fetch_json(
            self.LIVE_FEEDBACK_FETCH_URL.format(self._base_url, self._instruction_uuid)
        )
        return self

    def _fetch_json(self, url):
        response = urllib.request.urlopen(url)
        logger.debug(f"Fetched {url}")
        return json.loads(response.read())


class GameQuery(object):
    QUERIES = set([])

    def __init__(self):
        logging.basicConfig(level=logging.INFO)
        self._from_id = 0
        self._to_id = 0
        self._filter_name = ""
        self._mturk_only = True
        self._games = []
        self._games_by_id = {}
        self._plotter_funcs = []
        GameQuery.QUERIES.add(self)

    @classmethod
    def NamedFilters(cls):
        return {
            "separated-games-1": (2126, 2199),
            "separated-games-2": (2218, 2283),
        }

    def filter_by_name(self, filter_name):
        named_filters = GameQuery.NamedFilters()
        self._from_id, self._to_id = named_filters[filter_name]
        self._filter_name = filter_name
        return self

    def contains(self, game_id):
        return game_id in range(self._from_id, self._to_id + 1)

    @classmethod
    def QueryFromId(cls, game_id):
        for query in cls.QUERIES:
            if query.contains(game_id):
                return query
        return None

    def from_id(self, from_id):
        self._from_id = from_id
        return self

    def to_id(self, to_id):
        self._to_id = to_id
        return self

    def record_from_id(self, id):
        return self._games_by_id.get(id, None)

    def all_games(self):
        self._mturk_only = False
        return self

    def query(self):
        if len(self._games) > 0:
            logger.info(
                f"Already fetched data for games {self._from_id} to {self._to_id}."
            )
            return self
        GAME_FETCH_URL = "https://cerealbar2.com/data/game-list"
        games = []
        with urllib.request.urlopen(GAME_FETCH_URL) as response:
            logger.info(f"Fetched data from {GAME_FETCH_URL}")
            games_json = json.loads(response.read())
            games = [
                GameRecord.from_json(json.dumps(game_json)) for game_json in games_json
            ]
            games = [
                game
                for game in games
                if (game.id >= self._from_id) and (game.id <= self._to_id)
            ]
            if self._mturk_only:
                games = [game for game in games if game.type == "game-mturk"]
            for game in games:
                if game.leader is None:
                    game.leader = ""
                if game.follower is None:
                    game.follower = ""
                self._games_by_id[game.id] = game
            self._games = games
            return self

    def print(self):
        print(GameRecord.CSV_HEADER)
        for game in self._games:
            print(game.csvline())

    def _turn_histogram_plotter(self):
        # Aggregate the turn durations for each game.
        durations_s = np.empty(0)
        for game in self._games:
            turn_query = TurnQuery(game.id).query()
            durations_s = np.append(durations_s, turn_query.durations_s())

        # Plot the histogram.
        plt.hist(durations_s, bins=100)
        plt.title("Turn durations")
        plt.xlabel("Duration (s)")
        plt.ylabel("Frequency")

    def turn_histogram(self):
        self._plotter_funcs.append(self._turn_histogram_plotter)
        return self

    def _per_follower_scatter(self, followers_file):
        # Aggregate the average scores and number of games for each follower..
        with open(followers_file) as f:
            followers = [line.strip() for line in f]
            # Now take the md5sum of each follower to get a unique key.
            followers = [
                hashlib.md5(follower.encode("utf-8")).hexdigest()
                for follower in followers
            ]
        evaluated_followers = set(followers)
        logger.info(f"Evaluated followers: {evaluated_followers}")

        per_follower_scores = {}
        for game in self._games:
            if len(game.follower) == 0:
                continue
            if game.follower not in evaluated_followers:
                continue
            game_score = game.score
            game_duration = game.parse_duration()
            if game_duration.total_seconds() == 0:
                continue
            if game.follower not in per_follower_scores:
                per_follower_scores[game.follower] = np.empty(0)
            per_follower_scores[game.follower] = np.append(
                per_follower_scores[game.follower], game_score
            )

        per_follower_avg_score = {}
        per_follower_number_of_games = {}
        for follower in per_follower_scores:
            per_follower_avg_score[follower] = np.mean(per_follower_scores[follower])
            per_follower_number_of_games[follower] = len(per_follower_scores[follower])

        # Plot the scatter.
        for follower in per_follower_avg_score:
            logger.info(
                f"Follower {follower} has {per_follower_number_of_games[follower]} games."
            )
            plt.scatter(
                per_follower_number_of_games[follower],
                per_follower_avg_score[follower],
                label=follower,
                alpha=0.5,
            )

        plt.title("Per-follower Performance")
        plt.xlabel("Number of games")
        plt.ylabel("Avg Score")
        plt.legend()

    def follower_scatter(self, followers_file):
        self._plotter_funcs.append(lambda: self._per_follower_scatter(followers_file))
        return self

    def _score_duration_scatter(self, compare_to_filter_name=""):
        # Aggregate the turn durations for each game.
        durations_m = np.empty(0)
        scores = np.empty(0)
        for game in self._games:
            duration = game.parse_duration()
            if duration.total_seconds() == 0:
                continue
            durations_m = np.append(
                durations_m, game.parse_duration().total_seconds() / 60
            )
            scores = np.append(scores, game.score)

        # Plot the scatter. Determine the color deterministically based on the filter name.
        color = colorhash.ColorHash(self._filter_name)
        logger.info(f"Plotting {self._filter_name} with color {color}")
        plt.scatter(durations_m, scores, label=self._filter_name, color=color.hex)
        plt.title("Score vs Duration")
        plt.xlabel("Duration (m)")
        plt.ylabel("Score")

        if len(compare_to_filter_name) > 0:
            compare_to_filter_name = (
                GameQuery().filter_by_name(compare_to_filter_name).query()
            )
            compare_to_filter_name._score_duration_scatter()

        plt.legend()

    def score_duration_histogram(self, *, compare_to=""):
        self._plotter_funcs.append(lambda: self._score_duration_scatter(compare_to))
        return self

    def _pay_rate_histogram(self):
        # Aggregate the turn durations for each game.
        leader_rates = np.empty(0)
        follower_rates = np.empty(0)
        for game in self._games:
            if game.leader_rate() > 15:
                logger.info(
                    f"High leader rate ${game.leader_rate()}/hr found in game with score: {game.score} and duration: {game.duration}"
                )
            if game.follower_rate() > 15:
                logger.info(
                    f"High follower rate ${game.follower_rate()}/hr found in game with score: {game.score} and duration: {game.duration}"
                )
            leader_rates = np.append(leader_rates, game.leader_rate())
            follower_rates = np.append(follower_rates, game.follower_rate())

        # Plot the histograms side by side.
        # Leader
        plt.subplot(1, 2, 1)
        plt.hist(leader_rates, bins=20)
        plt.title("Leader Pay Rate")
        plt.xlabel("Rate ($/hr)")
        plt.ylabel("Frequency")
        # Show mean and median.
        plt.axvline(
            np.mean(leader_rates),
            color="r",
            linestyle="dashed",
            linewidth=2,
            label=f"Mean ({np.mean(leader_rates):0.2f})",
        )
        plt.axvline(
            np.median(leader_rates),
            color="b",
            linestyle="dashed",
            linewidth=2,
            label=f"Median ({np.median(leader_rates):0.2f})",
        )
        plt.legend()

        # Follower
        plt.subplot(1, 2, 2)
        plt.hist(follower_rates, bins=20)
        plt.title("Follower Pay Rate")
        plt.xlabel("Rate ($/hr)")
        plt.ylabel("Frequency")
        # Show mean and median.
        plt.axvline(
            np.mean(follower_rates),
            color="r",
            linestyle="dashed",
            linewidth=2,
            label=f"Mean ({np.mean(follower_rates):0.2f})",
        )
        plt.axvline(
            np.median(follower_rates),
            color="b",
            linestyle="dashed",
            linewidth=2,
            label=f"Median ({np.median(follower_rates):0.2f})",
        )
        plt.legend()

    def pay_rate_histogram(self):
        self._plotter_funcs.append(self._pay_rate_histogram)
        return self

    def _cost_histogram(self, compare_to_filter_name=""):
        # Aggregate the turn durations for each game.
        costs = np.empty(0)
        for game in self._games:
            costs = np.append(costs, game.total_cost())

        if len(compare_to_filter_name) > 0:
            compare_to_filter_name = (
                GameQuery().filter_by_name(compare_to_filter_name).query()
            )
            compare_to_filter_name._cost_histogram()

        # Plot the histograms side by side.
        # Leader
        plt.subplot(1, 2, 1)
        color = colorhash.ColorHash(self._filter_name)
        plt.hist(
            costs,
            bins=20,
            label=f"{self._filter_name} (${costs.sum():0.2f} Total)",
            color=color.hex,
        )
        plt.title(f"Game Prices (amount paid in total)")
        plt.xlabel("Price ($)")
        plt.ylabel("Frequency")
        # Show mean and median.
        plt.axvline(
            np.mean(costs),
            color="r",
            linestyle="dashed",
            linewidth=2,
            label=f"Mean ({np.mean(costs):0.2f})",
        )
        plt.axvline(
            np.median(costs),
            color="b",
            linestyle="dashed",
            linewidth=2,
            label=f"Median ({np.median(costs):0.2f})",
        )
        plt.legend()

    def cost_histogram(self, *, compare_to=""):
        self._plotter_funcs.append(lambda: self._cost_histogram(compare_to))
        return self

    def instant_leave_rate(self):
        # Find the number of games that are less than 1 minute long.
        num_instant_leave = 0
        for game in self._games:
            duration_s = game.parse_duration().total_seconds()
            if duration_s > 0 and duration_s < 60:
                num_instant_leave += 1
        logger.info(
            f"Instant leave rate: {num_instant_leave}/{len(self._games)} ({num_instant_leave/len(self._games):0.2f}%)"
        )

    def instant_leave_players(self):
        # Find players that leave the game instantaneously.
        instant_leave_players = set([])
        for game in self._games:
            duration_s = game.parse_duration().total_seconds()
            if duration_s > 0 and duration_s < 60:
                instant_leave_players.update(game.players)
        logger.info(f"Instant leave players: {instant_leave_players}")

    def total_cost(self):
        total_cost = 0
        for game in self._games:
            total_cost += game.total_cost()
        logger.info(
            f"Total cost over {len(self._games)} games: ${total_cost}. Avg cost: ${total_cost / len(self._games)}"
        )

    def imshow(self):
        for plotter_function in self._plotter_funcs:
            plotter_function()
        plt.show()


if __name__ == "__main__":
    fire.Fire(InstructionQuery)
