import logging
import shutil
import traceback
from datetime import datetime

from mapping_tool.generate_map import generate_map, get_dependencies_for_l3_map, get_data_level_for_descriptor
from mapping_tool.mapping_tool_descriptor import MappingToolDescriptor

logger = logging.getLogger(__name__)

logging.getLogger("imap_processing").setLevel(logging.WARNING)

import argparse
from pathlib import Path
from spacepy.pycdf import CDF

from mapping_tool.configuration import Configuration

from imap_data_access import ScienceFilePath


def cleanup_l2_l3_dependencies(descriptor: MappingToolDescriptor, start_date: datetime):
    data_level = get_data_level_for_descriptor(descriptor)
    filename = f"imap_{descriptor.instrument.name.lower()}_{data_level}_{descriptor.to_string()}_{start_date.strftime("%Y%m%d")}_v000.cdf"
    file_path = ScienceFilePath(filename)
    file_path.construct_path().unlink(missing_ok=True)

    dependencies = get_dependencies_for_l3_map(descriptor)
    for dependency in dependencies:
        cleanup_l2_l3_dependencies(dependency, start_date)


def do_mapping_tool(config: Configuration):
    map_date_ranges = config.canonical_map_period.calculate_date_ranges()

    descriptor = config.get_map_descriptor()
    for start_date, end_date in map_date_ranges:
        map_details = f'{descriptor.to_mapping_tool_string()} {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")}'

        logger.info(f"Generating map: {map_details}")
        try:
            generated_map_path = generate_map(descriptor, start_date, end_date)
            map_name_with_quantity_suffix = generated_map_path.name.replace(generated_map_path.name.split("_")[3],
                                                                            descriptor.to_mapping_tool_string())
            output_path = config.output_directory / map_name_with_quantity_suffix
            shutil.copy(generated_map_path, output_path)
            with CDF(str(output_path), readonly=False) as cdf:
                cdf.attrs['Logical_source'] = descriptor.to_mapping_tool_string()
                cdf.attrs['Logical_file_id'] = output_path.stem
        except Exception:
            logger.error(f"Failed to generate map: {map_details} with error\n{traceback.format_exc()}")
        finally:
            cleanup_l2_l3_dependencies(descriptor, start_date)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('config_file', type=Path)
    args = parser.parse_args()
    configuration = Configuration.from_file(args.config_file)

    do_mapping_tool(configuration)
