import logging

from mapping_tool.cli import do_mapping_tool
logger = logging.getLogger(__name__)

import argparse
from pathlib import Path

from mapping_tool.configuration import Configuration



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('config_file', type=Path, help="Path to configuration file in YAML or JSON format")
    parser.add_argument('-v', '--verbose', action='count', default=0, help='Increase verbosity')
    args = parser.parse_args()
    if args.verbose > 0:
        log_level = logging.INFO
    else:
        log_level = logging.ERROR
    logging.basicConfig(level=log_level, force=True)
    logging.captureWarnings(True)

    configuration = Configuration.from_file(args.config_file)

    do_mapping_tool(configuration)
