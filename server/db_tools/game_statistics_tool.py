import fire
import numpy as np
from autocorrect import Speller
from nltk.tokenize import word_tokenize

import server.config.config as config
import server.schemas.defaults as defaults_db
from server.db_tools.db_utils import (
    follower_got_lost,
    high_percent_cancelled_instructions,
    short_game,
)
from server.schemas import base
from server.schemas.cards import CardSelections, CardSets
from server.schemas.game import Game, Instruction, LiveFeedback, Move
from server.schemas.mturk import Worker

SECRET_LEADER_ID = 3
SECRET_FOLLOWER_ID = 4
ACTIVE_MOVE_WINDOW = 0.25

COMMANDS = [
    "game_counts",  # Prints out the number of human-human and human-AI games
    "help",  # Prints an overview of commands
    "follower_qualification_speed",  # Prints out how many games qualified followers needed to get a qual
    "basic_stats",  # Prints out basic game stats like avg/high scores
    "instruction_stats",  # Prints out stats related to instructions like length/vocab size
    "termination_stats",  # Prints stats related to instruction termination behavior
    "basic_feedback_stats",  # Prints stats related to feedback rates
    "feedback_action_stats",  # Prints stats about how many actions are assigned feedback
    "set_completion_efficiency",  # Prints stats about how fast many steps are needed for set completion
    "card_role_percentage",  # Prints stats about what percentage of cards are grabbed by whom
    "deselection_rate_stats",  # Prints stats related to card deselection
    "instruction_chaining_amount",  # Prints stats related to instruction chaining
    "num_invalid_games",  # Prints the number and type of invalid games
    "leader_feedback_rates",  # Prints information about individual leaders' feedback
    "execution_length_cap",  # Prints info about what percentage
]


def PrintUsage():
    print("Usage:")
    print("  game_counts --from_id=[0-9]+ --to_id=[0-9]+ --id_file=<str>")
    print("  help")
    print("Check the script for more. I need to write all of this.")


### Repeated utility functions
def get_list_of_ids(to_id, from_id, id_file):
    given_range = to_id != "" and from_id != "" and id_file == ""
    given_file = to_id == "" and from_id == "" and id_file != ""
    assert (given_range or given_file, "Function expects either a file or a range")

    if given_range:
        ids = [i for i in range(int(from_id), int(to_id) + 1)]
    elif given_file:
        with open(id_file, "r") as f:
            ids = []
            for line in f.readlines():
                ids.append(int(line.strip("\n")))
    else:
        assert (False, "This cannot be!")

    return ids


def filter_game(game):
    # Check if the game is an mturk game
    if game.type != "follower-pilot-lobby|4|game-mturk":
        return True

    if game.leader_id == game.follower_id:
        return True

    if game.leader_id == SECRET_LEADER_ID and game.follower_id == SECRET_FOLLOWER_ID:
        return True

    return False


def get_duration(start_time, end_time):
    diff = end_time - start_time
    return diff.seconds / 60


def get_active_instructions(instructions):
    return [i for i in instructions if i.turn_activated != -1]


def process_instruction(text):
    # Perform autocorrect spelling check, tokenize with NLTK and lowercase
    spell = Speller()
    text = spell(text)
    tokens = word_tokenize(text)
    tokens = [token.lower() for token in tokens]
    return tokens


def process_unique_tokens_counts(all_stats, tokens):
    unique_tokens = set()
    for token in tokens:
        all_stats["all_vocabs"].add(token)
        unique_tokens.add(token)
    all_stats["unique_vocab_per_instruction"].append(len(unique_tokens))


### Main analysis functions
def ReportGameTypes(ids):
    # Counters for the number of games
    num_human_human = 0
    num_human_AI = 0

    # Iterate over each mturk game in the set of ids. Update counter based on game type
    for i in ids:
        game = Game.select().where(Game.id == i).get()
        if filter_game(game):
            continue

        if game.follower_id is None:
            num_human_AI += 1
        else:
            num_human_human += 1

    print(
        f"There are a total of {num_human_human} human-human games and {num_human_AI} human-AI games"
    )
    print(f"Overall game count: {num_human_human + num_human_AI}")


