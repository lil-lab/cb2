using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

public class NotInteractiveInReplay : MonoBehaviour
{
    // Start is called before the first frame update
    void Start()
    {
        Network.NetworkManager network = Network.NetworkManager.TaggedInstance();
        if (network == null)
            return;
        if (network.IsReplay())
        {
            Button b = gameObject.GetComponent<Button>();
            if (b != null)
            {
                b.interactable = false;
                return;
            }
            TMPro.TMP_InputField tmp_i = gameObject.GetComponent<TMPro.TMP_InputField>();
            if (tmp_i != null)
            {
                tmp_i.interactable = false;
                return;
            }
            gameObject.SetActive(false);
        }
    }
}
