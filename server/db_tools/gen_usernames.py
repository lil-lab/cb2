from schemas.mturk import Worker
from schemas.leaderboard import Username

import config.config as config
import leaderboard
import schemas.defaults
from schemas import base

import fire

def InitWorkerDefaultUsernameIfNotExists(worker):
    username = leaderboard.LookupUsername(worker)
    if username is None:
        leaderboard.SetDefaultUsername(worker)
        print(f"Set username for {worker.hashed_id} ({leaderboard.LookupUsername(worker)})")
    else:
        print(f"Username exists for {worker.hashed_id} ({username})")

def main(config_filepath="config/server-config.json"):
    cfg = config.ReadConfigOrDie(config_filepath)

    print(f"Reading database from {cfg.database_path()}")
    # Setup the sqlite database used to record game actions.
    base.SetDatabase(cfg.database_path())
    base.ConnectDatabase()
    base.CreateTablesIfNotExists(schemas.defaults.ListDefaultTables())

    workers = Worker.select()
    for worker in workers:
        InitWorkerDefaultUsernameIfNotExists(worker)

if __name__ == "__main__":
    fire.Fire(main)