def ReportFollowerQualificationSpeed(ids):
    follower_to_stats = {}

    for i in ids:
        game = Game.select().where(Game.id == i).get()
        if filter_game(game) or game.follower_id is None:
            continue

        # Initialize the follower
        curr_follower = game.follower_id
        if curr_follower not in follower_to_stats:
            follower_to_stats[curr_follower] = {"total_games": 0, "above_2": 0}

        # Increment stats
        if follower_to_stats[curr_follower]["above_2"] < 2:
            follower_to_stats[curr_follower]["total_games"] += 1
            if game.score >= 3:
                follower_to_stats[curr_follower]["above_2"] += 1

    # Report average number of games to promotion
    print(f"There are {len(follower_to_stats)} followers")
    total_passed = 0
    req_games = 0
    for follower, stats in follower_to_stats.items():
        if stats["above_2"] == 2:
            total_passed += 1
            req_games += stats["total_games"]
    print(
        f"{total_passed} followers passed the training stage. On average, this took {req_games / total_passed} games"
    )


def ReportBasicStats(ids, game_type):
    all_stats = {"scores": [], "durations": [], "turns": []}

    for i in ids:
        game = Game.select().where(Game.id == i).get()
        if filter_game(game):
            continue

        if game_type == "human" and game.follower_id is None:
            continue
        if game_type == "ai" and game.follower_id is not None:
            continue

        all_stats["scores"].append(game.score)
        all_stats["durations"].append(get_duration(game.start_time, game.end_time))
        all_stats["turns"].append(game.number_turns)

    print(
        f"Human-{game_type} average score: {np.mean(all_stats['scores'])} pm {np.std(all_stats['scores'])}"
    )
    print(f"Human-{game_type} high score: {max(all_stats['scores'])}")
    print(
        f"Human-{game_type} average duration: {np.mean(all_stats['durations'])} pm {np.std(all_stats['durations'])}"
    )
    print(f"Human-{game_type} max duration: {max(all_stats['durations'])}")
    print(
        f"Human-{game_type} average num turns: {np.mean(all_stats['turns'])} pm {np.std(all_stats['turns'])}"
    )
    print(f"Human-{game_type} max turns: {max(all_stats['turns'])}")
    print()


def ReportInstructionStats(ids, game_type):
    all_stats = {
        "count": 0,
        "all_vocabs": set(),
        "unique_vocab_per_instruction": [],
        "lengths": [],
        "total_instruction_per_game": [],
        "active_instruction_per_game": [],
        "follower_actions_per_instruction": [],
    }

    for i in ids:
        game = Game.select().where(Game.id == i).get()
        if filter_game(game):
            continue
        if game_type == "human" and game.follower_id is None:
            continue
        if game_type == "ai" and game.follower_id is not None:
            continue

        # Instruction count statistics
        instructions = Instruction.select().join(Game).where(Instruction.game == game)
        active_instructions = get_active_instructions(instructions)
        all_stats["count"] += len(active_instructions)
        all_stats["total_instruction_per_game"].append(len(instructions))
        all_stats["active_instruction_per_game"].append(len(active_instructions))

        # Get per instruction statistics
        for instruction in active_instructions:
            # Get vocabulary statistics
            tokens = process_instruction(instruction.text)
            process_unique_tokens_counts(all_stats, tokens)
            all_stats["lengths"].append(len(tokens))

            # Get follower action statistics
            moves = (
                Move.select()
                .join(Game)
                .where(
                    Move.game == game,
                    Move.instruction == instruction,
                    Move.character_role == "Role.FOLLOWER",
                )
                .order_by(Move.id)
            )
            num_moves = len(moves)
            if instruction.turn_completed != -1:
                num_moves += 1
            all_stats["follower_actions_per_instruction"].append(num_moves)

    # Report instruction counts
    print(f"Human-{game_type} instruction count: {all_stats['count']}")
    print(
        f"Human-{game_type} average active instruction count: {np.mean(all_stats['active_instruction_per_game'])} "
        + f"pm {np.std(all_stats['active_instruction_per_game'])}"
    )
    print(
        f"Human-{game_type} max active instruction count: {max(all_stats['active_instruction_per_game'])}"
    )
    print(
        f"Human-{game_type} average overall instruction count: {np.mean(all_stats['total_instruction_per_game'])} "
        + f"pm {np.std(all_stats['total_instruction_per_game'])}"
    )
    print(
        f"Human-{game_type} max overall instruction count: {max(all_stats['total_instruction_per_game'])}"
    )

    # Report vocabulary
    print(f"Human-{game_type} vocabulary size: {len(all_stats['all_vocabs'])}")
    print(
        f"Human-{game_type} average number of unique tokens per instruction: {np.mean(all_stats['unique_vocab_per_instruction'])} "
        + f"pm {np.std(all_stats['unique_vocab_per_instruction'])}"
    )
    print(
        f"Human-{game_type} max number of unique tokens per instruction: {max(all_stats['unique_vocab_per_instruction'])}"
    )
    print(
        f"Human-{game_type} average instruction length: {np.mean(all_stats['lengths'])} "
        + f"pm {np.std(all_stats['lengths'])}"
    )
    print(f"Human-{game_type} max instruction length: {max(all_stats['lengths'])}")

    # Report number of follower actions per instruction
    print(
        f"Human-{game_type} average number of follower actions per instruction: {np.mean(all_stats['follower_actions_per_instruction'])} "
        + f"pm {np.std(all_stats['follower_actions_per_instruction'])}"
    )
    print(
        f"Human-{game_type} max number of follower actions per instruction: {max(all_stats['follower_actions_per_instruction'])}"
    )
    print()


