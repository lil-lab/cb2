from messages.tutorials import TutorialStep, Indicator, Instruction, Tooltip, TooltipType, LEADER_TUTORIAL, FOLLOWER_TUTORIAL
from hex import HecsCoord

import logging

TOOLTIP_X = 0.3
TOOLTIP_Y = 0.3

logger = logging.getLogger

LEADER_TUTORIAL_STEPS = [
    TutorialStep(
        None,
        Tooltip("",
                "Welcome to the leader tutorial. We'll walk "
                "you through the rules of Cerealbar and how to "
                "play the leader role. Press Shift to proceed.",
                TooltipType.UNTIL_DISMISSED),
        None,
    ),
    TutorialStep(
        None,
        Tooltip("",
                "You're playing as the Leader (blue circle). As the Leader, you"
                " can see the entire map! Toggle your map view by hitting 'C' on"
                " your keyboard.", TooltipType.UNTIL_CAMERA_TOGGLED),
        None
    ),
    TutorialStep(
        None,
        Tooltip("SCORE",
                "In the bottom left, there is the Time Left display. During the"
                " game, you are given 60 seconds per turn as the leader (Shift to"
                " continue).", TooltipType.UNTIL_DISMISSED),
        None
    ),
    TutorialStep(
        None,
        Tooltip("SCORE",
                "In that same box, the game shows you the number of moves left"
                " in the turn, and the number of turns before game over. Use them"
                " wisely in the game! (Shift to continue)",
                TooltipType.UNTIL_DISMISSED),
        None
    ),
    TutorialStep(
        None,
        Tooltip("",
                "Toggle the Camera again to return to the original view!"
                " Do you remember how to do this? (Hit 'C' again to toggle the"
                " Camera)", TooltipType.UNTIL_CAMERA_TOGGLED),
        None
    ),
    TutorialStep(
        None,
        Tooltip("",
                "By the way, you can move the camera by clicking and dragging"
                " the mouse (Or, use A/D) (Shift to continue).",
                TooltipType.UNTIL_DISMISSED),
        None
    ),
    TutorialStep(
        None,
        Tooltip("MessageInputField",
                "The yellow circle is indicating the Follower. You can send the"
                " Follower commands using the text box in the bottom left corner."
                " Try sending something now!", TooltipType.UNTIL_MESSAGE_SENT),
        None
    ),
    TutorialStep(
        None,
        Tooltip("INSTRUCTIONS",
                "For now, the Follower won't do anything, but in the game, once"
                " you end your turn, the Follower will see your instruction and"
                " get a chance to move (Shift to continue).",
                TooltipType.UNTIL_DISMISSED),
        None
    ),
    TutorialStep(
        Indicator(HecsCoord(0, 1, 3)),
        Tooltip("",
                "To move the Leader, use the arrow keys! Walk to the 1 orange"
                " star card on the hill nearby and move onto it.",
                TooltipType.UNTIL_INDICATOR_REACHED),
        None
    ),
    TutorialStep(
        Indicator(HecsCoord(1, 0, 1)),
        Tooltip("",
                "Good job! The goal is to collect as many sets of 3 cards as"
                " possible before you run out of turns. Try picking up the two"
                " diamonds at the bottom of the hill behind you.",
                TooltipType.UNTIL_INDICATOR_REACHED),
        None
    ),
    TutorialStep(
        Indicator(HecsCoord(0, 2, 2)),
        Tooltip("",
                "Now, look for the two blue plusses with an indicator circle and"
                " grab them too.", TooltipType.UNTIL_INDICATOR_REACHED),
        None
    ),
    TutorialStep(
        None,
        Tooltip("",
                "Uh oh, looks like we picked up a bad set! Each card in a set"
                " must have a unique color, shape, and number of items. If you"
                " violate this rule, the cards turn red! (Shift to continue).",
                TooltipType.UNTIL_DISMISSED),
        None
    ),
    TutorialStep(
        Indicator(HecsCoord(0, 2, 2)),
        Tooltip("",
                "To deselect a card, walk off the card and onto it again. Try it"
                " now!", TooltipType.UNTIL_INDICATOR_REACHED),
        None
    ),
    TutorialStep(
        Indicator(HecsCoord(1, 2, 1)),
        Tooltip("",
                "Now try collecting your first set. Go to the final card, the 3"
                " pink triangles nearby...", TooltipType.UNTIL_SET_COLLECTED),
        None
    ),
    TutorialStep(
        None,
        Tooltip("SCORE",
                "Good work! Your score is counted and displayed in the bottom"
                " left screen (Shift to continue).", TooltipType.UNTIL_DISMISSED),
        None
    ),
    TutorialStep(
        None,
        Tooltip("SCORE",
                "Each set will give you more turns to collect even more sets."
                " The higher your score, the more credit you will receive at the"
                " end of the game (Shift to continue).",
                TooltipType.UNTIL_DISMISSED),
        None
    ),
    TutorialStep(
        None,
        Tooltip("",
                "Complete two more sets to finish the tutorial.",
                TooltipType.UNTIL_SET_COLLECTED),
        None
    ),
    TutorialStep(
        None,
        Tooltip("",
                "One more set!",
                TooltipType.UNTIL_SET_COLLECTED),
        None
    ),
    TutorialStep(
        None,
        Tooltip("",
                "Nice!!! You've completed the tutorial! Here are some parting words (Shift to continue).",
                TooltipType.UNTIL_DISMISSED),
        None
    ),
    TutorialStep(
        None,
        Tooltip("",
                "Remember to leave useful instructions for the follower. You can "
                "see the whole board, but the follower gets twice as many moves "
                "per turn. By working together, you can get a higher score! "
                "(Shift to continue).", TooltipType.UNTIL_DISMISSED),
        None
    ),
    TutorialStep(
        None,
        Tooltip("",
                "Once you've exhausted your moves, you have the rest of your "
                "turn to leave instructions for the follower. (Shift to "
                "continue).", TooltipType.UNTIL_DISMISSED),
        None
    ),
    TutorialStep(
        None,
        Tooltip("",
                "If you haven't left any instructions for the follower, their "
                "turn will be skipped. Make sure to leave instructions before the "
                "time for your turn runs out! As the leader, you have a minute "
                "per turn. " "(Shift to continue).",
                TooltipType.UNTIL_DISMISSED),
        None
    ),
    TutorialStep(
        None,
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
                "play the follower role. Press Shift to proceed.",
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
        Indicator(HecsCoord(0, 1, 3)),
        Tooltip("INSTRUCTIONS",
                "You've received your first instruction. Follow it, then click"
                " \"Done\" in the top left.",
                TooltipType.UNTIL_OBJECTIVES_COMPLETED),
        Instruction("Move onto the orange star on the hill next to you."),
    ),
    TutorialStep(
        None,
        Tooltip("",
                "Great! Let's see if you can collect a set of 3 cards. (Shift to"
                " continue).", TooltipType.UNTIL_DISMISSED),
        None,
    ),
    TutorialStep(
        None,
        Tooltip("INSTRUCTIONS",
                "Don't forget to click on \"Done\" once you finish an"
                " instruction. You won't be able to proceed until then (Shift to"
                " continue).", TooltipType.UNTIL_DISMISSED),
        None,
    ),
    TutorialStep(
        Indicator(HecsCoord(1, 0, 1)),
        Tooltip("INSTRUCTIONS",
                "Follow the instructions...",
                TooltipType.UNTIL_OBJECTIVES_COMPLETED),
        Instruction("Turn around and go back down the mountain. Move onto the two"
                    " diamonds on the right at the base of the mountain.") ),
    TutorialStep(
        Indicator(HecsCoord(0, 2, 2)),
        Tooltip("INSTRUCTIONS",
                "Follow the instructions...",
                TooltipType.UNTIL_OBJECTIVES_COMPLETED),
        Instruction("Behind you, look for the two blue plusses near where you"
                    " started.") ),
    TutorialStep(
        None,
        Tooltip("",
                "Uh oh, looks like we picked up a bad set! Each card in a set"
                " must have a different color, shape, and number of items. If you"
                " violate this rule, the cards turn red! (Shift to continue).",
                TooltipType.UNTIL_DISMISSED),
        None
    ),
    TutorialStep(
        Indicator(HecsCoord(0, 2, 2)),
        Tooltip("",
                "To deselect a card, walk off the card and onto it again. Try it"
                " now!", TooltipType.UNTIL_INDICATOR_REACHED),
        None
    ),
    TutorialStep(
        Indicator(HecsCoord(1, 2, 1)),
        Tooltip("INSTRUCTIONS",
                "Last instruction!",
                TooltipType.UNTIL_OBJECTIVES_COMPLETED),
        Instruction("Now finish up the set by picking up the 3 pink triangles"
                    " next to you."), ),
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
        Tooltip("SCORE",
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