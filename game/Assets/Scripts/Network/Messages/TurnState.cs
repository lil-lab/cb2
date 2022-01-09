using System;
using UnityEngine;


namespace Network
{
    [Serializable]
    public class TurnState
    {
        public Role Turn;  // Who's turn it is.
        public int MovesRemaining;  // How many moves the player has left in this turn.
        public int TurnsLeft;  // How many turns the game has left.
        public string TurnEnd;  // Time when the current turn began.
        public string GameStart;  // Time when the game began.
        public int SetsCollected;
        public int Score;
        public bool GameOver;

        public string ScoreString(DateTime transmitTime)
        {
            DateTime game_start = DateTime.Parse(GameStart, null, System.Globalization.DateTimeStyles.RoundtripKind);
            TimeSpan gameDuration = transmitTime - game_start;
            return "Time taken: " + gameDuration.ToString(@"mm\:ss") + "\nSets Collected: " + SetsCollected + "\nScore: " + Score;
        }

        public string ShortStatus(DateTime transmitTime, Role role)
        {
            DateTime turn_end = DateTime.Parse(TurnEnd, null, System.Globalization.DateTimeStyles.RoundtripKind);
            TimeSpan timeLeftInTurn = (role == Turn) ? turn_end - transmitTime : new TimeSpan(0);
            int movesRemaining = (role == Turn) ? MovesRemaining : 0;
            int turnsLeft = Math.Max(TurnsLeft, 0);  // if -1 then game is over, display zero to be more tidy.
            return "Score: " + Score + "\tTime Left in turn: " + timeLeftInTurn.ToString(@"mm\:ss") + "\nMoves this turn: " + movesRemaining + "\tTurns Left: " + TurnsLeft;
        }
    }

    [Serializable]
    public class TurnComplete
    {
    }
}