def ReportTerminationStats(ids, game_type):
    termination_percentages = []
    total_instructions = 0
    total_cancelled = 0

    for i in ids:
        game = Game.select().where(Game.id == i).get()
        if filter_game(game):
            continue
        if game_type == "human" and game.follower_id is None:
            continue
        if game_type == "ai" and game.follower_id is not None:
            continue

        # Get the number of active instructions
        instructions = Instruction.select().join(Game).where(Instruction.game == game)
        active_instructions = get_active_instructions(instructions)
        num_inst = len(active_instructions)
        total_instructions += num_inst
        if num_inst == 0:
            continue

        # Get the number of terminated instructions
        num_cancelled = 0
        for inst in active_instructions:
            if inst.turn_cancelled != -1:
                num_cancelled += 1
                total_cancelled += 1

        termination_percentages.append(num_cancelled / num_inst)

    print(
        f"Human-{game_type}, average percentage of instructions cancelled per game is: {np.mean(termination_percentages)}"
    )
    print(
        f"Human-{game_type}, percentage of instructions cancelled overall is: {total_cancelled / total_instructions}"
    )


def ReportFeedbackStats(ids, game_type):
    total_feedback = 0
    total_positive_feedback = 0
    total_negative_feedback = 0

    total_instruction = 0
    total_instruction_with_feedback = 0

    for i in ids:
        game = Game.select().where(Game.id == i).get()
        if filter_game(game):
            continue
        if game_type == "human" and game.follower_id is None:
            continue
        if game_type == "ai" and game.follower_id is not None:
            continue

        # Get list of instructions
        instructions = Instruction.select().join(Game).where(Instruction.game == game)
        active_instructions = get_active_instructions(instructions)
        total_instruction += len(active_instructions)

        for instruction in active_instructions:
            feedbacks = (
                LiveFeedback.select()
                .join(Game)
                .where(LiveFeedback.instruction_id == instruction.id)
            )

            # Check if there is feedback
            if len(feedbacks) > 0:
                total_instruction_with_feedback += 1

            total_feedback += len(feedbacks)
            pos_feedback_count = len(
                [f for f in feedbacks if f.feedback_type == "POSITIVE"]
            )
            total_positive_feedback += pos_feedback_count
            neg_feedback_count = len(feedbacks) - pos_feedback_count
            total_negative_feedback += neg_feedback_count

    print(
        f"Human-{game_type}, percentage of instructions with feedback: {total_instruction_with_feedback / total_instruction}"
    )
    print(
        f"Human-{game_type}, number of feedback given: positive {total_positive_feedback}, negative: {total_negative_feedback}"
        + f", overall: {total_feedback}"
    )
    print(
        f"Human-{game_type}: percentage of positive feedback is {total_positive_feedback / total_feedback}"
    )
    print(
        f"Human-{game_type}: percentage of negative feedback is {total_negative_feedback / total_feedback}"
    )


def ReportFeedbackActionStats(ids, game_type):
    # Get dictionary mapping instruction ids to feedback information
    instruction_to_feedbacks = get_feedback_dictionary(ids, game_type)

    # Stat reporting
    report_dropped_feedback(instruction_to_feedbacks, game_type)
    report_action_feedback_stats(instruction_to_feedbacks, game_type)
    print()


