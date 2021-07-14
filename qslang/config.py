import os
import logging
from pathlib import Path

import toml

logger = logging.getLogger(__name__)

rootdir = Path(__file__).resolve().parent


def load_config():
    filepath = rootdir / "config.toml"
    if not filepath.exists():
        logger.warning("No config found, falling back to example config")
        filepath = Path(rootdir) / "config.toml.example"
    with open(filepath, "r") as f:
        return toml.load(f)


if __name__ == "__main__":
    print(load_config())
