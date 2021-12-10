using System;


namespace Network
{
    [Serializable]
    public class TurnState
    {
        public Role Turn;  // Who's turn it is.
        public int MovesRemaining;  // How many moves the player has left.
        public string GameEndDate;  // Time when the game ends, as a DateTime string in ISO 8601 format. As turns progress, this date may move further back.
        public string GameDuration;  // Duration of the game, in a human readable HHhMMmSSs format. E.g. "1h30m30s".
        public int SetsCollected;
        public int Score;
        public bool GameOver;

        public string ScoreString()
        {
            return "Time taken: " + GameDuration + "\nSets Collected: " + SetsCollected + "\nScore: " + Score;
        }

        public string ShortStatus()
        {
            return "Score: " + Score + "\tGame Time" + GameDuration + "\nMoves this turn: " + MovesRemaining + "\tSets Collected: " + SetsCollected;
        }
    }
}