def get_feedback_dictionary(ids, game_type):
    instruction_to_feedbacks = {}
    used_feedbacks = set()

    for i in ids:
        game = Game.select().where(Game.id == i).get()
        if filter_game(game):
            continue
        if game_type == "human" and game.follower_id is None:
            continue
        if game_type == "ai" and game.follower_id is not None:
            continue

        instructions = (
            Instruction.select()
            .join(Game)
            .where(Instruction.game == game)
            .order_by(Instruction.id)
        )
        active_instructions = get_active_instructions(instructions)
        for inst in active_instructions:
            curr_dict = {"dropped": [], "action_stats": []}

            # Get standard moves and feedback
            moves = (
                Move.select()
                .join(Game)
                .where(
                    Move.instruction_id == inst.id,
                    Move.character_role == "Role.FOLLOWER",
                )
                .order_by(Move.id)
            )
            move_buckets = [[] for move in moves]
            feedbacks = (
                LiveFeedback.select()
                .join(Game)
                .where(LiveFeedback.instruction_id == inst.id)
                .order_by(LiveFeedback.id)
            )

            # Get feedback and moves if the last action is a DONE
            move_types = [move.action_code for move in moves]
            all_moves = [move for move in moves]
            remaining_feedbacks = []
            if len(move_types) > 0 and move_types[-1] == "DONE":
                remaining_moves = (
                    Move.select()
                    .join(Game)
                    .where(
                        Move.game_id == all_moves[-1].game_id,
                        Move.character_role == "Role.FOLLOWER",
                        Move.turn_number == all_moves[-1].turn_number,
                        Move.game_time > all_moves[-1].game_time,
                    )
                )
                remaining_moves = [move for move in remaining_moves.order_by(Move.id)]
                all_moves += remaining_moves[:1]

                remaining_feedbacks = (
                    LiveFeedback.select()
                    .join(Game)
                    .where(
                        LiveFeedback.game_id == all_moves[-1].game_id,
                        LiveFeedback.turn_number == all_moves[-1].turn_number,
                        LiveFeedback.game_time > all_moves[-1].game_time,
                    )
                )
                remaining_feedbacks = remaining_feedbacks.order_by(LiveFeedback.id)

            # Assign the feedbacks to moves
            assign_feedback_to_moves(
                all_moves,
                move_buckets,
                feedbacks,
                remaining_feedbacks,
                used_feedbacks,
                curr_dict,
            )

            # Record the feedbacks
            for action, feedbacks in zip(move_types, move_buckets):
                curr_dict["action_stats"].append((action, feedbacks))
            instruction_to_feedbacks[inst.id] = curr_dict

    return instruction_to_feedbacks


def assign_feedback_to_moves(
    all_moves, move_buckets, feedbacks, remaining_feedbacks, used_feedbacks, curr_dict
):
    # First go through standard feedback
    for feedback in feedbacks:
        if feedback.id in used_feedbacks:
            continue

        bucket_index = get_bucket_index(all_moves, feedback, len(move_buckets))
        curr_value = numeric_feedback(feedback.feedback_type)
        if bucket_index != -1:
            move_buckets[bucket_index].append(curr_value)
            used_feedbacks.add(feedback.id)
        else:
            curr_dict["dropped"].append(curr_value)

    for feedback in remaining_feedbacks:
        bucket_index = get_bucket_index(all_moves, feedback, len(move_buckets))
        curr_value = numeric_feedback(feedback.feedback_type)
        if bucket_index != -1:
            move_buckets[bucket_index].append(curr_value)
            used_feedbacks.add(feedback.id)


def get_bucket_index(moves, feedback, num_moves):
    standard_time = time_in_seconds(feedback.game_time)
    adjusted_time = standard_time - 0.2

    for i in range(num_moves):
        # If the feedback was issued in a different turn, skip.
        if moves[i].turn_number != feedback.turn_number:
            continue

        move_time = time_in_seconds(moves[i].game_time)
        if i == 0 or moves[i - 1].turn_number != moves[i].turn_number:
            if adjusted_time < move_time and move_time <= standard_time:
                return i
            elif move_time <= adjusted_time:
                if i == len(moves) - 1:
                    return i
                elif adjusted_time < time_in_seconds(moves[i + 1].game_time):
                    return i
        elif move_time <= adjusted_time:
            if i == len(moves) - 1:
                return i
            elif adjusted_time < time_in_seconds(moves[i + 1].game_time):
                return i

    return -1


def time_in_seconds(game_time):
    hour, minute, second = [float(t) for t in game_time.split(":")]
    return hour * (60**2) + minute * 60 + second


def numeric_feedback(feedback_type):
    return 1 if feedback_type == "POSITIVE" else -1


def report_dropped_feedback(i2f, game_type):
    total_feedback = 0
    total_dropped = 0
    total_dropped_pos = 0
    total_dropped_neg = 0

    for i_id, stats in i2f.items():
        # Add dropped values
        for feedback in stats["dropped"]:
            total_feedback += 1
            total_dropped += 1
            if feedback == +1:
                total_dropped_pos += 1
            else:
                total_dropped_neg += 1

        for action, feedbacks in stats["action_stats"]:
            total_feedback += len(feedbacks)

    print(f"Human-{game_type}, total number of feedback: {total_feedback}")
    print(
        f"Human-{game_type}, dropped feedback forms {total_dropped / total_feedback}% ({total_dropped}/{total_feedback}) of this"
    )
    print(
        f"Human-{game_type}, {total_dropped_pos / total_dropped}% of dropped is positive and {total_dropped_neg/total_dropped} is negative"
    )


