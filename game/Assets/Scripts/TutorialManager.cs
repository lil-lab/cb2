using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using TMPro;

public class TutorialManager : MonoBehaviour
{
    public static readonly string TAG = "TutorialManager";
    private static readonly string CANVAS_TAG = "TOOLTIP_CANVAS";
    private static TutorialManager _instance;

    public GameObject TooltipTextbox;
    public GameObject HighlightBox;

    private Prop _indicator = null;

    private Network.Tooltip _lastTooltip = null;

    public static TutorialManager TaggedInstance()
    {
        if (_instance == null)
        {
            GameObject tutorialManager = GameObject.FindGameObjectWithTag(TutorialManager.TAG);
            _instance = tutorialManager.GetComponent<TutorialManager>();
        }
        return _instance;
    }

    private Canvas TaggedCanvas()
    {
        Canvas canvas = GameObject.FindGameObjectWithTag(CANVAS_TAG).GetComponent<Canvas>();
        return canvas;
    }

    public void SetIndicator(HecsCoord location)
    {
        if (_indicator != null)
        {
            _indicator.Destroy();
        }
        UnityAssetSource assetSource = new UnityAssetSource();
        GameObject groundPulse = assetSource.Load(IAssetSource.AssetId.TUTORIAL_INDICATOR);
        _indicator = new Prop(groundPulse);
        _indicator.AddAction(Init.InitAt(location, 0));
    }

    public void ClearIndicator()
    {
        if (_indicator != null)
        {
            _indicator.Destroy();
        }
    }

    public void CopyRectangleProperties(RectTransform rectTo, RectTransform rectFrom)
    {
        rectTo.anchorMin = rectFrom.anchorMin;
        rectTo.anchorMax = rectFrom.anchorMax;
        rectTo.anchoredPosition = rectFrom.anchoredPosition;
        rectTo.offsetMin = rectFrom.offsetMin;
        rectTo.offsetMax = rectFrom.offsetMax;
        rectTo.sizeDelta = rectFrom.sizeDelta;
        rectTo.pivot = rectFrom.pivot;
    }

    public void SetTooltip(string text, string highlightedComponentTag)
    {
        Canvas canvas = TaggedCanvas();
        float canvasWidth = canvas.GetComponent<RectTransform>().rect.width;
        float canvasHeight = canvas.GetComponent<RectTransform>().rect.height;
        TMPro.TMP_Text tooltip = TooltipTextbox.GetComponent<TMPro.TMP_Text>();
        tooltip.text = text;
        if (highlightedComponentTag == "")
        {
            HighlightBox.GetComponent<RectTransform>().sizeDelta = new Vector2(0, 0);
            return;
        }
        GameObject highlightedComponent = GameObject.FindGameObjectWithTag(highlightedComponentTag);
        RectTransform highlightedComponentRect = highlightedComponent.GetComponent<RectTransform>();
        Vector3[] corners = new Vector3[4];
        highlightedComponentRect.GetWorldCorners(corners);
        CopyRectangleProperties(HighlightBox.GetComponent<RectTransform>(), highlightedComponentRect);
        HighlightBox.GetComponent<RectTransform>().SetPositionAndRotation(highlightedComponentRect.position + (new Vector3(-5f, 5f, 0)), highlightedComponentRect.rotation);
        HighlightBox.GetComponent<RectTransform>().sizeDelta = new Vector2(corners[2].x - corners[0].x, corners[2].y - corners[0].y);
        HighlightBox.GetComponent<RectTransform>().ForceUpdateRectTransforms();
    }

    public void HandleTutorialStep(Network.TutorialStep step)
    {
        if (step.Tooltip != null)
        {
            Network.Tooltip tooltip = step.Tooltip;
            _lastTooltip = tooltip;
            SetTooltip(tooltip.Text, tooltip.HighlightedComponentTag);
        }
        if (step.Indicator != null)
        {
            SetIndicator(step.Indicator.Location);
        } else {
            ClearIndicator();
        }
    }

    public void NextStep()
    {
        Network.NetworkManager.TaggedInstance().NextTutorialStep();
    }

    public void Start()
    {
        NextStep();
    }

    public void Update()
    {
        if (_lastTooltip != null)
        {
            if ((Input.GetKeyDown(KeyCode.LeftShift) || Input.GetKeyDown(KeyCode.RightShift)) && (_lastTooltip.Type == Network.TooltipType.UNTIL_DISMISSED))
            {
                NextStep();
            }
            if (Input.GetKeyDown(KeyCode.C) && (_lastTooltip.Type == Network.TooltipType.UNTIL_CAMERA_TOGGLED))
            {
                NextStep();
            }
        }
        if (_indicator != null)
        {
            _indicator.Update();
        }
    }
}
