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
        CARD_SELECT,
        CARD_DESELECT,
        // Easter egg sounds to play when the score is high enough.
        EASTER_EGG_SOUND_1,
        EASTER_EGG_SOUND_2,
        EASTER_EGG_SOUND_3,
        EASTER_EGG_SOUND_4,
    }

    [Serializable]
    public class SoundTrigger
    {
        public SoundClipType sound_clip;
        public float volume = 1.0f;  // Range: 0.0f (mute) to 1.0f (loudest)
    }
}