def report_action_feedback_stats(i2f, game_type):
    action_stats = {}
    for action_type in ["MF", "MB", "TR", "TL", "DONE", "overall"]:
        action_stats[action_type] = {
            "without": 0,
            "cancelled_out": 0,
            "positive": 0,
            "negative": 0,
            "with": 0,
            "feedback_count_per": [],
        }
    act_with_f_per_inst = []

    for i_id, stats in i2f.items():
        per_instruction = 0
        for action, feedbacks in stats["action_stats"]:
            action_stats[action]["feedback_count_per"].append(len(feedbacks))
            action_stats["overall"]["feedback_count_per"].append(len(feedbacks))

            if sum(feedbacks) == 0:
                action_stats[action]["without"] += 1
                action_stats["overall"]["without"] += 1
                if len(feedbacks) > 0:
                    action_stats[action]["cancelled_out"] += 1
                    action_stats["overall"]["cancelled_out"] += 1
            else:
                action_stats[action]["with"] += 1
                action_stats["overall"]["with"] += 1
                per_instruction += 1

                label = "positive" if sum(feedbacks) > 0 else "negative"
                action_stats[action][label] += 1
                action_stats["overall"][label] += 1

        if len(stats["action_stats"]) > 0:
            act_with_f_per_inst.append(per_instruction / len(stats["action_stats"]))

    print(
        f"Human-{game_type}, on average, {np.mean(act_with_f_per_inst)}% of actions per instruction have feedback"
    )
    for action_type, stats in action_stats.items():
        total_actions = stats["with"] + stats["without"]
        print(f"Human-{game_type}, there were {total_actions} {action_type} actions")
        print(
            f"Human-{game_type}, {stats['with'] / total_actions}% of {action_type} actions have feedback"
        )
        print(
            f"Human-{game_type}, if {action_type} actions don't have feedback, {stats['cancelled_out']/stats['without']}% "
            + "of the time, this is due to positive and negative feedback cancelling each other"
        )
        if stats["with"] > 0:
            print(
                f"Human-{game_type}, if {action_type} actions have feedback, they are assigned positive and negative feedback"
                + f" {stats['positive']/stats['with']}% and {stats['negative']/stats['with']}% of the time respectively"
            )
        print(
            f"Human-{game_type}, on average, a {action_type} action is given {np.mean(stats['feedback_count_per'])} feedbacks"
        )


def ReportSetCompletionEfficiency(ids, game_type):
    num_leader_moves = []
    num_follower_moves = []

    for i in ids:
        game = Game.select().where(Game.id == i).get()
        if filter_game(game):
            continue
        if game_type == "human" and game.follower_id is None:
            continue
        if game_type == "ai" and game.follower_id is not None:
            continue

        # Get list of completed sets
        sets = (
            CardSets.select()
            .join(Game)
            .where(CardSets.game == game)
            .order_by(CardSets.id)
        )
        for score, cardset in enumerate(sets):
            # Get the id of the move finishing
            move_id = cardset.move_id

            # Get list of moves between last score and this move
            if score == 0:
                moves = (
                    Move.select()
                    .join(Game)
                    .where(Move.game == game, Move.id <= move_id)
                    .order_by(Move.id)
                )
            else:
                past_move = sets[score - 1].move_id
                moves = (
                    Move.select()
                    .join(Game)
                    .where(Move.game == game, Move.id > past_move, Move.id <= move_id)
                    .order_by(Move.id)
                )

            # Iterate over each move
            leader_moves = 0
            follower_moves = 0
            for move in moves:
                if move.action_code == "DONE":
                    continue

                if move.character_role == "Role.FOLLOWER":
                    follower_moves += 1
                else:
                    leader_moves += 1

            num_leader_moves.append(leader_moves)
            num_follower_moves.append(follower_moves)

    print(
        f"Human-{game_type}, average leader move per set: {np.mean(num_leader_moves)}"
    )
    print(
        f"Human-{game_type}, average follower move per set: {np.mean(num_follower_moves)}"
    )
    print()


