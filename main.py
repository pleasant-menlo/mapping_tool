import argparse
from pathlib import Path

from configuration import Configuration


def create_maps():
    pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('config_file', type=Path)
    args = parser.parse_args()
    config = Configuration.from_json(args.config_file)
    print(config.get_map_descriptors())

    create_maps()
