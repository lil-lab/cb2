using System;

namespace Network
{
    public enum SoundClipType
    {
        NONE = 0,
        INSTRUCTION_RECEIVED,
        INSTRUCTION_SENT,
        INVALID_SET,
        NEGATIVE_FEEDBACK,
        POSITIVE_FEEDBACK,
        VALID_SET,
        // Add more sound clip types here as needed
    }

    [Serializable]
    public class SoundTrigger
    {
        public SoundClipType sound_clip;
        public float volume = 1.0f;  // Range: 0.0f (mute) to 1.0f (loudest)
    }
}
