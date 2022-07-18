from schemas.mturk import Worker, WorkerExperience
from schemas.game import Game
from db_tools import db_utils

import config.config as config
import experience
import schemas.defaults
from schemas import base

import fire
import peewee

from tqdm import tqdm

def main(config_filepath="config/server-config.json"):
    cfg = config.ReadConfigOrDie(config_filepath)

    print(f"Reading database from {cfg.database_path()}")
    # Setup the sqlite database used to record game actions.
    base.SetDatabase(cfg.database_path())
    base.ConnectDatabase()
    base.CreateTablesIfNotExists(schemas.defaults.ListDefaultTables())

    workers = Worker.select().join(schemas.mturk.WorkerExperience)
    for worker in tqdm(workers):
        experience.InitWorkerExperience(worker)

    games = db_utils.ListMturkGames().join(Worker, join_type=peewee.JOIN.LEFT_OUTER, on=((Game.leader == Worker.id) or (Game.follower == Worker.id)))
    for game in tqdm(games):
        experience.UpdateWorkerExperienceTable(game)

if __name__ == "__main__":
    fire.Fire(main)