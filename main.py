import logging

logger = logging.getLogger(__name__)

logging.getLogger("imap_processing").setLevel(logging.WARNING)
logging.getLogger("imap_data_access").setLevel(logging.WARNING)

import argparse
from pathlib import Path

from imap_data_access import ProcessingInputCollection, ScienceInput, SPICEInput
from imap_processing.cli import Hi, Lo, Ultra
from imap_processing.ena_maps.utils.naming import MappableInstrumentShortName

from mapping_tool.configuration import Configuration
from mapping_tool.dependency_collector import DependencyCollector
from mapping_tool.map_generator import process


def do_mapping_tool():
    parser = argparse.ArgumentParser()
    parser.add_argument('config_file', type=Path)
    args = parser.parse_args()
    config = Configuration.from_json(args.config_file)

    map_date_ranges = config.canonical_map_period.calculate_date_ranges()
    date_range_and_spice = [(*date_range, DependencyCollector.collect_spice_kernels(*date_range)) for date_range in
                            map_date_ranges]

    for descriptor, _ in config.get_map_descriptors():
        if config.output_files is not None and (descriptor.instrument, descriptor.sensor) in config.output_files:
            filenames_iterator = iter(config.output_files[(descriptor.instrument, descriptor.sensor)])
        else:
            filenames_iterator = iter([])

        for start_date, end_date, spice_kernel_names in date_range_and_spice:
            filename = next(filenames_iterator, None)
            map_details = f"{descriptor.to_string()} {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")}"
            psets = DependencyCollector.get_pointing_sets(descriptor, start_date, end_date)
            if len(psets) == 0:
                logger.warning(f"No pointing sets found for {map_details}")
                continue

            logger.info(f"Generating map: {map_details}")
            for pset in psets:
                logger.info(Path(pset).name)

            processing_input_collection = ProcessingInputCollection(
                *[ScienceInput(Path(pset).name) for pset in psets],
                *[SPICEInput(name) for name in spice_kernel_names])
            processor_classes = {
                MappableInstrumentShortName.HI: Hi,
                MappableInstrumentShortName.LO: Lo,
                MappableInstrumentShortName.ULTRA: Ultra,
            }
            processor = processor_classes[descriptor.instrument](
                data_level="l2", data_descriptor=descriptor.to_string(),
                dependency_str=processing_input_collection.serialize(),
                start_date=start_date.strftime("%Y%m%d"),
                repointing=None,
                version="0",
                upload_to_sdc=False
            )
            process(processor, config.output_directory, filename)


if __name__ == "__main__":
    do_mapping_tool()
