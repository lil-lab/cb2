#!/bin/bash
python -m follower_bots.training.pretrain_follower --cnn_option=1 --lr=0.0005665878334840695 --wd=1.089585419207773e-05 --training_cutoff=15 --experiments_folder=./experiments/pretraining/deployment_models --experiment_name=run_3 --state_embed_dim=128 --use_timesteps --warmup_steps=854 --num_layers=-1
