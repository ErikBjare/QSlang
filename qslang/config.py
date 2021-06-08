import os

import toml


base_dir = os.path.dirname(__file__)


def load_config():
    with open(os.path.dirname(base_dir) + "/config.toml", "r") as f:
        return toml.load(f)


if __name__ == "__main__":
    print(load_config())
