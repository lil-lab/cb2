# File: evaluate_pretrained_on_corpora
# ------------------------------------
# Script for evaluating a pretrained model on
# static corpora. This essentially runs the evaluate_epoch
# function on the main training script.

import argparse
import os

import numpy as np
import torch

import follower_bots.constants as const
from follower_bots.data_utils.pyclient_utils import initialize_coordinator
from follower_bots.data_utils.sql_dataset import (
    get_leader_actions,
    get_sql_dataloader_for,
)
from follower_bots.models.model_utils import load_follower_model_for_corpora_eval
from follower_bots.training.train_utils import evaluate_on_cb2
from follower_bots.utils import mkdir


def get_args():
    parser = argparse.ArgumentParser(description="Interaction with pretrained models")

    # Experiment arguments
    parser.add_argument(
        "--evaluation_turns",
        type=int,
        default=1,
        help="How many times to evaluate the model with rollouts",
    )
    parser.add_argument(
        "--savepath_name",
        type=str,
        default="corpora_evaluation",
        help="The name of the file to save the results in",
    )

    # Model loading arguments
    parser.add_argument(
        "--experiments_folder",
        type=str,
        help="The folder in which the desired experiment is held",
    )
    parser.add_argument(
        "--experiments_name",
        type=str,
        help="The name of the experiment from which to load a model",
    )
    parser.add_argument(
        "--sampling_strat",
        type=str,
        default=const.SAMPLING_STRAT,
        choices=const.SAMPLING_STRATS,
        help="The strategy to follow for sampling follower actions",
    )

    # Ensembling arguments: Will override some of past arguments
    parser.add_argument(
        "--use_ensembling",
        action="store_true",
        help="If set, will use an ensemble of models",
    )
    parser.add_argument(
        "--ensemble_model_names",
        type=str,
        nargs="*",
        help="The name of the experiments from which to load models",
    )
    parser.add_argument(
        "--ensembling_strat",
        type=str,
        choices=const.ENSEMBLING_STRATS,
        default="boltzmann_multiplication",
        help="What ensembling strategy to use for ensembling",
    )

    # Dataset arguments
    parser.add_argument("--batch_size", type=int, default=const.BATCH_SIZE)
    parser.add_argument("--num_workers", type=int, default=const.NUM_WORKERS)
    parser.add_argument("--pretrain_dset_path", default="./follower_bots/pretraining_data")
    parser.add_argument(
        "--config_filepath", default="./follower_bots/data_configs/pretraining_examples.json"
    )

    args = parser.parse_args()
    return args


def standard_evaluation(
    args, savepath, follower, val_loader, coordinator, leader_actions
):
    average_accuracies = []
    swsds = []
    distances = []
    recall_precisions = []

    # Perform evaluation evaluation_turns times
    for i in range(args.evaluation_turns):
        acc, swsd, dist, recall_precision = evaluate_on_cb2(
            follower, val_loader, coordinator, leader_actions
        )
        average_accuracies.append(acc)
        swsds.append(swsd)
        distances.append(dist)
        recall_precisions.append(recall_precision)

    # Report the results
    average_accuracy, std_accuracy = np.mean(average_accuracies), np.std(
        average_accuracies
    )
    print(
        f"Average accuracy for collecting cards: {average_accuracy} pm {std_accuracy}"
    )

    average_swsd, std_swsd = np.mean(swsds), np.std(swsds)
    print(f"Average SWSD for collecting cards: {average_swsd} pm {std_swsd}")

    avg_dist = np.mean([d[0] for d in distances])
    avg_dist_when_correct = np.mean([d[1] for d in distances])
    avg_dist_when_incorrect = np.mean([d[2] for d in distances])
    print(
        f"Average distance: {avg_dist}, average distance when instruction is correct: {avg_dist_when_correct}, "
        + f"average distance when instruction is incorrect: {avg_dist_when_incorrect}"
    )

    avg_recall = np.mean([rp[0] for rp in recall_precisions])
    avg_precision = np.mean([rp[1] for rp in recall_precisions])
    print(
        f"Average model recall: {avg_recall}, average model precision: {avg_precision}"
    )

    # Save to more easily repeat reporting
    save_list = [
        (average_accuracy, std_accuracy),
        (average_swsd, std_swsd),
        (avg_dist, avg_dist_when_correct, avg_dist_when_incorrect),
        (avg_recall, avg_precision),
    ]
    torch.save(save_list, savepath)


def get_result_savepath(args):
    base_dir = os.path.join(args.experiments_folder, args.experiments_name, "logging")
    if args.use_ensembling and not os.path.exists(base_dir):
        mkdir(base_dir)
    savepath = os.path.join(base_dir, f"{args.savepath_name}.pt")
    return savepath


def main():
    args = get_args()

    # Get the model savepath
    savepath = get_result_savepath(args)
    print(f"Saving model results to: {savepath}")

    # Load the model
    follower = load_follower_model_for_corpora_eval(args)
    follower.eval()

    val_loader = get_sql_dataloader_for(args, "val")
    coordinator = initialize_coordinator(args)
    leader_actions = get_leader_actions(args)

    standard_evaluation(
        args, savepath, follower, val_loader, coordinator, leader_actions
    )


if __name__ == "__main__":
    main()
