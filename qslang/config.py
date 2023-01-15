import logging
from pathlib import Path

import toml

logger = logging.getLogger(__name__)

rootdir = Path(__file__).resolve().parent.parent
homedir = Path.home()
configdir = homedir / ".config" / "qslang"

_testing = False
_config = None


def set_global_testing():
    logger.info("Setting global testing flag")
    global _testing
    _testing = True


def load_config(testing=False):
    global _testing
    global _config

    testing = testing or _testing
    if _config:
        return _config

    filepath = None
    for path in (configdir, rootdir):
        path = path / "config.toml"
        if path.exists():
            filepath = path

    if not filepath or testing:
        if not filepath:
            logger.warning("No config found, falling back to example config")
        if testing:
            logger.info("Using example config for testing")
        filepath = rootdir / "config.toml.example"

    logger.info(f"Using config file at {filepath}")
    with open(filepath, "r") as f:
        config = toml.load(f)
    _config = config
    return config


if __name__ == "__main__":
    print(rootdir)
    print(load_config())