def ReportCardPlayerRoleStats(ids, game_type):
    total_cards = 0
    total_follower = 0
    total_follower_deselects = 0
    follower_percentages = []
    follower_deselect_percentages = []

    for i in ids:
        game = Game.select().where(Game.id == i).get()
        if filter_game(game):
            continue
        if game_type == "human" and game.follower_id is None:
            continue
        if game_type == "ai" and game.follower_id is not None:
            continue

        # Get list of card selection events and iterate over them
        card_selections = (
            CardSelections.select()
            .join(Game)
            .where(CardSelections.game == game)
            .order_by(CardSelections.id)
        )

        total_curr_game = 0
        follower_curr_game = 0
        follower_deselects = 0
        for selection in card_selections:
            # Get the associated role
            move_id = selection.move_id
            move = Move.select().join(Game).where(Move.id == move_id).get()

            total_curr_game += 1
            if move.character_role == "Role.FOLLOWER":
                follower_curr_game += 1
                if selection.type == "unselect":
                    follower_deselects += 1

        total_cards += total_curr_game
        total_follower += follower_curr_game
        total_follower_deselects += follower_deselects
        if total_curr_game != 0:
            follower_percentages.append(follower_curr_game / total_curr_game)
        if follower_curr_game != 0:
            follower_deselect_percentages.append(
                follower_deselects / follower_curr_game
            )

    # Report the results
    print(
        f"Human-{game_type}, on average, a follower performs {np.mean(follower_percentages) * 100}% of card"
        + " interactions per game"
    )
    print(
        f"Human-{game_type}, on average, {np.mean(follower_deselect_percentages) * 100}% of card interactions "
        + "in a game by followers are deselections"
    )
    print(
        f"Human-{game_type}, {total_follower / total_cards * 100}% of card interactions are by followers"
    )
    print(
        f"Human-{game_type}, {total_follower_deselects / total_follower * 100}% of follower card interactions "
        + "are deselections"
    )
    print()


def ReportDeselectionRateStats(ids, game_type):
    total_selection = 0
    total_deselects = 0
    deselect_by_follower = 0

    deselection_percentages = []
    deselection_by_follower_percentages = []

    for i in ids:
        game = Game.select().where(Game.id == i).get()
        if filter_game(game):
            continue
        if game_type == "human" and game.follower_id is None:
            continue
        if game_type == "ai" and game.follower_id is not None:
            continue

        # Get list of card selection events and iterate over them
        card_selections = (
            CardSelections.select()
            .join(Game)
            .where(CardSelections.game == game)
            .order_by(CardSelections.id)
        )

        num_selects = len(card_selections)
        num_deselects = 0
        curr_deselect_by_follower = 0
        for selection in card_selections:
            if selection.type == "unselect":
                num_deselects += 1
                move = (
                    Move.select().join(Game).where(Move.id == selection.move_id).get()
                )
                if move.character_role == "Role.FOLLOWER":
                    curr_deselect_by_follower += 1

        total_selection += num_selects
        total_deselects += num_deselects
        deselect_by_follower += curr_deselect_by_follower

        if num_selects != 0:
            deselection_percentages.append(num_deselects / num_selects)
        if num_deselects != 0:
            deselection_by_follower_percentages.append(
                curr_deselect_by_follower / num_deselects
            )

    # Reporting results
    print(
        f"Human-{game_type}, on average, {np.mean(deselection_percentages) * 100}% of card selections "
        + "are deselection actions"
    )
    print(
        f"Human-{game_type}, on average, {np.mean(deselection_by_follower_percentages) * 100}% of deselections "
        + "in a game were performed by followers"
    )
    print(
        f"Human-{game_type}, {total_deselects / total_selection * 100}% of card interactions are deselections."
    )
    print(
        f"Human-{game_type}, {deselect_by_follower / total_deselects * 100}% of deselections are by followers."
    )
    print()


def ReportInstructionChaining(ids, game_type):
    num_chaining_overall = []
    avg_chaining_per_game = []

    for i in ids:
        game = Game.select().where(Game.id == i).get()
        if filter_game(game):
            continue
        if game_type == "human" and game.follower_id is None:
            continue
        if game_type == "ai" and game.follower_id is not None:
            continue

        instructions = (
            Instruction.select()
            .join(Game)
            .where(Instruction.game == game)
            .order_by(Instruction.id)
        )

        curr_game_chaining = []
        start_turn = -1
        num_instruction = 0
        for instruction in instructions:
            if instruction.turn_issued != start_turn:
                if start_turn != -1:
                    curr_game_chaining.append(num_instruction)

                start_turn = instruction.turn_issued
                num_instruction = 1
            else:
                num_instruction += 1
        if start_turn != -1:
            curr_game_chaining.append(num_instruction)

        num_chaining_overall += curr_game_chaining
        if len(curr_game_chaining) != 0:
            avg_chaining_per_game.append(np.mean(curr_game_chaining))

    # Report results
    print(
        f"Human-{game_type}, within a game a leader issues chains of {np.mean(avg_chaining_per_game)} instructions"
        + "when they issue instructions"
    )
    print(
        f"Human-{game_type}, when a leader issues instructions, they issue chains of {np.mean(num_chaining_overall)}"
        + " instructions on average"
    )
    print(
        f"Human-{game_type}, the greatest number of instructions a leader issued in one turn was {max(num_chaining_overall)}"
    )
    print()


