import logging

from mapping_tool.dependency_collector import DependencyCollector
from mapping_tool.generate_map import generate_map

logger = logging.getLogger(__name__)

logging.getLogger("imap_processing").setLevel(logging.WARNING)

import imap_data_access
import spiceypy
import argparse
from pathlib import Path

from mapping_tool.configuration import Configuration


def do_mapping_tool():
    parser = argparse.ArgumentParser()
    parser.add_argument('config_file', type=Path)
    args = parser.parse_args()
    config = Configuration.from_file(args.config_file)

    map_date_ranges = config.canonical_map_period.calculate_date_ranges()

    for descriptor, _ in config.get_map_descriptors():
        for start_date, end_date in map_date_ranges:
            map_details = f'{descriptor.to_string()} {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")}'

            logger.info(f"Generating map: {map_details}")

            generate_map(descriptor, start_date, end_date)


if __name__ == "__main__":
    do_mapping_tool()
