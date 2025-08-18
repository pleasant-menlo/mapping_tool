import logging
import shutil
import traceback
from datetime import datetime

import numpy as np

from mapping_tool.generate_map import generate_map, get_data_level_for_descriptor
from mapping_tool.mapping_tool_descriptor import MappingToolDescriptor

logger = logging.getLogger(__name__)

logging.getLogger("imap_processing").setLevel(logging.WARNING)

import argparse
from pathlib import Path
from spacepy.pycdf import CDF

from mapping_tool.configuration import Configuration

import imap_data_access


def get_output_filename(descriptor: MappingToolDescriptor, start_date: datetime):
    data_level = get_data_level_for_descriptor(descriptor)
    return f"imap_{descriptor.instrument.name.lower()}_{data_level}_{descriptor.to_mapping_tool_string()}_{start_date.strftime("%Y%m%d")}_v000.cdf"


def cleanup_l2_l3_dependencies(descriptor: MappingToolDescriptor):
    l2_path = imap_data_access.config["DATA_DIR"] / 'imap' / descriptor.instrument.name.lower() / 'l2'
    l3_path = imap_data_access.config["DATA_DIR"] / 'imap' / descriptor.instrument.name.lower() / 'l3'

    if l2_path.exists():
        logger.info(f"Cleaning up {l2_path}")
        shutil.rmtree(l2_path)
    if l3_path.exists():
        logger.info(f"Cleaning up {l3_path}")
        shutil.rmtree(l3_path)


def do_mapping_tool(config: Configuration):
    map_date_ranges = config.get_map_date_ranges()

    descriptor = config.get_map_descriptor()

    first_start_date = map_date_ranges[0][0]
    output_filename = get_output_filename(descriptor, first_start_date)
    final_output_path = config.output_directory / output_filename
    if final_output_path.exists():
        logger.info(f"Skipping generation of map: {output_filename}, because it already exists!")
        return

    output_map_paths = []
    for start_date, end_date in map_date_ranges:
        map_details = f'{descriptor.to_mapping_tool_string()} {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")}'

        logger.info(f"Generating map: {map_details}")
        try:
            generated_map_path = generate_map(descriptor, start_date, end_date)
            output_map_paths.append(generated_map_path)
        except Exception:
            logger.error(f"Failed to generate map: {map_details} with error\n{traceback.format_exc()}")

    first_map_path = output_map_paths[0]
    with CDF(str(final_output_path), str(first_map_path), readonly=False) as cdf:
        cdf.attrs['Logical_source'] = descriptor.to_mapping_tool_string() + "_generated-by-mapper-tool"
        cdf.attrs['Logical_file_id'] = final_output_path.stem
        cdf.attrs['Mapper_tool_configuration'] = config.raw_config
        cdf.attrs['Data_type'] = cdf.attrs['Data_type'][0].replace(descriptor.to_string(),
                                                                   descriptor.to_mapping_tool_string())
        for additional_map_path in output_map_paths[1:]:
            with CDF(str(additional_map_path)) as additional_map:
                cdf['epoch'][...] = np.concatenate((cdf['epoch'][...], additional_map['epoch'][...]))
                for var in cdf:
                    if "DEPEND_0" in cdf[var].attrs and cdf[var].attrs['DEPEND_0'] == "epoch":
                        cdf[var][...] = np.concatenate((cdf.raw_var(var)[...], additional_map.raw_var(var)[...]))

    cleanup_l2_l3_dependencies(descriptor)


# def concatenate_map_files()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('config_file', type=Path)
    args = parser.parse_args()
    configuration = Configuration.from_file(args.config_file)

    do_mapping_tool(configuration)
