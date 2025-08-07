import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import skip
from unittest.mock import patch, call, Mock

from imap_processing.ena_maps.utils.naming import MappableInstrumentShortName

import main
from main import do_mapping_tool
from mapping_tool.mapping_tool_descriptor import MappingToolDescriptor
from test.test_builders import create_map_descriptor, create_config_dict, create_configuration, \
    create_canonical_map_period
from test.test_helpers import run_periodically


class TestMain(unittest.TestCase):

    @patch('main.CDF')
    @patch('main.shutil.copy')
    @patch('main.generate_map')
    @patch('main.Configuration.from_file')
    @patch('main.argparse.ArgumentParser')
    def test_do_mapping_tool(self, mock_argument_parser_class, mock_configuration_from_file, mock_generate_map,
                             mock_copy_file, mock_cdf):
        self.assertTrue(hasattr(main, "logger"))
        main.logger = Mock()

        mock_configuration = Mock()

        hi_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI, sensor="90",
                                              quantity_suffix="TEST")

        mock_configuration.get_map_descriptor.return_value = hi_descriptor

        mock_generate_map.side_effect = [
            Path('path/to/cdf/imap_hi_l3_h90-ena-h-sf-sp-ram-hae-2deg-6mo_20250101_v000.cdf'),
            Path('path/to/cdf/imap_hi_l3_h90-ena-h-sf-sp-ram-hae-2deg-6mo_20260101_v000.cdf'),
        ]

        map_date_ranges = [
            (datetime(2025, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 1, tzinfo=timezone.utc)),
            (datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2027, 1, 1, tzinfo=timezone.utc))
        ]

        mock_configuration.canonical_map_period.calculate_date_ranges.return_value = map_date_ranges
        mock_configuration.output_directory = Path("path/to/output")
        mock_configuration.quantity_suffix = "TEST"

        mock_cdf_file_1 = Mock()
        mock_cdf_file_2 = Mock()
        mock_cdf.return_value.__enter__.side_effect = [mock_cdf_file_1, mock_cdf_file_2]

        mock_cdf_file_1.attrs = {
            "Logical_source": "old logical source",
            "Logical_file_id": "old logical file_id",
        }

        mock_cdf_file_2.attrs = {
            "Logical_source": "old logical source",
            "Logical_file_id": "old logical file_id",
        }

        do_mapping_tool(mock_configuration)

        mock_configuration.get_map_descriptor.assert_called_once()
        mock_configuration.canonical_map_period.calculate_date_ranges.assert_called_once()

        main.logger.info.assert_has_calls([
            call('Generating map: h90-enaTEST-h-sf-sp-ram-hae-2deg-6mo 2025-01-01 to 2026-01-01'),
            call('Generating map: h90-enaTEST-h-sf-sp-ram-hae-2deg-6mo 2026-01-01 to 2027-01-01'),
        ])

        mock_generate_map.assert_has_calls([
            call(hi_descriptor, map_date_ranges[0][0], map_date_ranges[0][1]),
            call(hi_descriptor, map_date_ranges[1][0], map_date_ranges[1][1]),
        ])

        self.assertEqual('h90-enaTEST-h-sf-sp-ram-hae-2deg-6mo', mock_cdf_file_1.attrs["Logical_source"])
        self.assertEqual('imap_hi_l3_h90-enaTEST-h-sf-sp-ram-hae-2deg-6mo_20250101_v000',
                         mock_cdf_file_1.attrs["Logical_file_id"])

        self.assertEqual('h90-enaTEST-h-sf-sp-ram-hae-2deg-6mo', mock_cdf_file_2.attrs["Logical_source"])
        self.assertEqual('imap_hi_l3_h90-enaTEST-h-sf-sp-ram-hae-2deg-6mo_20260101_v000',
                         mock_cdf_file_2.attrs["Logical_file_id"])

        mock_copy_file.assert_has_calls([
            call(Path('path/to/cdf/imap_hi_l3_h90-ena-h-sf-sp-ram-hae-2deg-6mo_20250101_v000.cdf'),
                 Path('path/to/output/imap_hi_l3_h90-enaTEST-h-sf-sp-ram-hae-2deg-6mo_20250101_v000.cdf')),
            call(Path('path/to/cdf/imap_hi_l3_h90-ena-h-sf-sp-ram-hae-2deg-6mo_20260101_v000.cdf'),
                 Path('path/to/output/imap_hi_l3_h90-enaTEST-h-sf-sp-ram-hae-2deg-6mo_20260101_v000.cdf')),
        ])

    @patch('main.CDF')
    @patch('main.shutil.copy')
    @patch('main.generate_map')
    def test_continues_to_generate_maps_when_one_fails(self, mock_generate_map, _mock_copy, _mock_cdf):
        config = create_configuration(canonical_map_period=create_canonical_map_period(number_of_maps=3))

        mock_generate_map.side_effect = [Path('path/to/imap_l3_hi_h90-enaCUSTOM-h-sf-nsp-ram-custom-4deg-6mo'),
                                         Exception("failed to generate map"),
                                         Path('path/to/other/imap_l3_hi_h90-enaCUSTOM-h-sf-nsp-ram-custom-4deg-6mo')]

        do_mapping_tool(config)

        map_descriptor = MappingToolDescriptor.from_string("h90-ena-h-sf-nsp-ram-custom-4deg-6mo")

        mock_generate_map.assert_has_calls([
            call(map_descriptor, datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc),
                 datetime(2025, 7, 2, 15, 0, tzinfo=timezone.utc)),
            call(map_descriptor, datetime(2025, 7, 2, 15, 0, tzinfo=timezone.utc),
                 datetime(2026, 1, 1, 6, 0, tzinfo=timezone.utc)),
            call(map_descriptor, datetime(2026, 1, 1, 6, 0, tzinfo=timezone.utc),
                 datetime(2026, 7, 2, 21, 0, tzinfo=timezone.utc)),
        ])

    @run_periodically(timedelta(days=1))
    def test_main_integration(self):
        config_json = {
            "canonical_map_period": {
                "year": 2025,
                "quarter": 3,
                "map_period": 3,
                "number_of_maps": 1
            },
            "instrument": "Hi 90",
            "spin_phase": "Ram",
            "reference_frame": "spacecraft",
            "survival_corrected": True,
            "spice_frame_name": "IMAP_HAE",
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

            print(process_result.stderr)
            self.assertTrue(
                (tmp_dir / "imap_hi_l3_h90-enaTEST-h-sf-sp-ram-custom-4deg-3mo_20250702_v000.cdf").exists())
