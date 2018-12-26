import toml


def load_config():
    with open('config.toml', 'r') as f:
        return toml.load(f)


if __name__ == "__main__":
    print(load_config())
