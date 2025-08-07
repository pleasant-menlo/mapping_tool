import logging
import shutil

from mapping_tool.generate_map import generate_map

logger = logging.getLogger(__name__)

logging.getLogger("imap_processing").setLevel(logging.WARNING)

import argparse
from pathlib import Path
from spacepy.pycdf import CDF

from mapping_tool.configuration import Configuration


def do_mapping_tool():
    parser = argparse.ArgumentParser()
    parser.add_argument('config_file', type=Path)
    args = parser.parse_args()
    config = Configuration.from_file(args.config_file)

    map_date_ranges = config.canonical_map_period.calculate_date_ranges()

    descriptor = config.get_map_descriptor()
    for start_date, end_date in map_date_ranges:
        map_details = f'{descriptor.to_mapping_tool_string()} {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")}'

        logger.info(f"Generating map: {map_details}")

        generated_map_path = generate_map(descriptor, start_date, end_date)
        map_name_with_quantity_suffix = generated_map_path.name.replace(generated_map_path.name.split("_")[3],
                                                                        descriptor.to_mapping_tool_string())
        output_path = config.output_directory / map_name_with_quantity_suffix
        shutil.copy(generated_map_path, output_path)
        with CDF(str(output_path), readonly=False) as cdf:
            cdf.attrs['Logical_source'] = descriptor.to_mapping_tool_string()
            cdf.attrs['Logical_file_id'] = output_path.stem


if __name__ == "__main__":
    do_mapping_tool()
