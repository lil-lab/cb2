using System;
using UnityEngine;


namespace Network
{
    [Serializable]
    public class TurnState
    {
        public Role turn;  // Who's turn it is.
        public int moves_remaining;  // How many moves the player has left in this turn.
        public int turns_left;  // How many turns the game has left.
        public string turn_end;  // Time when the current turn began.
        public string game_start;  // Time when the game began.
        public int sets_collected;
        public int score;
        public bool game_over;

        public string ScoreString(DateTime transmitTime)
        {
            DateTime game_start_parsed = DateTime.Parse(game_start, null, System.Globalization.DateTimeStyles.RoundtripKind);
            TimeSpan gameDuration = transmitTime - game_start_parsed;
            return "Time taken: " + gameDuration.ToString(@"mm\:ss") + "\nSets Collected: " + sets_collected + "\nScore: " + score;
        }

        public string ShortStatus(DateTime transmitTime, Role role)
        {
            DateTime turn_end_parsed = DateTime.Parse(turn_end, null, System.Globalization.DateTimeStyles.RoundtripKind);
            TimeSpan timeLeftInTurn = (role == turn) ? turn_end_parsed - transmitTime : new TimeSpan(0);
            int movesRemaining = (role == turn) ? moves_remaining : 0;
            string color = movesRemaining == 0 ? "red" : "#00ff00ff";
            string coloredMovesRemaining = "<color=" + color + ">" + movesRemaining + "</color>";
            int turnsLeft = Math.Max(turns_left, 0);  // if -1 then game is over, display zero to be more tidy.
            return "Score: " + score + "\tTime Left in turn: " + timeLeftInTurn.ToString(@"mm\:ss") + "\nMoves this turn: " + coloredMovesRemaining + "\tTurns Left: " + turns_left;
        }
    }

    [Serializable]
    public class TurnComplete
    {
    }
}