import json
import os
import subprocess
import sys
import tempfile
import unittest
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, call, sentinel, Mock

from imap_data_access import ScienceInput, SPICEInput
from imap_processing.ena_maps.utils.naming import MappableInstrumentShortName

import main
from main import do_mapping_tool
from test.test_builders import create_map_descriptor
from test.test_helpers import run_periodically


class TestMain(unittest.TestCase):

    @patch('main.SPICEInput')
    @patch('main.ScienceInput')
    @patch('main.process')
    @patch('main.ProcessingInputCollection')
    @patch('main.Ultra')
    @patch('main.Lo')
    @patch('main.Hi')
    @patch('main.DependencyCollector.collect_spice_kernels')
    @patch('main.DependencyCollector.get_pointing_sets')
    @patch('main.Configuration.from_json')
    @patch('main.argparse.ArgumentParser')
    def test_do_mapping_tool(self, mock_argument_parser_class, mock_configuration_from_json, mock_get_pointing_sets,
                             mock_collect_spice_kernels, mock_hi_processor_class, mock_lo_processor_class,
                             mock_ultra_processor_class,
                             mock_processing_input_collection_class, mock_process, mock_science_input_class,
                             mock_spice_input_class):
        mock_argument_parser = mock_argument_parser_class.return_value
        mock_args = mock_argument_parser.parse_args.return_value
        mock_configuration = mock_configuration_from_json.return_value
        mock_processing_input_collection = mock_processing_input_collection_class.return_value

        hi_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI)
        lo_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.LO)
        ultra_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.ULTRA)

        mock_configuration.get_map_descriptors.return_value = [hi_descriptor, lo_descriptor, ultra_descriptor]
        mock_configuration.canonical_map_period.calculate_date_ranges.return_value = [
            (datetime(2025, 1, 1), datetime(2026, 1, 1)),
            (datetime(2026, 1, 1), datetime(2027, 1, 1))]

        science_input_mocks = defaultdict(Mock)
        spice_input_mocks = defaultdict(Mock)
        mock_science_input_class.side_effect = science_input_mocks.__getitem__
        mock_spice_input_class.side_effect = spice_input_mocks.__getitem__

        mock_get_pointing_sets.return_value = ["some/path/to/imap_hi_l1c_pset_20250101_v001.cdf",
                                               "some/path/to/imap_hi_l1c_pset_20250102_v001.cdf"]

        mock_collect_spice_kernels.return_value = ["naif0012.tls", "imap_sclk_0000.tsc"]

        do_mapping_tool()

        mock_argument_parser_class.assert_called_once()

        mock_argument_parser.add_argument.assert_called_once_with('config_file', type=Path)
        mock_argument_parser.parse_args.assert_called_once()

        mock_configuration_from_json.assert_called_once_with(mock_args.config_file)

        mock_configuration.get_map_descriptors.assert_called_once()
        mock_configuration.canonical_map_period.calculate_date_ranges.assert_called_once()

        mock_get_pointing_sets.assert_has_calls([
            call(hi_descriptor, datetime(2025, 1, 1), datetime(2026, 1, 1)),
            call(hi_descriptor, datetime(2026, 1, 1), datetime(2027, 1, 1)),
            call(lo_descriptor, datetime(2025, 1, 1), datetime(2026, 1, 1)),
            call(lo_descriptor, datetime(2026, 1, 1), datetime(2027, 1, 1)),
            call(ultra_descriptor, datetime(2025, 1, 1), datetime(2026, 1, 1)),
            call(ultra_descriptor, datetime(2026, 1, 1), datetime(2027, 1, 1))
        ])

        mock_collect_spice_kernels.assert_has_calls([
            call(datetime(2025, 1, 1), datetime(2026, 1, 1)),
            call(datetime(2026, 1, 1), datetime(2027, 1, 1))
        ])

        self.assertEqual(6, mock_processing_input_collection_class.call_count)
        mock_processing_input_collection_class.assert_called_with(
            science_input_mocks["imap_hi_l1c_pset_20250101_v001.cdf"],
            science_input_mocks["imap_hi_l1c_pset_20250102_v001.cdf"],
            spice_input_mocks["naif0012.tls"],
            spice_input_mocks["imap_sclk_0000.tsc"],
        )

        mock_hi_processor_class.assert_has_calls([
            call(data_level="l2", data_descriptor=hi_descriptor.to_string(),
                 dependency_str=mock_processing_input_collection.serialize.return_value,
                 start_date="20250101",
                 repointing=None,
                 version="0",
                 upload_to_sdc=False),
            call(data_level="l2", data_descriptor=hi_descriptor.to_string(),
                 dependency_str=mock_processing_input_collection.serialize.return_value,
                 start_date="20260101",
                 repointing=None,
                 version="0",
                 upload_to_sdc=False)
        ])
        mock_lo_processor_class.assert_has_calls([
            call(data_level="l2", data_descriptor=lo_descriptor.to_string(),
                 dependency_str=mock_processing_input_collection.serialize.return_value,
                 start_date="20250101",
                 repointing=None,
                 version="0",
                 upload_to_sdc=False),
            call(data_level="l2", data_descriptor=lo_descriptor.to_string(),
                 dependency_str=mock_processing_input_collection.serialize.return_value,
                 start_date="20260101",
                 repointing=None,
                 version="0",
                 upload_to_sdc=False)
        ])
        mock_ultra_processor_class.assert_has_calls([
            call(data_level="l2", data_descriptor=ultra_descriptor.to_string(),
                 dependency_str=mock_processing_input_collection.serialize.return_value,
                 start_date="20250101",
                 repointing=None,
                 version="0",
                 upload_to_sdc=False),
            call(data_level="l2", data_descriptor=ultra_descriptor.to_string(),
                 dependency_str=mock_processing_input_collection.serialize.return_value,
                 start_date="20260101",
                 repointing=None,
                 version="0",
                 upload_to_sdc=False)
        ])

        self.assertEqual(6, mock_process.call_count)

        mock_process.assert_has_calls([
            call(mock_hi_processor_class.return_value, mock_configuration),
            call(mock_hi_processor_class.return_value, mock_configuration),
            call(mock_lo_processor_class.return_value, mock_configuration),
            call(mock_lo_processor_class.return_value, mock_configuration),
            call(mock_ultra_processor_class.return_value, mock_configuration),
            call(mock_ultra_processor_class.return_value, mock_configuration),
        ])

    @run_periodically
    def test_main_integration(self):
        config_json = {
            "canonical_map_period": {
                "year": 2025,
                "quarter": 3,
                "map_period": 1,
                "number_of_maps": 1
            },
            "instrument": [
                "Hi 90",
                "Lo",
                "Ultra 90"
            ],
            "spin_phase": "Ram",
            "reference_frame": "spacecraft",
            "survival_corrected": True,
            "coordinate_system": "hae",
            "pixelation_scheme": "square",
            "pixel_parameter": 2,
            "map_data_type": "ENA Intensity",
            "lo_species": "h",
            "output_directory": "."
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            tmp_dir = Path(temporary_directory)

            with open(tmp_dir / "config.json", "w") as config_file:
                json.dump(config_json, config_file)

            subprocess.run([sys.executable, main.__file__, "config.json"], cwd=temporary_directory)

            self.assertTrue((tmp_dir / "imap_hi_l2_h90-ena-h-sf-sp-full-hae-4deg-1mo-20250101_v000.cdf").exists())
            self.assertTrue((tmp_dir / "imap_lo_l2_l090-ena-h-sf-sp-full-hae-4deg-1mo-20250101_v000.cdf").exists())
            self.assertTrue((tmp_dir / "imap_ultra_l2_u90-ena-h-sf-sp-full-hae-4deg-1mo-20250101_v000.cdf").exists())
