import json
import os
import subprocess
import sys
import tempfile
import unittest
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import skipIf, skip
from unittest.mock import patch, call, sentinel, Mock

from imap_data_access import ScienceInput, SPICEInput
from imap_processing.ena_maps.utils.naming import MappableInstrumentShortName

import main
from main import do_mapping_tool
from mapping_tool.configuration import DataLevel
from test.test_builders import create_map_descriptor
from test.test_helpers import run_periodically


class TestMain(unittest.TestCase):

    @patch('main.shutil.copy')
    @patch('main.generate_map')
    @patch('main.Configuration.from_file')
    @patch('main.argparse.ArgumentParser')
    def test_do_mapping_tool(self, mock_argument_parser_class, mock_configuration_from_file, mock_generate_map,
                             mock_copy_file):
        self.assertTrue(hasattr(main, "logger"))
        main.logger = Mock()

        mock_argument_parser = mock_argument_parser_class.return_value
        mock_args = mock_argument_parser.parse_args.return_value
        mock_configuration = mock_configuration_from_file.return_value

        hi_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI, sensor="90")
        lo_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.LO, sensor="")
        ultra_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.ULTRA, sensor="45")

        mock_configuration.get_map_descriptors.return_value = [hi_descriptor,
                                                               lo_descriptor,
                                                               ultra_descriptor]

        mock_generate_map.side_effect = [
            Path('path/to/cdf/imap_hi_l3_h90-ena-h-sf-sp-ram-hae-2deg-6mo_20250101_v000.cdf'),
            Path('path/to/cdf/imap_hi_l3_h90-ena-h-sf-sp-ram-hae-2deg-6mo_20260101_v000.cdf'),
            Path('path/to/cdf/imap_lo_l3_ilo-ena-h-sf-sp-ram-hae-2deg-6mo_20250101_v000.cdf'),
            Path('path/to/cdf/imap_lo_l3_ilo-ena-h-sf-sp-ram-hae-2deg-6mo_20260101_v000.cdf'),
            Path('path/to/cdf/imap_ultra_l3_u45-ena-h-sf-sp-ram-hae-2deg-6mo_20250101_v000.cdf'),
            Path('path/to/cdf/imap_ultra_l3_u45-ena-h-sf-sp-ram-hae-2deg-6mo_20260101_v000.cdf')
        ]

        map_date_ranges = [
            (datetime(2025, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 1, tzinfo=timezone.utc)),
            (datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2027, 1, 1, tzinfo=timezone.utc))
        ]

        mock_configuration.canonical_map_period.calculate_date_ranges.return_value = map_date_ranges
        mock_configuration.output_directory = Path("path/to/output")
        mock_configuration.quantity_suffix = "TEST"

        do_mapping_tool()

        mock_argument_parser_class.assert_called_once()

        mock_argument_parser.add_argument.assert_called_once_with('config_file', type=Path)
        mock_argument_parser.parse_args.assert_called_once()

        mock_configuration_from_file.assert_called_once_with(mock_args.config_file)

        mock_configuration.get_map_descriptors.assert_called_once()
        mock_configuration.canonical_map_period.calculate_date_ranges.assert_called_once()

        main.logger.info.assert_has_calls([
            call('Generating map: h90-ena-h-sf-sp-ram-hae-2deg-6mo 2025-01-01 to 2026-01-01'),
            call('Generating map: h90-ena-h-sf-sp-ram-hae-2deg-6mo 2026-01-01 to 2027-01-01'),
            call('Generating map: ilo-ena-h-sf-sp-ram-hae-2deg-6mo 2025-01-01 to 2026-01-01'),
            call('Generating map: ilo-ena-h-sf-sp-ram-hae-2deg-6mo 2026-01-01 to 2027-01-01'),
            call('Generating map: u45-ena-h-sf-sp-ram-hae-2deg-6mo 2025-01-01 to 2026-01-01'),
            call('Generating map: u45-ena-h-sf-sp-ram-hae-2deg-6mo 2026-01-01 to 2027-01-01'),
        ])

        mock_generate_map.assert_has_calls([
            call(hi_descriptor, map_date_ranges[0][0], map_date_ranges[0][1]),
            call(hi_descriptor, map_date_ranges[1][0], map_date_ranges[1][1]),
            call(lo_descriptor, map_date_ranges[0][0], map_date_ranges[0][1]),
            call(lo_descriptor, map_date_ranges[1][0], map_date_ranges[1][1]),
            call(ultra_descriptor, map_date_ranges[0][0], map_date_ranges[0][1]),
            call(ultra_descriptor, map_date_ranges[1][0], map_date_ranges[1][1]),
        ])

        mock_copy_file.assert_has_calls([
            call(Path('path/to/cdf/imap_hi_l3_h90-ena-h-sf-sp-ram-hae-2deg-6mo_20250101_v000.cdf'),
                 Path('path/to/output/imap_hi_l3_h90-enaTEST-h-sf-sp-ram-hae-2deg-6mo_20250101_v000.cdf')),
            call(Path('path/to/cdf/imap_hi_l3_h90-ena-h-sf-sp-ram-hae-2deg-6mo_20260101_v000.cdf'),
                 Path('path/to/output/imap_hi_l3_h90-enaTEST-h-sf-sp-ram-hae-2deg-6mo_20260101_v000.cdf')),
            call(Path('path/to/cdf/imap_lo_l3_ilo-ena-h-sf-sp-ram-hae-2deg-6mo_20250101_v000.cdf'),
                 Path('path/to/output/imap_lo_l3_ilo-enaTEST-h-sf-sp-ram-hae-2deg-6mo_20250101_v000.cdf')),
            call(Path('path/to/cdf/imap_lo_l3_ilo-ena-h-sf-sp-ram-hae-2deg-6mo_20260101_v000.cdf'),
                 Path('path/to/output/imap_lo_l3_ilo-enaTEST-h-sf-sp-ram-hae-2deg-6mo_20260101_v000.cdf')),
            call(Path('path/to/cdf/imap_ultra_l3_u45-ena-h-sf-sp-ram-hae-2deg-6mo_20250101_v000.cdf'),
                 Path('path/to/output/imap_ultra_l3_u45-enaTEST-h-sf-sp-ram-hae-2deg-6mo_20250101_v000.cdf')),
            call(Path('path/to/cdf/imap_ultra_l3_u45-ena-h-sf-sp-ram-hae-2deg-6mo_20260101_v000.cdf'),
                 Path('path/to/output/imap_ultra_l3_u45-enaTEST-h-sf-sp-ram-hae-2deg-6mo_20260101_v000.cdf'))
        ])

    @skip
    @run_periodically(timedelta(days=1))
    def test_main_integration(self):
        config_json = {
            "canonical_map_period": {
                "year": 2025,
                "quarter": 3,
                "map_period": 3,
                "number_of_maps": 1
            },
            "instruments": [
                "Hi 90"
            ],
            "spin_phase": "Ram",
            "reference_frame": "spacecraft",
            "survival_corrected": True,
            "coordinate_system": "hae",
            "pixelation_scheme": "square",
            "pixel_parameter": 4,
            "map_data_type": "ENA Intensity",
            "lo_species": "h",
            "output_directory": ".",
            "quantity_suffix": "test"
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            tmp_dir = Path(temporary_directory)

            with open(tmp_dir / "config.json", "w") as config_file:
                json.dump(config_json, config_file)

            process_result = subprocess.run([sys.executable, main.__file__, "config.json"], cwd=temporary_directory,
                                            text=True, capture_output=True)

            if process_result.returncode != 0:
                self.fail("Process failed:\n" + process_result.stderr)

            expected_stderr_messages = [
                'Generating map: h90-ena-h-sf-sp-ram-hae-2deg-1mo 2025-07-02 to 2025-08-02',
                'imap_hi_l1c_90sensor-pset_20250702_v001.cdf',
                'Writing to: hi90 map.cdf',
                # 'No pointing sets found for ilo-ena-h-sf-sp-ram-hae-2deg-1mo 2025-07-02 to 2025-08-02',
                # 'Generating map: u90-ena-h-sf-sp-ram-hae-2deg-1mo 2025-07-02 to 2025-08-02',
                # 'imap_ultra_l1c_90sensor-spacecraftpset_20250715-repoint00062_v001.cdf',
                # 'Writing to: imap_ultra_l2_u90-ena-h-sf-nsp-full-hae-2deg-0mo_20250702_v000.cdf'
            ]

            for message in expected_stderr_messages:
                self.assertIn(message, process_result.stderr)

            self.assertTrue((tmp_dir / "hi90 map.cdf").exists())
            # self.assertTrue((tmp_dir / "imap_ultra_l2_u90-ena-h-sf-nsp-full-hae-2deg-0mo_20250702_v000.cdf").exists())
