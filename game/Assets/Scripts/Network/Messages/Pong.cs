using System;
// The client-side response to a ping message. 
// Carries ping receive timestamp so that the server can synchronize clocks.
namespace Network
{
    [Serializable]
    public class Pong
    {
        public string ping_receive_time;  // ISO 8601 format.
    }
}