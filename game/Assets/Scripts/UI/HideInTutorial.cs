using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class HideInTutorial : MonoBehaviour
{
    // Start is called before the first frame update
    void Start()
    {
        if (TutorialManager.TaggedInstance() != null)
        {
            gameObject.SetActive(false);
        }
    }
}
