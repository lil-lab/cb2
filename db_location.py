"""Utility to locate the database file used by a CB2 instance.

Run with:

```
python3 -m db_location --config_filepath="path/to/config.yaml"
```

"""

import logging
import os
import sys

import fire

from server.config.config import Config, ReadConfigOrDie

logger = logging.getLogger(__name__)


def main(config_filepath: str = ""):
    """Locate the database file used by a CB2 instance.

    Args:
        config_filepath: Path to the config file used by the CB2 instance.
    """
    logging.basicConfig(level=logging.INFO)

    if config_filepath == "":
        config = Config()
        logger.warning(
            f"No config was provided. Using default database located at: {config.database_path()}"
        )
    else:
        if not os.path.exists(config_filepath):
            logger.error(f"Provided config file does not exist: {config_filepath}")
            sys.exit(1)
        config = ReadConfigOrDie(config_filepath)
    print(f"Database path: {config.database_path()}")


if __name__ == "__main__":
    fire.Fire(main)
