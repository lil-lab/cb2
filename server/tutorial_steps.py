from messages.tutorials import TutorialStep, Indicator, Instruction, Tooltip, TooltipType, LEADER_TUTORIAL, FOLLOWER_TUTORIAL, FollowerActions
from hex import HecsCoord

import logging

from enum import Enum

TOOLTIP_X = 0.3
TOOLTIP_Y = 0.3

logger = logging.getLogger

LEADER_TUTORIAL_STEPS = [
    TutorialStep(
        [],
        Tooltip("",
                "Welcome leader! This tutorial will walk you through the CerealBar game (press \"shift\" to continue)",
                TooltipType.UNTIL_DISMISSED),
        None,
    ),
    TutorialStep(
        [],
        Tooltip("",
                "You are the leader (blue circle). You see the entire map, decide card sets to collect with the follower (yellow circle), collect cards, and give the follower instructions. (press \"shift\" to continue)",
                TooltipType.UNTIL_DISMISSED),
        None,
    ),
    TutorialStep(
        [],
        Tooltip("CAMERA_BUTTON",
                "You have two camera views. Toggle them with the \"camera\" button (or the \"C\" key). Try it now.",
                TooltipType.UNTIL_CAMERA_TOGGLED),
        None,
    ),
    TutorialStep(
        [],
        Tooltip("SCORE",
                "Game information is on the left panel. You have 60 seconds per turn. (press \"shift\" to continue)",
                TooltipType.UNTIL_DISMISSED),
        None,
    ),
    TutorialStep(
        [],
        Tooltip("CAMERA_BUTTON",
                "You can drag the camera view with the mouse or the buttons A/D. Toggle the camera again to return to the first view.",
                TooltipType.UNTIL_CAMERA_TOGGLED),
        None,
    ),
    TutorialStep(
        [],
        Tooltip("FOLLOWER_VIEW",
                "The top-left window shows what the follower sees. Cards are covered with \"?\" and visibility is limited! (press \"shift\" to continue)",
                TooltipType.UNTIL_DISMISSED),
        None,
    ),
    TutorialStep(
        [],
        Tooltip("",
                "The follower view is limited, so consider this when writing instructions. They can't see like you! (press \"shift\" to continue)",
                TooltipType.UNTIL_DISMISSED),
        None,
    ),
    TutorialStep(
        [Indicator(HecsCoord(0, 2, 0)), Indicator(HecsCoord(1, 0, 1)), Indicator(HecsCoord(0, 3, 2))],
        Tooltip("",
                "First, let's plan to collect this set of three cards. Each color, shape, and count is unique, so this set will give us a point. (press \"shift\" to continue)",
                TooltipType.UNTIL_DISMISSED),
        None,
    ),
    TutorialStep(
        [],
        Tooltip("MessageInputField",
                "Let's write an instruction! Use the text box in the bottom-left (or press \"T\"). Tell them to turn left and grab the middle card in the trio of cards.",
                TooltipType.UNTIL_MESSAGE_SENT),
        None,
    ),
    TutorialStep(
        [],
        Tooltip("INSTRUCTIONS",
                "The follower only sees the current instructions, but you can queue multiple instructions, so they can use their steps efficiently. (press \"shift\" to continue)",
                TooltipType.UNTIL_DISMISSED),
        None,
    ),
    TutorialStep(
        [],
        Tooltip("",
                "Tell the follower to get the card at the edge of the map. This card will be straight ahead of them once they finish the previous instruction.",
                TooltipType.UNTIL_MESSAGE_SENT),
        None,
    ),
    TutorialStep(
        [Indicator(HecsCoord(1, 0, 1))],
        Tooltip("",
                "Now let's do some stuff ourselves. Pick up the two black diamonds ahead of you",
                TooltipType.UNTIL_INDICATOR_REACHED),
        None,
    ),
    TutorialStep(
        [],
        Tooltip("END_TURN_PANEL",
                "Finish your turn by pressing \"End Turn\" or the key \"N\".",
                TooltipType.UNTIL_TURN_ENDED),
        None,
    ),
    TutorialStep(
      [],
      Tooltip("", "Now it's the follower's turn! Wait for them to move...",
      TooltipType.FOLLOWER_TURN),
      None,
      [FollowerActions.TURN_LEFT, FollowerActions.TURN_LEFT, FollowerActions.FORWARDS],
    ),
    TutorialStep(
      [],
      Tooltip("", "", 
      TooltipType.FOLLOWER_TURN),
      None,
      [FollowerActions.INSTRUCTION_DONE],
    ),
    TutorialStep(
        [],
        Tooltip("",
                "The follower completed one instruction. See how it's marked as done. They now get the second instruction. They still have steps, so they can start it (press \"shift\" continue)",
                TooltipType.UNTIL_DISMISSED),
        None,
    ),

    TutorialStep(
      [],
      Tooltip("", "Now it's the follower's turn! Wait for them to move...",
      TooltipType.FOLLOWER_TURN),
      None,
      [FollowerActions.TURN_LEFT, FollowerActions.FORWARDS, FollowerActions.FORWARDS],
    ),
    TutorialStep(
        [],
        Tooltip(
            "CANCEL_BUTTON",
            "Oh, no! The follower is confused. Let's stop them. Hold the \"Interrupt\" button for 1 second.",
            TooltipType.UNTIL_TURN_ENDED),
        None
    ),
    TutorialStep(
        [Indicator(HecsCoord(0, 2, 0))],
        Tooltip(
            "MessageInputField",
            "Now let's rephrase our instruction so the follower will turn around and grab the green square card.",
            TooltipType.UNTIL_MESSAGE_SENT),
        None
    ),
    TutorialStep(
        [],
        Tooltip(
            "END_TURN_PANEL",
            "Don't forget to end your turn!",
            TooltipType.UNTIL_TURN_ENDED),
        None
    ),
    TutorialStep(
      [],
      Tooltip("", "It's the follower's turn...", TooltipType.FOLLOWER_TURN),
      None,
      [FollowerActions.TURN_RIGHT, FollowerActions.TURN_RIGHT, FollowerActions.FORWARDS, FollowerActions.TURN_RIGHT, FollowerActions.FORWARDS, FollowerActions.TURN_LEFT, FollowerActions.FORWARDS],
    ),
    TutorialStep(
      [],
      Tooltip("", "It's the follower's turn...", TooltipType.FOLLOWER_TURN),
      None,
      [FollowerActions.INSTRUCTION_DONE, FollowerActions.END_TURN],
    ),
    TutorialStep(
        [Indicator(HecsCoord(0, 2, 2))],
        Tooltip("",
                "Good job! The goal is to collect as many sets of 3 cards as"
                " possible before you run out of turns. Let's do another one. Try picking up the two"
                " pink triangles near where you started.",
                TooltipType.UNTIL_INDICATOR_REACHED),
        None
    ),
    TutorialStep(
        [],
        Tooltip("",
                "Each card in a set must have a unique color, shape, and number of items. If you"
                " violate this rule, the cards turn red! Let's try it (Shift to continue).",
                TooltipType.UNTIL_DISMISSED),
        None
    ),
    TutorialStep(
        [Indicator(HecsCoord(1, 1, 3))],
        Tooltip("",
                "Go step on the two blue crosses. This isn't unique, since we already have a card with 2 shapes.",
                TooltipType.UNTIL_INDICATOR_REACHED),
        None
    ),
    TutorialStep(
        [Indicator(HecsCoord(1, 1, 3))],
        Tooltip("",
                "Now to fix the problem, let's unselect the two blue crosses. Step off and back onto the card. now!",
                TooltipType.UNTIL_INDICATOR_REACHED),
        None
    ),
    TutorialStep(
        [Indicator(HecsCoord(0, 3, 2))],
        Tooltip("",
                "Continue with the set. Go to the next card, the 3 blue diamonds nearby...", TooltipType.UNTIL_INDICATOR_REACHED),
        None
    ),
    TutorialStep(
        [],
        Tooltip("",
                "Ask the follower to grab the last card, behind them at the corner of the map.", TooltipType.UNTIL_MESSAGE_SENT),
        None
    ),
    TutorialStep(
        [],
        Tooltip("END_TURN_PANEL",
                "Now end your turn to give the follower a chance to move.", TooltipType.UNTIL_TURN_ENDED),
        None
    ),
    TutorialStep(
      [],
      Tooltip("", "It's the follower's turn...", TooltipType.FOLLOWER_TURN),
      None,
      [FollowerActions.TURN_LEFT, FollowerActions.TURN_LEFT, FollowerActions.TURN_LEFT, FollowerActions.FORWARDS, FollowerActions.FORWARDS, FollowerActions.FORWARDS, FollowerActions.TURN_RIGHT, FollowerActions.FORWARDS, FollowerActions.FORWARDS],
    ),
    TutorialStep(
      [],
      Tooltip("", "It's the follower's turn...", TooltipType.FOLLOWER_TURN),
      None,
      [FollowerActions.INSTRUCTION_DONE],
    ),
    TutorialStep(
        [],
        Tooltip("SCORE",
                "Good work! Your score is counted and displayed in the bottom"
                " left screen (Shift to continue).", TooltipType.UNTIL_DISMISSED),
        None
    ),
    TutorialStep(
        [],
        Tooltip("SCORE",
                "Each set will give you more turns to collect even more sets."
                " The higher your score, the more credit you will receive at the"
                " end of the game (Shift to continue).",
                TooltipType.UNTIL_DISMISSED),
        None
    ),
    TutorialStep(
        [],
        Tooltip("",
                "Remember to leave useful instructions for the follower. You can "
                "see the whole board, but the follower gets twice as many moves "
                "per turn. By working together, you can get a higher score! "
                "(Shift to continue).", TooltipType.UNTIL_DISMISSED),
        None
    ),
    TutorialStep(
        [],
        Tooltip("",
                "Once you've exhausted your moves, you have the rest of your "
                "turn to leave instructions for the follower (Shift to "
                "continue).", TooltipType.UNTIL_DISMISSED),
        None
    ),
    TutorialStep(
        [],
        Tooltip("",
                "If you haven't left any instructions for the follower, their "
                "turn will be skipped. In real games, you have a minute per turn. Make sure to leave instructions before the "
                "time for your turn runs out! (Shift to continue).",
                TooltipType.UNTIL_DISMISSED),
        None
    ),
    TutorialStep(
        [],
        Tooltip("",
                "Good luck out there! (Shift to continue).",
                TooltipType.UNTIL_DISMISSED),
        None
    ),
]

