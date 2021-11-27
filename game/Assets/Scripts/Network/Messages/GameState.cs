using System;


namespace Network
{
    [Serializable]
    public class GameState
    {
        public Role Turn;  // Who's turn it is.
        public int TurnsRemaining;
        public int MovesRemaining;  // How many moves the player has left.
        public string GameEndDate;  // When the game ends, as a DateTime string in ISO 8601 format.
        public int Score;
    }
}