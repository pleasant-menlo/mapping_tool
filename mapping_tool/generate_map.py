import dataclasses
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import imap_data_access

from mapping_tool.configuration import DataLevel
from imap_processing.ena_maps.utils.naming import MapDescriptor, MappableInstrumentShortName
from imap_l3_processing.models import InputMetadata
from imap_l3_processing.hi.hi_processor import HiProcessor
from imap_l3_processing.ultra.l3.ultra_processor import UltraProcessor
from imap_l3_processing.lo.lo_processor import LoProcessor
from imap_processing.cli import Hi, Lo, Ultra
from imap_data_access import ProcessingInputCollection, ScienceInput, SPICEInput

from mapping_tool.dependency_collector import DependencyCollector
from mapping_tool.map_generator import logger as logger1
import spiceypy


def get_dependencies_for_l3_map(map_descriptor: MapDescriptor) -> list[MapDescriptor]:
    match map_descriptor:
        case MapDescriptor(principal_data="spx"):
            return [dataclasses.replace(map_descriptor, principal_data="ena")]
        case MapDescriptor(sensor="combined"):
            return [
                dataclasses.replace(map_descriptor, sensor="90"),
                dataclasses.replace(map_descriptor, sensor="45"),
            ]
        case MapDescriptor(survival_corrected="sp", spin_phase="ram" | "anti"):
            return [dataclasses.replace(map_descriptor, survival_corrected="nsp")]
        case MapDescriptor(survival_corrected="sp", spin_phase="full"):
            return [
                dataclasses.replace(map_descriptor, spin_phase="ram"),
                dataclasses.replace(map_descriptor, spin_phase="anti")
            ]
        case _:
            return []


def get_data_level_for_descriptor(descriptor: MapDescriptor):
    if descriptor.instrument == MappableInstrumentShortName.GLOWS or descriptor.instrument == MappableInstrumentShortName.IDEX:
        return DataLevel.NA
    elif descriptor.survival_corrected == "sp" or "combined" == descriptor.sensor or descriptor.principal_data == "spx":
        return DataLevel.L3
    else:
        return DataLevel.L2


def generate_map(descriptor: MapDescriptor, start: datetime, end: datetime) -> Optional[Path]:
    data_level = get_data_level_for_descriptor(descriptor)
    if data_level == DataLevel.L2:
        return generate_l2_map(descriptor, start, end)
    elif data_level == DataLevel.L3:
        map_deps = []
        for dependency in get_dependencies_for_l3_map(descriptor):
            if get_data_level_for_descriptor(dependency) == DataLevel.L2 or DataLevel.L3:
                if (dep := generate_map(dependency, start, end)) is not None:
                    map_deps.append(dep)
        return generate_l3_map(descriptor, start, end, map_deps)
    else:
        print("its a bad level", data_level)
        return None


def generate_l3_map(descriptor: MapDescriptor, start: datetime, end: datetime, input_maps: list[Path]) -> Path:
    processor_class = {
        MappableInstrumentShortName.HI: HiProcessor,
        MappableInstrumentShortName.LO: LoProcessor,
        MappableInstrumentShortName.ULTRA: UltraProcessor,
    }.get(descriptor.instrument)

    input_metadata = InputMetadata(
        instrument=descriptor.instrument.name.lower(),
        data_level='l3',
        start_date=start,
        end_date=end,
        version='v000',
        descriptor=descriptor.to_string(),
    )

    spice_kernel_paths = DependencyCollector.collect_spice_kernels(start_date=start, end_date=end)
    for kernel in spice_kernel_paths:
        kernel_path = imap_data_access.download(kernel)
        spiceypy.furnsh(str(kernel_path))

    processing_input_collection = ProcessingInputCollection(*[ScienceInput(dep.name) for dep in input_maps])

    processor = processor_class(
        processing_input_collection,
        input_metadata
    )

    try:
        processed_files = processor.process()
    except Exception as e:
        raise ValueError(f"Processing for {descriptor.to_string()} failed: {str(e)}")

    if len(processed_files) < 1:
        raise ValueError("L3 processing did not return any files!")
    elif len(processed_files) > 1:
        raise ValueError("L3 processing returned too many files!")

    return processed_files[0]


def generate_l2_map(descriptor: MapDescriptor, start_date: datetime, end_date: datetime) -> Optional[Path]:
    spice_kernel_names = DependencyCollector.collect_spice_kernels(start_date=start_date, end_date=end_date)

    map_details = f'{descriptor.to_string()} {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")}'
    psets = DependencyCollector.get_pointing_sets(descriptor, start_date, end_date)

    logger = logging.getLogger("bob")

    if len(psets) == 0:
        logger.warning(f"No pointing sets found for {map_details}")
        return None

    logger.info(f"Generating map: {map_details}")
    for pset in psets:
        logger.info(Path(pset).name)

    processing_input_collection = ProcessingInputCollection(
        *[ScienceInput(pset) for pset in psets],
        *[SPICEInput(kernel.name) for kernel in spice_kernel_names])

    processor_classes = {
        MappableInstrumentShortName.HI: Hi,
        MappableInstrumentShortName.LO: Lo,
        MappableInstrumentShortName.ULTRA: Ultra,
    }
    # processor = processor_classes[descriptor.instrument](
    #     data_level="l2", data_descriptor=descriptor.to_string(),
    #     dependency_str=processing_input_collection.serialize(),
    #     start_date=start_date.strftime("%Y%m%d"),
    #     repointing=None,
    #     version="0",
    #     upload_to_sdc=False
    # )
    #
    # downloaded_deps = processor.pre_processing()
    # try:
    #     results = processor.do_processing(downloaded_deps)
    # except Exception as e:
    #     logger1.warning(
    #         f" Processor failed when trying to generate map: {processor.descriptor}! Skipping\nexception: {e}")
    #     processor.cleanup()
    #     results = []
    #
    # results = processor.post_processing(results, downloaded_deps)
    #
    # if len(results) > 1:
    #     raise ValueError("Expected L2 processing to only produce a single map!")
    #
    # return next(iter(results), None)