def ReportInvalidGames(ids, game_type):
    num_games = 0
    num_short = 0
    num_too_many_term = 0
    num_lost = 0
    num_invalid = 0

    for i in ids:
        game = Game.select().where(Game.id == i).get()
        if filter_game(game):
            continue
        if game_type == "human" and game.follower_id is None:
            continue
        if game_type == "ai" and game.follower_id is not None:
            continue
        instructions = (
            Instruction.select()
            .join(Game)
            .where(Instruction.game == game)
            .order_by(Instruction.id)
        )
        num_games += 1

        is_short = short_game(game)
        is_lost = follower_got_lost(instructions)
        is_cancelled = high_percent_cancelled_instructions(instructions)

        if is_short:
            num_short += 1
        if is_lost:
            num_lost += 1
        if is_cancelled:
            num_too_many_term += 1
        if is_short or is_lost or is_cancelled:
            num_invalid += 1

    # Report results
    print(
        f"There are {num_games} human-{game_type} games. {num_invalid / num_games * 100}% of these are invalid"
    )
    print(
        f"Short games: {num_short / num_games * 100}%, follower got lost: {num_lost / num_games * 100}%, "
        + f"too many instructions terminated: {num_too_many_term / num_games * 100}%"
    )
    print()


def ReportLeaderFeedbackRates(ids):
    leader_to_rates = get_leader_to_rates(ids)
    report_overall_leader_feedback_percentage(leader_to_rates)
    passed_leaders_2 = report_leaders_who_maintained_bonus_under_current_scheme(
        leader_to_rates
    )


def report_overall_leader_feedback_percentage(leader_to_rates):
    # Check how many leaders give feedback for over 75% of instructions
    num_over_75 = 0
    num_over_75_2_games = 0
    over_2_games = 0
    passed_leaders = []
    for leader, l_dict in leader_to_rates.items():
        if len(l_dict["rates"]) > 2:
            over_2_games += 1

        overall_with = 0
        overall_count = 0
        for with_feedback, total_in_game, _ in l_dict["rates"]:
            overall_with += with_feedback
            overall_count += total_in_game
        if overall_count > 0 and overall_with / overall_count >= 0.75:
            num_over_75 += 1
            if len(l_dict["rates"]) > 2:
                num_over_75_2_games += 1
                passed_leaders.append(leader)

    print(
        f"{num_over_75}/{len(leader_to_rates)} leaders gave feedback to over 75% of their instructions"
    )
    print(
        f"{num_over_75_2_games}/{over_2_games} of leaders who played more than 2 games gave feedback to over 75% of their instructions"
    )
    return passed_leaders


def report_leaders_who_maintained_bonus_under_current_scheme(leader_to_rates):
    over_2_games = 0
    passed_leaders = []

    for leader, l_dict in leader_to_rates.items():
        if len(l_dict["rates"]) <= 2:
            continue

        print(l_dict["rates"])
        over_2_games += 1
        bad_in_sequence = 0
        failed = False
        for _, _, rate in l_dict["rates"]:
            if rate < 0.75:
                bad_in_sequence += 1
            else:
                bad_in_sequence = 0

            if bad_in_sequence == 2:
                failed = True
                break
        if not failed:
            passed_leaders.append(leader)

    print(
        f"{len(passed_leaders)}/{over_2_games} leaders maintained their bonus in the current scheme"
    )
    return passed_leaders


def get_leader_to_rates(ids):
    leader_to_rates = {}
    for i in ids:
        game = Game.select().where(Game.id == i).get()
        if filter_game(game):
            continue

        # Record the leader
        leader = game.leader_id
        if leader not in leader_to_rates:
            leader_entry = Worker.select().where(Worker.id == leader).get()
            leader_to_rates[leader] = {"hash": leader_entry.hashed_id, "rates": []}

        instructions = Instruction.select().join(Game).where(Instruction.game == game)
        active_instructions = get_active_instructions(instructions)
        if len(active_instructions) == 0:
            continue

        with_feedback = 0
        for instruction in active_instructions:
            feedbacks = (
                LiveFeedback.select()
                .join(Game)
                .where(LiveFeedback.instruction_id == instruction.id)
            )
            if len(feedbacks) > 0:
                with_feedback += 1
        leader_to_rates[leader]["rates"].append(
            (
                with_feedback,
                len(active_instructions),
                with_feedback / len(active_instructions),
            )
        )

    return leader_to_rates


