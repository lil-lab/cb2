# File: constants.py
# ------------------
# Keeps track of constant values throughout training experiments.

import torch

from follower_bots.utils import get_gpt2_sep_index
from server.config.config import Config

# Environment values
EDGE_WIDTH = 25
VISIBLE_DISTANCE = 7
FOV = 96.5
UNITY_COORDS_SCALE = 3.46
FOG_END = Config.fog_end
ACTIVE_MOVE_WINDOW = 0.25

# Architecture constants
TEXT_SEP_IDX = get_gpt2_sep_index()
TEXT_PAD_IDX = TEXT_SEP_IDX + 1
TEXT_VOCAB_SIZE = TEXT_PAD_IDX + 1
STATE_PAD_IDX = 0
NUM_PROPERTIES = 74
ACT_DIM = 6
CNN_OPTION = 3
CNN_EMB_DIM = 128
GPT_EMB_DIM = 768
MAX_TIME = 25
INFERENCE_HORIZON = 20
NUM_LAYERS = -1

# Sampling arguments
ENSEMBLING_STRATS = [
    "majority_voting_raw",
    "majority_voting_softmax",
    "boltzmann_multiplication",
]
SAMPLING_STRAT = "softmax"
SAMPLING_STRATS = ["argmax", "softmax"]

# Training arguments
LR = 0.0001
WD = 0.0001
ADAM_EPSILON = 1e-8
MAX_GRAD_NORM = 1.0
WARMUP_STEPS = 500
INFERENCE_TEMPERATURE = 1.0
N_EPOCH = 150
BATCH_SIZE = 32
NUM_WORKERS = 1

# Experiment arguments
SEED = -1

# Miscellaneous constants
TORCH_DEVICE = (
    torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
)
