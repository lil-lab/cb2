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

    public void Update()
    {
        Network.NetworkManager network = Network.NetworkManager.TaggedInstance();
        if (network == null)
            return;
        if (network.CurrentTurn() != Network.Role.FOLLOWER) return;
        if (network.Role() != Network.Role.FOLLOWER) return;
        if (Input.GetKeyDown(KeyCode.D))
        {
            OnCompleteObjective();
        }
    }
}