def ReportExecutionLengthCap(ids):
    num_instructions = 0
    num_below_cap = 0
    for i in ids:
        game = Game.select().where(Game.id == i).get()
        if filter_game(game):
            continue

        # Get the associated instructions
        instructions = Instruction.select().join(Game).where(Instruction.game == game)
        active_instructions = get_active_instructions(instructions)
        for inst in active_instructions:
            num_instructions += 1
            moves = (
                Move.select()
                .join(Game)
                .where(
                    Move.instruction_id == inst.id,
                    Move.character_role == "Role.FOLLOWER",
                )
                .order_by(Move.id)
            )
            if len(moves) <= 22:
                num_below_cap += 1

    print(
        f"Executions with a length less than or equal to the cap form {num_below_cap / num_instructions * 100}% of instructions"
    )


def main(
    command,
    to_id="",
    from_id="",
    id_file="",
    config_filepath="server/config/server-config.yaml",
):
    if command == "help":
        PrintUsage()
        return

    # Setup the sqlite database used to record game actions.
    cfg = config.ReadConfigOrDie(config_filepath)
    print(f"Reading database from {cfg.database_path()}")
    base.SetDatabase(cfg)
    base.ConnectDatabase()
    base.CreateTablesIfNotExists(defaults_db.ListDefaultTables())

    # Individual statistics commands
    if command == "game_counts":
        ids = get_list_of_ids(to_id, from_id, id_file)
        ReportGameTypes(ids)
    elif command == "follower_qualification_speed":
        ids = get_list_of_ids(to_id, from_id, id_file)
        ReportFollowerQualificationSpeed(ids)
    elif command == "basic_stats":
        ids = get_list_of_ids(to_id, from_id, id_file)
        ReportBasicStats(ids, "ai")
        ReportBasicStats(ids, "human")
        ReportBasicStats(ids, "overall")
    elif command == "instruction_stats":
        ids = get_list_of_ids(to_id, from_id, id_file)
        ReportInstructionStats(ids, "ai")
        ReportInstructionStats(ids, "human")
        ReportInstructionStats(ids, "overall")
    elif command == "termination_stats":
        ids = get_list_of_ids(to_id, from_id, id_file)
        ReportTerminationStats(ids, "ai")
        ReportTerminationStats(ids, "human")
        ReportTerminationStats(ids, "overall")
    elif command == "basic_feedback_stats":
        ids = get_list_of_ids(to_id, from_id, id_file)
        ReportFeedbackStats(ids, "ai")
        ReportFeedbackStats(ids, "human")
        ReportFeedbackStats(ids, "overall")
    elif command == "feedback_action_stats":
        ids = get_list_of_ids(to_id, from_id, id_file)
        ReportFeedbackActionStats(ids, "ai")
        ReportFeedbackActionStats(ids, "human")
        ReportFeedbackActionStats(ids, "overall")
    elif command == "set_completion_efficiency":
        ids = get_list_of_ids(to_id, from_id, id_file)
        ReportSetCompletionEfficiency(ids, "ai")
        ReportSetCompletionEfficiency(ids, "human")
        ReportSetCompletionEfficiency(ids, "overall")
    elif command == "card_role_percentage":
        ids = get_list_of_ids(to_id, from_id, id_file)
        ReportCardPlayerRoleStats(ids, "ai")
        ReportCardPlayerRoleStats(ids, "human")
        ReportCardPlayerRoleStats(ids, "overall")
    elif command == "deselection_rate_stats":
        ids = get_list_of_ids(to_id, from_id, id_file)
        ReportDeselectionRateStats(ids, "ai")
        ReportDeselectionRateStats(ids, "human")
        ReportDeselectionRateStats(ids, "overall")
    elif command == "instruction_chaining_amount":
        ids = get_list_of_ids(to_id, from_id, id_file)
        ReportInstructionChaining(ids, "ai")
        ReportInstructionChaining(ids, "human")
        ReportInstructionChaining(ids, "overall")
    elif command == "num_invalid_games":
        ids = get_list_of_ids(to_id, from_id, id_file)
        ReportInvalidGames(ids, "ai")
        ReportInvalidGames(ids, "human")
        ReportInvalidGames(ids, "overall")
    elif command == "leader_feedback_rates":
        ids = get_list_of_ids(to_id, from_id, id_file)
        ReportLeaderFeedbackRates(ids)
    elif command == "execution_length_cap":
        ids = get_list_of_ids(to_id, from_id, id_file)
        ReportExecutionLengthCap(ids)
    else:
        PrintUsage()


if __name__ == "__main__":
    fire.Fire(main)
