using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class UIObjectiveInfo : MonoBehaviour
{
    public Network.ObjectiveMessage Objective = null;

    public void OnCompleteObjective()
    {
        Network.ObjectiveCompleteMessage complete = new Network.ObjectiveCompleteMessage();
        complete.Uuid = Objective.Uuid;
        MenuTransitionHandler.TaggedInstance().OnCompleteObjective(complete);
    }
}
