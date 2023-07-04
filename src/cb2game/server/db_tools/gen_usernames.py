import fire
from tqdm import tqdm

import cb2game.server.config.config as config
import cb2game.server.leaderboard as leaderboard
import cb2game.server.schemas.defaults as defaults_db
from cb2game.server.schemas import base
from cb2game.server.schemas.mturk import Worker
from cb2game.server.util import PackageRoot


def InitWorkerDefaultUsernameIfNotExists(worker):
    username = leaderboard.LookupUsername(worker)
    if username is None:
        leaderboard.SetDefaultUsername(worker)
        print(
            f"Set username for {worker.hashed_id} ({leaderboard.LookupUsername(worker)})"
        )
    else:
        print(f"Username exists for {worker.hashed_id} ({username})")


def main(config_filepath=(PackageRoot() / "server/config/server-config.yaml")):
    cfg = config.ReadConfigOrDie(config_filepath)

    print(f"Reading database from {cfg.database_path()}")
    # Setup the sqlite database used to record game actions.
    base.SetDatabase(cfg)
    base.ConnectDatabase()
    base.CreateTablesIfNotExists(defaults_db.ListDefaultTables())

    workers = Worker.select()
    for worker in tqdm(workers):
        InitWorkerDefaultUsernameIfNotExists(worker)


if __name__ == "__main__":
    fire.Fire(main)
