import argparse
from pathlib import Path

from imap_data_access import ProcessingInputCollection, ScienceInput
from imap_processing.ena_maps.utils.naming import MappableInstrumentShortName

from mapping_tool.configuration import Configuration
from mapping_tool.dependency_collector import DependencyCollector
from mapping_tool.hi_map_generator import HiMapGenerator


def create_maps():
    pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('config_file', type=Path)
    args = parser.parse_args()
    config = Configuration.from_json(args.config_file)
    descriptor = config.get_map_descriptors()
    start_date, end_date = config.canonical_map_period.calculate_date_range()

    psets = DependencyCollector.get_pointing_sets(descriptor, start_date, end_date)
    DependencyCollector.furnish_spice(start_date, end_date)

    print("Generating map: " + descriptor.to_string())
    print('\n'.join([pset.split('/')[-1] for pset in psets]))

    processing_input_collection = ProcessingInputCollection(*[ScienceInput(Path(pset).name) for pset in psets])

    if descriptor.instrument == MappableInstrumentShortName.HI:
        if "h45-ena-h-sf-full-hae-4deg" in descriptor.to_string() or "h90-ena-h-sf-full-hae-4deg" in descriptor.to_string():
            HiMapGenerator(config).make_map(descriptor.to_string(), start_date, processing_input_collection)
        else:
            raise Exception(f"L2 processing code not implemented for map: {descriptor.to_string()}")
