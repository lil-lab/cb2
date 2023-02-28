#!/bin/bash
python -m follower_bots.training.pretrain_follower --cnn_option=1 --lr=0.0007532246812636627 --wd=1.0870184782265894e-05 --training_cutoff=15 --experiments_folder=./experiments/pretraining/deployment_models --experiment_name=run_2 --state_embed_dim=128 --use_timesteps --warmup_steps=1148 --num_layers=-1

