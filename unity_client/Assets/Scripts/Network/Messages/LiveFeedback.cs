using System;

namespace Network
{
    public enum FeedbackType
    {
        NONE = 0,
        POSITIVE,
        NEGATIVE,
    }

    [Serializable]
    public class LiveFeedback
    {
        public FeedbackType signal;
    }
}
