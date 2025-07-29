from datetime import datetime
from pathlib import Path
from typing import Optional

from configuration import DataLevel
from main import get_data_level_for_descriptor, get_dependencies_for_l3_map, logger
from imap_processing.ena_maps.utils.naming import MapDescriptor, MappableInstrumentShortName
from imap_l3_processing.models import InputMetadata
from imap_l3_processing.hi.hi_processor import HiProcessor
from imap_l3_processing.ultra.l3.ultra_processor import UltraProcessor
from imap_l3_processing.lo.lo_processor import LoProcessor
from imap_processing.cli import Hi, Lo, Ultra
from imap_data_access import ProcessingInputCollection, ScienceInput, SPICEInput

from mapping_tool.dependency_collector import DependencyCollector
from mapping_tool.map_generator import process, write_l2_output


def generate_map(descriptor: MapDescriptor, start: datetime, end: datetime) -> Optional[Path]:
    data_level = get_data_level_for_descriptor(descriptor)
    if data_level == DataLevel.L2:
        return generate_l2_map(descriptor, start, end)
    elif data_level == DataLevel.L3:
        map_deps = []
        for dependency in get_dependencies_for_l3_map(descriptor):
            if get_data_level_for_descriptor(dependency) == DataLevel.L2 or DataLevel.L3:
                map_deps.append(generate_map(dependency, start, end))
        return generate_l3_map(descriptor, start, end, map_deps)
    else:
        return None


def generate_l3_map(descriptor: MapDescriptor, start: datetime, end: datetime, input_maps: list[Path]) -> Path:
    # descriptor = 'h90-ena-h-sf-sp-full-hae-4deg-3mo'
    psets = DependencyCollector.get_pointing_sets(descriptor, start, end)
    input_metadata = InputMetadata(
        instrument=descriptor.instrument.value,
        data_level='l3',
        start_date=start,
        end_date=end,
        version='v000',
        descriptor=descriptor.to_string(),
    )
    processing_input_collection = ProcessingInputCollection()
    processing_input_collection.add([ScienceInput(Path(pset).name) for pset in psets])
    processing_input_collection.add([ScienceInput(dep.name) for dep in input_maps])
    spice_kernels = [SPICEInput(spice) for spice in
                     DependencyCollector.collect_spice_kernels(start_date=start, end_date=end)]
    processing_input_collection.add(spice_kernels)

    processor_classes = {
        MappableInstrumentShortName.HI: HiProcessor,
        MappableInstrumentShortName.LO: LoProcessor,
        MappableInstrumentShortName.ULTRA: UltraProcessor,
    }

    processor = processor_classes[descriptor.instrument](
        processing_input_collection,
        input_metadata
    )
    processor.process()


def generate_l2_map(descriptor: MapDescriptor, start_date: datetime, end_date: datetime) -> Optional[Path]:
    spice_kernel_names = DependencyCollector.collect_spice_kernels(start_date=start_date, end_date=end_date)

    map_details = f'{descriptor.to_string()} {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")}'
    psets = DependencyCollector.get_pointing_sets(descriptor, start_date, end_date)
    if len(psets) == 0:
        logger.warning(f"No pointing sets found for {map_details}")
        return None

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
    downloaded_deps = processor.pre_processing()
    try:
        results = processor.do_processing(downloaded_deps)
    except Exception as e:
        logger.warning(
            f" Processor failed when trying to generate map: {processor.descriptor}! Skipping\nexception: {e}")
        processor.cleanup()
        return None
    return write_l2_output(lambda: processor.post_processing(results, downloaded_deps), config.output_directory,
                           filename)
