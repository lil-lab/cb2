# File: pretrain_follower
# -----------------------
# Pretraining script to train the follower agent with behavior cloning.

import argparse
import os

import torch
import torch.multiprocessing
import torch.nn as nn
from torch.utils.tensorboard import SummaryWriter

torch.multiprocessing.set_sharing_strategy("file_system")

import follower_bots.constants as const
from follower_bots.data_utils.pyclient_utils import initialize_coordinator
from follower_bots.data_utils.sql_dataset import get_leader_actions, get_sql_dataloader
from follower_bots.training.train_utils import evaluate_on_cb2, get_optimizer_and_scheduler 

from follower_bots.models.model_utils import get_follower_model, save_checkpoints
from follower_bots.utils import setup_experiment


def get_args():
    parser = argparse.ArgumentParser(
        description="Behavior Cloning pretraining for the follower model"
    )

    # Model arguments:
    parser.add_argument(
        "--act_dim",
        type=int,
        default=const.ACT_DIM,
        help="Number of actions the follower can take",
    )
    parser.add_argument(
        "--state_embed_dim",
        type=int,
        default=const.CNN_EMB_DIM,
        help="The dimension that state property indices are embedded to",
    )
    parser.add_argument(
        "--num_layers",
        type=int,
        default=const.NUM_LAYERS,
        help="Number of hidden layers to use for GPT-2. If -1, use all of GPT-2.",
    )
    parser.add_argument(
        "--cnn_option",
        type=int,
        default=const.CNN_OPTION,
        help="Which CNN architecture to process the state encoding with",
    )
    parser.add_argument("--max_ep_len", type=int, default=const.MAX_TIME)
    parser.add_argument(
        "--use_timesteps",
        action="store_true",
        help="If set, will use additional timestep embeddings",
    )
    parser.add_argument(
        "--freeze_embeddings",
        action="store_true",
        help="If set, we will freeze GPT-2's character embeddings",
    )
    parser.add_argument(
        "--inference_temperature",
        type=float,
        default=const.INFERENCE_TEMPERATURE,
        help="The temperature value to use during inference",
    )
    parser.add_argument(
        "--sampling_strat",
        type=str,
        default=const.SAMPLING_STRAT,
        choices=const.SAMPLING_STRATS,
        help="The strategy to follow for sampling follower actions during deployment",
    )

    # Training arguments
    parser.add_argument(
        "--lr", type=float, default=const.LR, help="The initial learning rate for Adam"
    )
    parser.add_argument(
        "--wd", type=float, default=const.WD, help="Weight decay for Adam"
    )
    parser.add_argument(
        "--adam_epsilon",
        type=float,
        default=const.ADAM_EPSILON,
        help="Epsilon for Adam optimzer",
    )
    parser.add_argument(
        "--max_grad_norm",
        type=float,
        default=const.MAX_GRAD_NORM,
        help="Max gradient norm.",
    )
    parser.add_argument(
        "--warmup_steps",
        type=int,
        default=const.WARMUP_STEPS,
        help="Number of warm-up steps for the lr scheduler",
    )

    parser.add_argument(
        "--n_epochs",
        type=int,
        default=const.N_EPOCH,
        help="Maximum number of epochs to train the model for",
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=const.BATCH_SIZE,
        help="Minibatch size during training",
    )
    parser.add_argument(
        "--num_workers",
        type=int,
        default=const.NUM_WORKERS,
        help="Number of workers for the dataloader",
    )
    parser.add_argument(
        "--training_cutoff",
        type=int,
        default=6,
        help="The number of epochs (where best val accuracy doesn't improve) to wait before stopping",
    )

    # Experiment arguments
    parser.add_argument(
        "--experiments_folder",
        type=str,
        default=os.path.join(".", "experiments", "pretraining"),
        help="The parent folder where the experiments folder will be kept",
    )
    parser.add_argument(
        "--experiment_name",
        type=str,
        default="follower_pretrain",
        help="Name for the experiment folder",
    )

    parser.add_argument("--pretrain_dset_path", type=str, default="./follower_bots/pretraining_data")
    parser.add_argument(
        "--config_filepath", default="./follower_bots/data_configs/pretraining_examples.json"
    )

    parser.add_argument(
        "--launch_from_checkpoint",
        action="store_true",
        help="If set, will load the most recent model.",
    )

    args = parser.parse_args()
    return args


