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
                "REPEATED FOR CLARITY: The follower view is limited, so consider this when writing instructions. They CAN NOT see card patterns! (press \"shift\" to continue)",
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
                "Let’s write an instruction! Use the environment to describe to the follower what to do, including the lakes, mountains, grass, snow, paths, trees, houses, lights, rocks, etc” (shift to continue)",
                TooltipType.UNTIL_DISMISSED),
        None,
    ),
    TutorialStep(
        [],
        Tooltip("MessageInputField",
                "Use the text box in the bottom-left (or press “T”). Tell them to turn left and grab the middle card in the trio of cards.",
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
        [Indicator(HecsCoord(0, 2, 0))],
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
                "The follower completed one instruction. See how it's crossed out now? They now see the second instruction. They still have steps, so they can start it (press \"shift\" continue)",
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
            "Oh, no! The follower is confused. Let's stop them. Hold the \"Interrupt\" button for 1 second. It will cancel all queued instructions and end the follower's turn.",
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
                " pink triangles near where you started. Do it yourself!",
                TooltipType.UNTIL_INDICATOR_REACHED),
        None
    ),
    TutorialStep(
        [],
        Tooltip("",
                "Each card in a set must have a unique color, shape, and number of items. If you"
                " violate this rule, the cards turn red! Let's try breaking the rules... (Shift to continue).",
                TooltipType.UNTIL_DISMISSED),
        None
    ),
    TutorialStep(
        [Indicator(HecsCoord(0, 2, 4))],
        Tooltip("",
                "Go step on the two blue crosses. This isn't unique, since we already have a card with 2 shapes.",
                TooltipType.UNTIL_INDICATOR_REACHED),
        None
    ),
    TutorialStep(
        [Indicator(HecsCoord(0, 2, 4))],
        Tooltip("",
                "Oh no! Now to fix the problem, let's unselect the two blue crosses. Step off and back onto the card. now!",
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
        [Indicator(HecsCoord(1, 4, 5))],
        Tooltip("",
                "Ask the follower to grab the last card. Instruct them to turn around and follow the road to the end, then grab the first card on the snowy mountain.", TooltipType.UNTIL_MESSAGE_SENT),
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
      [FollowerActions.TURN_LEFT, FollowerActions.TURN_LEFT, FollowerActions.TURN_LEFT, FollowerActions.FORWARDS, FollowerActions.FORWARDS, FollowerActions.FORWARDS, FollowerActions.FORWARDS, FollowerActions.TURN_LEFT, FollowerActions.FORWARDS, FollowerActions.TURN_RIGHT, FollowerActions.FORWARDS, FollowerActions.TURN_LEFT, FollowerActions.FORWARDS, FollowerActions.FORWARDS],
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
        [],
        Tooltip("",
                "Welcome follower! This tutorial will walk you through the CerealBar game (press \"shift\" to continue)",
                TooltipType.UNTIL_DISMISSED),
        None,
    ),
    TutorialStep(
        [Indicator(HecsCoord(1, 1, 1))],
        Tooltip("",
                "You move using the arrow keys. Move to the indicator on your right.",
                TooltipType.UNTIL_INDICATOR_REACHED),
        None,
    ),
    TutorialStep(
        [],
        Tooltip("",
                "Your goal is to follow the Leader's instructions. Together, you will collect sets of cards. The Leader sees the patterns on cards and the entire environment, so you just need to follow their instructions (press \"Shift\" to continue).",
                TooltipType.UNTIL_DISMISSED),
        None,
    ),
    TutorialStep(
        [],
        Tooltip("",
                "Remember! Follow the Leader's instructions! DO NOT act on your own! (press \"Shift\" to continue)",
                TooltipType.UNTIL_DISMISSED),
        None,
    ),
    TutorialStep(
        [],
        Tooltip("",
                "When asked to select cards, you do so by stepping on them (press \"Shift\" to continue)",
                TooltipType.UNTIL_DISMISSED),
        None,
    ),
    TutorialStep(
        [Indicator(HecsCoord(0, 1, 4))],
        Tooltip("INSTRUCTION_TITLE_TEXT",
                "You've received your first instruction! Follow it, then click \"Done\" (or the key \"D\") when you are done",
                TooltipType.UNTIL_INDICATOR_REACHED),
        Instruction("Go up the steps ahead, and you'll see two cards on the mountain. Select the card on your left")
    ),
    TutorialStep(
        [],
        Tooltip("SCORE",
                "You only have a few steps per turn, and limited time. Be efficient! Every move and turn counts. Remaining steps and time are shown in the bottom left window (press \"Shift\" to continue)",
                TooltipType.UNTIL_DISMISSED),
        None,
    ),
    TutorialStep(
        [],
        Tooltip("",
                "Follow the instructions... Don't forget to mark them as done when complete!",
                TooltipType.UNTIL_OBJECTIVES_COMPLETED),
        Instruction("Turn around and go back down the steps. Grab the card by the orange house on the right.")
    ),
    TutorialStep(
        [],
        Tooltip("",
                "Follow the instructions... Don't forget to mark them as done when complete!",
                TooltipType.UNTIL_OBJECTIVES_COMPLETED),
        Instruction("Behind you there should be a v-shaped cluster of cards along the road. Grab the closest card in the cluster.")),
    TutorialStep(
        [],
        Tooltip("",
                "Follow the instructions... To unselect a card, step off of it"
                " and then back onto it. Don't forget to mark them as done when complete!",
                TooltipType.UNTIL_OBJECTIVES_COMPLETED),
        Instruction("Oops, I messed up! Deselect the current card by"
                    " walking off it, and then back onto it.") ),
    TutorialStep(
        [],
        Tooltip("",
                "Last instruction! If you followed all the previous instructions, this should result in you collecting a set.",
                TooltipType.UNTIL_SET_COLLECTED),
        Instruction("Pick up the center card in the v-shaped cluster.")),
    TutorialStep(
        [],
        Tooltip("SCORE",
                "Hooray! We collected a set of 3 cards. We received a point, and more turns! Our score and turns left show in the bottom-left window. (press \"Shift\" to continue)",
                TooltipType.UNTIL_DISMISSED),
        None,
    ),
    TutorialStep(
        [],
        Tooltip("",
                "Don't forget to hit the \"Done\" button when you're done with an instruction!",
                TooltipType.UNTIL_OBJECTIVES_COMPLETED),
        None,
    ),
    TutorialStep(
        [],
        Tooltip("",
                "Advice: If you're not sure what to do with an instruction, do your best, and mark the instruction as done to get the next one. (press \"Shift\" to continue)",
                TooltipType.UNTIL_DISMISSED),
        None,
    ),
    TutorialStep(
        [],
        Tooltip("",
                "When you run out of steps or instructions, your turn will automatically end. (press \"Shift\" to continue)",
                TooltipType.UNTIL_DISMISSED),
        None,
    ),
    TutorialStep(
        [],
        Tooltip("",
                "You completed the tutorial. Good luck! (press \"Shift\" to continue)",
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
