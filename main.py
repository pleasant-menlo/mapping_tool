import os

import argparse
from pathlib import Path

from imap_data_access import ProcessingInputCollection, ScienceInput, SPICEInput
from imap_processing.cli import Hi, Lo, Ultra
from imap_processing.ena_maps.utils.naming import MappableInstrumentShortName

from mapping_tool.configuration import Configuration
from mapping_tool.dependency_collector import DependencyCollector
from mapping_tool.map_generator import process


def create_maps():
    pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('config_file', type=Path)
    args = parser.parse_args()
    config = Configuration.from_json(args.config_file)

    descriptor = config.get_map_descriptors()
    for start_date, end_date in config.canonical_map_period.calculate_date_ranges():
        spice_kernel_names = DependencyCollector.collect_spice_kernels(start_date, end_date)
        psets = DependencyCollector.get_pointing_sets(descriptor, start_date, end_date)
        if len(psets) == 0:
            print("No pointing sets found for", descriptor.to_string(), start_date, end_date)
            continue

        print("Generating map: " + descriptor.to_string())
        print('\n'.join([pset.split('/')[-1] for pset in psets]))

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
        process(processor, config)
