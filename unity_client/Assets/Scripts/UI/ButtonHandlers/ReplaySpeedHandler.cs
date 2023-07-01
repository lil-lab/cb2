using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

public class ReplaySpeedHandler : MonoBehaviour
{
    private Slider _slider;
    // Start is called before the first frame update
    void Start()
    {
        _slider = GetComponent<Slider>();         
        if (_slider != null)
        {
            _slider.onValueChanged.AddListener(delegate {ValueChangeCheck ();});
        }
    }

    public void ValueChangeCheck()
    {
        Logger.GetOrCreateTrackedLogger("ReplaySpeedHandler").Info("Slider speed changed to " + _slider.value);
        ReplayManager.TaggedInstance().SetSpeed(_slider.value);
    }
}
