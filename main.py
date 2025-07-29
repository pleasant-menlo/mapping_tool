import dataclasses
import logging
from datetime import datetime
from typing import Optional
from unittest.mock import Mock

logger = logging.getLogger(__name__)

logging.getLogger("imap_processing").setLevel(logging.WARNING)
# logging.getLogger("imap_data_access").setLevel(logging.WARNING)

import argparse
from pathlib import Path

from imap_data_access import ProcessingInputCollection, ScienceInput, SPICEInput
from imap_processing.cli import Hi, Lo, Ultra
from imap_processing.ena_maps.utils.naming import MappableInstrumentShortName, MapDescriptor

from mapping_tool.configuration import Configuration, DataLevel
from mapping_tool.dependency_collector import DependencyCollector
from mapping_tool.map_generator import process
from imap_l3_processing.maps.hilo_l3_survival_dependencies import HiLoL3SurvivalDependencies
from imap_l3_processing.hi.l3.hi_l3_spectral_fit_dependencies import HiL3SpectralIndexDependencies
from imap_l3_processing.hi.hi_processor import HiProcessor

def get_dependencies_for_l3_map(map_descriptor: MapDescriptor) -> list[MapDescriptor]:
    match map_descriptor:
        case MapDescriptor(principal_data="spx"):
            return [dataclasses.replace(map_descriptor, principal_data="ena")]
        case MapDescriptor(survival_corrected="sp", spin_phase="ram" | "anti"):
            return [dataclasses.replace(map_descriptor, survival_corrected="nsp")]
        case MapDescriptor(survival_corrected="sp", spin_phase="full"):
            return [
                dataclasses.replace(map_descriptor, spin_phase="ram"),
                dataclasses.replace(map_descriptor, spin_phase="anti")
            ]
        case MapDescriptor(sensor="combined"):
            return [
                dataclasses.replace(map_descriptor, sensor="90"),
                dataclasses.replace(map_descriptor, sensor="45"),
            ]


def get_data_level_for_descriptor(descriptor: MapDescriptor):
    data_level = DataLevel.L2
    if descriptor.survival_corrected == "sp" or "combined" == descriptor.sensor or descriptor.principal_data == "spx":
        data_level = DataLevel.L3
    elif descriptor.instrument == MappableInstrumentShortName.GLOWS or descriptor.instrument == MappableInstrumentShortName.IDEX:
        data_level = DataLevel.NA
    return data_level


def generate_map(descriptor, start_date, end_date):
    match get_data_level_for_descriptor():
        case DataLevel.L2:
            generate_l2_map(descriptor, start_date, end_date)
        case DataLevel.L3:
            generate_l3_map(descriptor, start_date, end_date)


def generate_l3_map(descriptor, start_date, end_date) -> Path:
    match descriptor:
        case MapDescriptor(principal_data="spx"):
            dependency_descriptor = dataclasses.replace(descriptor, principal_data="ena")
            input_map_path = generate_map(descriptor, start_date, end_date)
            depedencies = HiL3SpectralIndexDependencies.from_file_paths(input_map_path)

            processor = HiProcessor(ProcessingInputCollection(), Mock())
            processor.do_processing(dependencies)

        case MapDescriptor(survival_corrected="sp", spin_phase="ram" | "anti"):
            return [dataclasses.replace(map_descriptor, survival_corrected="nsp")]
        case MapDescriptor(survival_corrected="sp", spin_phase="full"):
            return [
                dataclasses.replace(map_descriptor, spin_phase="ram"),
                dataclasses.replace(map_descriptor, spin_phase="anti")
            ]
        case MapDescriptor(sensor="combined"):
            return [
                dataclasses.replace(map_descriptor, sensor="90"),
                dataclasses.replace(map_descriptor, sensor="45"),
            ]


    input_maps = [Path() for input_map in ]


    for dependency_descriptor in get_dependencies_for_l3_map(product_descriptor):
        if get_data_level_for_descriptor(product_descriptor) == DataLevel.L3:
            match product_descriptor:
                case MapDescriptor(principal_data="spx"):
                    pass


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
            map_details = f'{descriptor.to_string()} {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")}'
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
