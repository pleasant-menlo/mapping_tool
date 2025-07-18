from pathlib import Path


def get_example_config_path():
    return Path(__name__).parent / "example_configuration_files"
