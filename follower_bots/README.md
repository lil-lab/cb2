Baseline Follower Model
=======================

- [Baseline Follower Model](#baseline-follower-model)
  - [Intro](#intro)
  - [Environment Setup](#environment-setup)
  - [Using Pretrained Models](#using-pretrained-models)
  - [Training New Models](#training-new-models)

Intro
-----

This folder contains the code used to train the follower model launched during our deployment
experiments and that is currently available to play with on the [CB2 website](https://cb2.ai).
Specifically, this folder contains code for interacting with and preprocessing the sqlite3
training database, a baseline follower model architecture, and scripts for training the model
using behavior cloning and evaluating its performance on games in the database.

Note that the various scripts here are examples and do not represent the only way of using the
CB2 repository.

Environment Setup
-----------------
This section assumes that a virtual environment with the necessary dependencies has been set up
as instructed on the main folder. After this, execute the following commands to complete environment
setup for model training:

```
python3 -m pip install torch==1.12.1+cu102 torchvision==0.13.1+cu102 torchaudio==0.12.1 --extra-index-url https://download.pytorch.org/whl/cu102
python3 -m pip install transformers==4.21.3 ray==2.0.0 scipy==1.7.3 seaborn==0.11.2
```

Using Pretrained Models
-----------------------
If you wish to use the models we trained and deployed, you may download them through
[this link](https://lil.nlp.cornell.edu/resources/cb2-base/). There are three models held
in this page. To use them, first create the folder `experiments/pretraining/deployment_models`,
place the zip files into the folder and unzip them. Each folder contains the model state_dict and
the arguments used to create the model.

To deploy and interact with a single one of these models in the bot-sandbox lobby, run the
following command:

```
python3 -m follower_bots.training.follower_demo --host=<server-link> --experiments_folder=./follower_bots/experiments/pretraining/deployment_models --experiments_name run_<run_number>
```

If you wish to launch an ensemble of all three models, use the following command instead

```
python3 -m follower_bots.training.follower_demo --host=<server-link> --experiments_folder=./follower_bots/experiments/pretraining/deployment_models --use_ensembling --ensemble_model_names run_1 run_2 run_3
```

This script can also be used to launch and interact with models trained from scratch.

Training New Models
-------------------
In order to train a new model, first run the following command in order to preprocess
the sqlite3 database:

```python3 -m follower_bots.data_utils.preprocess_sql```

Note that this script assumes the existence of a `pretraining_data` folder including
the training database, which should be renamed to `game_data.db`. Afterwards, you may use
the `training/pretrain_follower.py` script to train a new model. The `training/scripts`
folder contains the commands used to train our deployment models.

After each epoch of training, we evaluate models' performance on the validation set by
executing the model on each instruction in it. The code for the evaluation process
can be found in `training/train_utils.py`.

