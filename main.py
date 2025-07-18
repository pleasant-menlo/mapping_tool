import argparse
from pathlib import Path

from imap_data_access import ProcessingInputCollection, ScienceInput
from imap_processing.ena_maps.utils.naming import MappableInstrumentShortName

from mapping_tool.configuration import Configuration
from mapping_tool.hi_map_generator import HiMapGenerator


def create_maps():
    pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('config_file', type=Path)
    args = parser.parse_args()
    config = Configuration.from_json(args.config_file)
    descriptor = config.get_map_descriptors()
    if descriptor.instrument == MappableInstrumentShortName.HI:
        HiMapGenerator(config).make_map(descriptor.to_string(), ProcessingInputCollection(ScienceInput("imap_hi_l1c_90sensor-pset_20260401_v001.cdf")))

