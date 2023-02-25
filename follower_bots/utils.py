# File: utils.py
# --------------
# Script containing various utility functions

import json
import os
import pickle

from transformers import GPT2Config


def mkdir(dirpath):
    if not os.path.exists(dirpath):
        try:
            os.makedirs(dirpath)
        except FileExistsError:
            pass


def setup_experiment(args):
    # Make an overall experiments folder.
    args.expdir = os.path.join(args.experiments_folder, args.experiment_name)
    mkdir(args.expdir)

    # Make a checkpoints folder
    args.checkpoint_dir = os.path.join(args.expdir, "checkpoints")
    mkdir(args.checkpoint_dir)

    # Make a logging folder for tensorboard, etc.
    args.logdir = os.path.join(args.expdir, "logging")
    mkdir(args.logdir)

    with open(os.path.join(args.logdir, "args.json"), "w") as args_file:
        json.dump(args.__dict__, args_file)


def load_pickle(filename):
    try:
        with open(filename, "rb") as f:
            data = pickle.load(f)
            return data
    except Exception as e:
        raise (e)


def dump_pickle(filename, data):
    try:
        with open(filename, "wb") as f:
            pickle.dump(data, f)
    except Exception as e:
        raise (e)


def load_json(filename):
    try:
        with open(filename) as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise (e)


def get_gpt2_sep_index():
    config = GPT2Config()
    return config.vocab_size - 1  # The eos_token id


def load_arguments(args_dir):
    # Loads arguments from an existing logging directory.
    loaded_args = load_json(os.path.join(args_dir, "args.json"))
    return loaded_args
