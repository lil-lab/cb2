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
        IAssetSource.AssetId assetId = IAssetSource.AssetId.TUTORIAL_INDICATOR;
        GameObject groundPulse = assetSource.Load(assetId);
        _indicator = new Prop(groundPulse, assetId);
        _indicator.AddAction(Init.InitAt(location, 0));
    }

    public void ClearIndicator()
    {
        if (_indicator != null)
        {
            _indicator.Destroy();
        }
    }

    public void OverlayRectangle(RectTransform overlay, RectTransform uiElement)
    {
        Vector3[] corners = new Vector3[4];
        uiElement.GetWorldCorners(corners);
        // Lower left and upper right coordinates in overlay space.
        Vector3 ll = overlay.worldToLocalMatrix * corners[0];
        Vector3 ur = overlay.worldToLocalMatrix * corners[2];
        overlay.anchorMax = ur;
        overlay.anchorMin = ll;
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

        OverlayRectangle(HighlightBox.GetComponent<RectTransform>(), highlightedComponentRect);
        HighlightBox.GetComponent<RectTransform>().ForceUpdateRectTransforms();
    }

    public void HandleTutorialStep(Network.TutorialStep step)
    {
        if (step.tooltip != null)
        {
            Network.Tooltip tooltip = step.tooltip;
            _lastTooltip = tooltip;
            SetTooltip(tooltip.text, tooltip.highlighted_component_tag);
        }
        if (step.indicator != null)
        {
            SetIndicator(step.indicator.location);
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
            if ((Input.GetKeyDown(KeyCode.LeftShift) || Input.GetKeyDown(KeyCode.RightShift)) && (_lastTooltip.type == Network.TooltipType.UNTIL_DISMISSED))
            {
                NextStep();
            }
            if (Input.GetKeyDown(KeyCode.C) && (_lastTooltip.type == Network.TooltipType.UNTIL_CAMERA_TOGGLED))
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
