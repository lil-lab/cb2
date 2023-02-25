# File: model_utils
# -----------------
# Contain utilities for models, such as loading and saving models

import os

import torch

from follower_bots.constants import TORCH_DEVICE
from follower_bots.models.ensembled_models import FollowerEnsemble
from follower_bots.models.follower_transformers import DecisionTransformer
from follower_bots.utils import load_arguments


def save_checkpoints(
    follower,
    optimizer,
    scheduler,
    swsd,
    best_swsd,
    epoch,
    epochs_since_best,
    checkpoint_dir,
):
    """
    Saves model, optimizer and scheduler state dicts to the checkpointing folder.
    """
    torch.save(
        [follower.state_dict(), epoch, (best_swsd, epochs_since_best)],
        os.path.join(checkpoint_dir, "latest_follower.pth"),
    )
    torch.save(
        optimizer.state_dict(), os.path.join(checkpoint_dir, "latest_optimizer.pt")
    )
    torch.save(
        scheduler.state_dict(), os.path.join(checkpoint_dir, "latest_scheduler.pt")
    )

    if swsd >= best_swsd:
        torch.save(
            [follower.state_dict(), epoch, (best_swsd, epochs_since_best)],
            os.path.join(checkpoint_dir, "best_follower.pth"),
        )
        torch.save(
            optimizer.state_dict(), os.path.join(checkpoint_dir, "best_optimizer.pt")
        )
        torch.save(
            scheduler.state_dict(), os.path.join(checkpoint_dir, "best_scheduler.pt")
        )


def get_follower_model(args):
    """
    Function for initializing a follower model for training. If the launch_from_checkpoint
    flag is set and a checkpoint exists, training will resume from the checkpoint.
    """

    # Load the model normally
    follower = DecisionTransformer(
        args.act_dim,
        args.state_embed_dim,
        args.cnn_option,
        freeze_embeddings=args.freeze_embeddings,
        use_timesteps=args.use_timesteps,
        max_ep_len=args.max_ep_len,
        num_layers=args.num_layers,
        inference_temperature=args.inference_temperature,
        sampling_strat=args.sampling_strat,
        device=TORCH_DEVICE,
    ).to(TORCH_DEVICE)

    args.start_epoch = 0
    args.best_swsd = float("-inf")
    args.epochs_since_best = 0

    # If we wish to continue training from a checkpoint
    if args.launch_from_checkpoint and os.path.exists(
        os.path.join(args.checkpoint_dir, "latest_follower.pth")
    ):
        state_dict, epoch, (best_swsd, epochs_since_best) = torch.load(
            os.path.join(args.checkpoint_dir, "latest_follower.pth")
        )
        follower.load_state_dict(state_dict)

        args.start_epoch = epoch + 1
        args.best_swsd = best_swsd
        args.epochs_since_best = epochs_since_best

    return follower


def load_follower_model(args, args_dir, model_dir, load_best=True):
    model_args = load_arguments(args_dir)
    follower = DecisionTransformer(
        model_args["act_dim"],
        model_args["state_embed_dim"],
        model_args["cnn_option"],
        max_ep_len=model_args["max_ep_len"],
        use_timesteps=model_args["use_timesteps"],
        freeze_embeddings=model_args["freeze_embeddings"],
        num_layers=model_args["num_layers"],
        inference_temperature=model_args["inference_temperature"],
        sampling_strat=args.sampling_strat,
        device=TORCH_DEVICE,
    ).to(TORCH_DEVICE)

    filename = "best_follower.pth" if load_best else "latest_follower.pth"
    state_dict, epoch, (best_swsd, epochs_since_best) = torch.load(
        os.path.join(model_dir, filename), map_location=TORCH_DEVICE
    )
    follower.load_state_dict(state_dict)

    return follower, epoch, (best_swsd, epochs_since_best)


def load_follower_model_for_corpora_eval_ensembled(args):
    args_dirs = []
    model_dirs = []
    for run_num, exp_name in enumerate(args.ensemble_model_names):
        # Add the argument directory
        args_dir = os.path.join(arg.experiments_folder, exp_name, "logging")
        args_dirs.append(args_dir)

        # Add the model directory
        model_dir = os.path.join(args.experiments_folder, exp_name, "checkpoints")
        model_dirs.append(model_dir)

    if len(args_dirs) > 1:
        follower = FollowerEnsemble(args, args_dirs, model_dirs)
    else:
        follower, _, _ = load_follower_model(
            args, args_dirs[0], model_dirs[0], load_best=True
        )
    return follower


def load_follower_model_for_corpora_eval_standard(args):
    args_dir = os.path.join(args.experiments_folder, args.experiments_name, "logging")
    model_dir = os.path.join(
        args.experiments_folder, args.experiments_name, "checkpoints"
    )
    follower, _, _ = load_follower_model(args, args_dir, model_dir, load_best=True)
    return follower


def load_follower_model_from_binaries(args, models_to_use):
    if len(models_to_use) == 1:
        base_path = os.path.join('follower_bots', 'experiments', 'pretraining',
                                 'deployment_models', f'follower_{models_to_use[0]}.pt')
        follower = torch.load(base_path).to(TORCH_DEVICE)
        follower.device = TORCH_DEVICE
        return follower
    elif len(models_to_use) > 1:
        follower = FollowerEnsemble(args, None, None, deployment_models=models_to_use)
    else:
        print("Expected to be given at least one model to use")
        assert(False)

def load_follower_model_for_corpora_eval(args):
    "ensembled" if args.use_ensembling else "normal"
    if args.use_deployment_models:
        return load_follower_model_from_binaries(args, args.deployment_models_to_use)
    if args.use_ensembling:
        return load_follower_model_for_corpora_eval_ensembled(args)
    else:
        return load_follower_model_for_corpora_eval_standard(args)
