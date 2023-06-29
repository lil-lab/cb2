"""Utility to locate the database file used by a CB2 instance.

Run with:

```
python3 -m db_location --config_filepath="path/to/config.yaml"
```

"""

import os
import sys

import fire

from server.config.config import ReadConfigOrDie


def main(config_filepath: str = ""):
    """Locate the database file used by a CB2 instance.

    Args:
        config_filepath: Path to the config file used by the CB2 instance.
    """
    if not os.path.exists(config_filepath):
        print("No config file path provided.")
        sys.exit(1)

    config = ReadConfigOrDie(config_filepath)
    print(f"Database path: {config.database_path()}")


if __name__ == "__main__":
    fire.Fire(main)
