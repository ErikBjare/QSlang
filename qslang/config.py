import logging
from pathlib import Path

import toml

logger = logging.getLogger(__name__)

rootdir = Path(__file__).resolve().parent.parent
homedir = Path.home()
configdir = homedir / ".config" / "qslang"


def load_config():
    filepath = None
    for path in (configdir, rootdir):
        path = path / "config.toml"
        if path.exists():
            filepath = path

    if not filepath:
        logger.warning("No config found, falling back to example config")
        filepath = rootdir / "config.toml.example"

    with open(filepath, "r") as f:
        return toml.load(f)


if __name__ == "__main__":
    print(rootdir)
    print(load_config())