def train(
    args,
    follower,
    optimizer,
    scheduler,
    tr_loader,
    val_loader,
    coordinator,
    i_uuid_to_actions,
    val_loader_ce,
):
    best_card_acc, best_swsd = float("-inf"), args.best_swsd
    writer = SummaryWriter(args.logdir)
    epochs_since_best = args.epochs_since_best

    for epoch in range(args.start_epoch, args.n_epochs):
        tr_ce_loss = train_epoch(follower, optimizer, scheduler, tr_loader)

        writer.add_scalar("tr_ce_loss", tr_ce_loss, global_step=epoch)
        print(f"Epoch {epoch} train loss: {tr_ce_loss}")

        # Evaluate model (both statically and on client)
        selection_accuracy, swsd, distances, recall_precision = evaluate_on_cb2(
            follower, val_loader, coordinator, i_uuid_to_actions
        )
        test_ce = evaluate_on_data(follower, val_loader_ce)

        # Record primary metrics
        writer.add_scalar("te_card_accuracy", selection_accuracy, global_step=epoch)
        best_card_acc = (
            selection_accuracy if selection_accuracy > best_card_acc else best_card_acc
        )
        print(
            f"Epoch {epoch} card_acc: {selection_accuracy}, best card_acc: {best_card_acc}"
        )

        writer.add_scalar("te_swsd", swsd, global_step=epoch)
        if swsd > best_swsd:
            best_swsd = swsd
            epochs_since_best = 0
        else:
            epochs_since_best += 1
        print(f"Epoch {epoch} swsd: {swsd}, best swsd: {best_swsd}")

        # Record secondary metrics
        print(
            f"Epoch {epoch} average distances: overall {distances[0]}, correct: {distances[1]}, incorrect: {distances[2]}"
        )
        writer.add_scalar("average_distance", distances[0], global_step=epoch)
        writer.add_scalar("average_distance_correct", distances[1], global_step=epoch)
        writer.add_scalar("average_distance_incorrect", distances[2], global_step=epoch)

        print(f"Epoch {epoch} average recall: {recall_precision[0]}")
        writer.add_scalar("average_recall", recall_precision[0], global_step=epoch)
        print(f"Epoch {epoch} average precision: {recall_precision[1]}")
        writer.add_scalar("average_precision", recall_precision[1], global_step=epoch)

        # Record ce for the sake of it
        print(f"Epoch {epoch} test_ce: {test_ce}")
        writer.add_scalar("test_ce", test_ce, global_step=epoch)

        checkpoint_dir = args.checkpoint_dir
        save_checkpoints(
            follower,
            optimizer,
            scheduler,
            swsd,
            best_swsd,
            epoch,
            epochs_since_best,
            checkpoint_dir,
        )

        if epochs_since_best >= args.training_cutoff:
            print(
                f"Model has not been improving in the past {epochs_since_best} epochs"
            )
            print("Stopping training")
            break


def train_epoch(follower, optimizer, scheduler, tr_loader):
    follower.train()
    train_loss, train_size = 0, 0
    criterion = nn.CrossEntropyLoss()

    for s, a, t, text, pos_idx, attn_mask, text_mask, action_mask, ids, _ in tr_loader:
        # Forward pass
        a_target = a.clone()
        a_pred = follower(s, a, t, text, pos_idx, attn_mask, text_mask, action_mask)

        a_pred = a_pred.view(-1, const.ACT_DIM)
        a_target = a_target.to(a_pred.device).reshape(-1)
        loss = criterion(a_pred, a_target)

        # Backward pass
        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(follower.parameters(), args.max_grad_norm)
        optimizer.step()
        scheduler.step()

        # Update losses
        N = s.shape[0]
        train_loss += loss.cpu().item() * N
        train_size += N

    return train_loss / train_size


def evaluate_on_data(follower, val_loader):
    follower.eval()
    test_loss, test_size = 0, 0
    criterion = nn.CrossEntropyLoss()

    with torch.no_grad():
        for (
            s,
            a,
            t,
            text,
            pos_idx,
            attn_mask,
            text_mask,
            action_mask,
            ids,
            _,
        ) in val_loader:
            a_pred = follower(s, a, t, text, pos_idx, attn_mask, text_mask, action_mask)

            a_pred = a_pred.view(-1, const.ACT_DIM)
            a_target = a.to(a_pred.device).reshape(-1)
            loss = criterion(a_pred, a_target)

            N = s.shape[0]
            test_loss += loss.cpu().item() * N
            test_size += N

    return test_loss / test_size


if __name__ == "__main__":
    args = get_args()

    # Make experiment, checkpoint and logging folders
    setup_experiment(args)

    # Model, dataloader and optim
    follower = get_follower_model(args)
    tr_loader, val_loader, val_loader_ce = get_sql_dataloader(args)
    optimizer, scheduler = get_optimizer_and_scheduler(args, tr_loader, follower)

    # Initialize the validation coordinator
    coordinator = initialize_coordinator(args)
    i_uuid_to_actions = get_leader_actions(args)

    train(
        args,
        follower,
        optimizer,
        scheduler,
        tr_loader,
        val_loader,
        coordinator,
        i_uuid_to_actions,
        val_loader_ce,
    )