FOLLOWER_TUTORIAL_STEPS = [
    TutorialStep(
        None,
        Tooltip("",
                "Welcome to the follower tutorial. We'll walk "
                "you through the rules of Cerealbar and how to "
                "play the follower role (Shift to continue).",
                TooltipType.UNTIL_DISMISSED),
        None,
    ),
    TutorialStep(
        Indicator(HecsCoord(0, 1, 1)),
        Tooltip("",
                "To move around, use the arrow keys. Try moving to the indicator"
                " on the screen.", TooltipType.UNTIL_INDICATOR_REACHED),
        None,
    ),
    TutorialStep(
        None,
        Tooltip("",
                "Good! In this game, you and the leader are trying to collect"
                " cards. You collect a card by stepping on it (Shift to"
                " continue).", TooltipType.UNTIL_DISMISSED),
        None,
    ),
    TutorialStep(
        None,
        Tooltip("",
                "As the follower, your primary responsibility is to "
                "follow the instructions of the leader (Shift to continue).",
                TooltipType.UNTIL_DISMISSED),
        None,
    ),
    TutorialStep(
        None,
        Tooltip("",
                "Since you're the follower, you cannot see card patterns. Cards are covered with a \"?\" (Shift to continue).",
                TooltipType.UNTIL_DISMISSED),
        None,
    ),
    TutorialStep(
        Indicator(HecsCoord(0, 1, 3)),
        Tooltip("INSTRUCTIONS",
                "You've received your first instruction. Follow it, then click"
                " \"Done\" in the top left.",
                TooltipType.UNTIL_OBJECTIVES_COMPLETED),
        Instruction("Go up the steps and stand on the first card you see on the platform."),
    ),
    TutorialStep(
        None,
        Tooltip("INSTRUCTIONS",
                "Great! Don't forget to click on \"Done\" once you finish an"
                " instruction. You won't be able to proceed until then (Shift to"
                " continue).", TooltipType.UNTIL_DISMISSED),
        None,
    ),
    TutorialStep(
        None,
        Tooltip("",
                "Follow the instructions...",
                TooltipType.UNTIL_OBJECTIVES_COMPLETED),
        Instruction("Turn around and go back down the steps. Move onto the card"
                    " on the right at the base of the mountain.")
    ),
    TutorialStep(
        None,
        Tooltip("",
                "Follow the instructions...",
                TooltipType.UNTIL_OBJECTIVES_COMPLETED),
        Instruction("Behind you, near where you started, you'll see a cluster of 3 cards in a V-shape. Move onto the closest card.") ),
    TutorialStep(
        None,
        Tooltip("",
                "Follow the instructions... To unselect a card, step off of it"
                " and then back onto it.",
                TooltipType.UNTIL_OBJECTIVES_COMPLETED),
        Instruction("Oops, sorry I messed up! Can you unselect that card by"
                    " walking off it and then back onto it?") ),
    TutorialStep(
        None,
        Tooltip("",
                "Last instruction!",
                TooltipType.UNTIL_OBJECTIVES_COMPLETED),
        Instruction("Now finish up the set by picking up the center card in that v-shaped group of 3 cards."), ),
    TutorialStep(
        None,
        Tooltip("SCORE",
                "Look at that! You collected a set of 3 cards! Each is unique in "
                "color, shape, and quantity. You've been rewarded 1 point. Your "
                "score is displayed in the bottom left window (Shift to continue).",
                TooltipType.UNTIL_DISMISSED),
        None,
    ),
    TutorialStep(
        None,
        Tooltip("",
                "In a real game, you only have a certain number of movements per "
                "turn, use them wisely! Your remaining moves are shown in the "
                "bottom left. (Shift to continue).",
                TooltipType.UNTIL_DISMISSED),
        None,
    ),
    TutorialStep(
        None,
        Tooltip("",
                "By the way, if you're not sure what to do, try your best to "
                "follow the instructions. If you're really not sure, mark the "
                "instruction as done and let the leader clarify on the next "
                "turn. (Shift to continue).",
                TooltipType.UNTIL_DISMISSED),
        None,
    ),
    TutorialStep(
        None,
        Tooltip("",
                "As the follower, if you run out of moves or instructions, your "
                "turn will end immediately (Shift to continue).",
                TooltipType.UNTIL_DISMISSED),
        None,
    ),
    TutorialStep(
        None,
        Tooltip("",
                "Remember, follow the instructions. Don't go off on your own! "
                "The leader can see the entire board, but you can only see what's "
                "around you. As the follower, you can move twice as far as the "
                "leader per turn. Work together to succeed! (Shift to continue).",
                TooltipType.UNTIL_DISMISSED), None,
    ),
    TutorialStep(
        None,
        Tooltip("",
                "Best of luck on your first game! (Shift to finish).",
                TooltipType.UNTIL_DISMISSED),
        None,
    ),
]

def LoadTutorialSteps(tutorial_name):
    if tutorial_name == LEADER_TUTORIAL:
        return LEADER_TUTORIAL_STEPS
    elif tutorial_name == FOLLOWER_TUTORIAL:
        return FOLLOWER_TUTORIAL_STEPS
    else:
        logger.warn("Unrecognized tutorial name.")
        return []
