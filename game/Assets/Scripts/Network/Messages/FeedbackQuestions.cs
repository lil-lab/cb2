using System;
using System.Collections.Generic;

namespace Network
{
    public enum QuestionType
    {
        NONE = 0,
        BOOLEAN,
        MULTIPLE_CHOICE,
        TEXT
    }

    [Serializable]
    public class FeedbackQuestion
    {
        public QuestionType type = QuestionType.NONE;
        public Role to = Role.NONE; // Role which is being questioned.
        public string question = "";
        public string uuid = "";
        public float timeout_s = 10.0f;
        public List<string> answers = new List<string>();
    }

    [Serializable]
    public class FeedbackResponse
    {
        public string uuid = "";
        public string response = "";
        public int response_index = -1;
        public bool response_tf = false;
    }
}
