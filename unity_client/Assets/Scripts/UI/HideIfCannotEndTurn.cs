using System.Collections;
using System.Collections.Generic;
using UnityEngine;

// If the current player is the Leader and there are no pending instructions for
// the follower, then the player cannot end their turn.
public class HideIfCannotEndTurn : MonoBehaviour
{
    private Vector2 _originalSize;
    void Start()
    {
        RectTransform rt = gameObject.GetComponent<RectTransform>();
        _originalSize = new Vector2(rt.sizeDelta.x, rt.sizeDelta.y);
    }
    void Update()
    {
        // Followers can always end their turn.
        if (Network.NetworkManager.TaggedInstance().Role() == Network.Role.FOLLOWER) return; 
        List<Network.ObjectiveMessage> messages = MenuTransitionHandler.TaggedInstance().ObjectiveList();
        foreach (Network.ObjectiveMessage message in messages)
        {
            if (!message.is_concluded())
            {
                gameObject.transform.localScale = new Vector3(1, 1, 1);
                // Set rect height to 0.
                gameObject.GetComponent<RectTransform>().sizeDelta = _originalSize;
                return;
            }
        }
        gameObject.transform.localScale = new Vector3(0, 0, 0);
        gameObject.GetComponent<RectTransform>().sizeDelta = new Vector2(0, 0);
    }
}
