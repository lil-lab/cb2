#!/bin/bash
python -m follower_bots.training.pretrain_follower --cnn_option=1 --lr=0.0007425310658008663 --wd=6.053646330383653e-06 --training_cutoff=15 --experiments_folder=./experiments/pretraining/deployment_models --experiment_name=run_1 --state_embed_dim=128 --use_timesteps --warmup_steps=969 --num_layers=-1
