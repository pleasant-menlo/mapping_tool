import logging
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, call, Mock
import imap_data_access

from imap_processing.ena_maps.utils.naming import MappableInstrumentShortName
from spacepy.pycdf import CDF

import main
from main import do_mapping_tool, cleanup_l2_l3_dependencies
from mapping_tool.mapping_tool_descriptor import MappingToolDescriptor
from test.test_builders import create_map_descriptor, create_configuration, create_canonical_map_period
from test.test_helpers import run_periodically, get_example_config_path, get_test_cdf_file_path


class TestMain(unittest.TestCase):

    @patch('main.CDF')
    @patch('main.shutil.copy')
    @patch('main.generate_map')
    @patch('main.cleanup_l2_l3_dependencies')
    def test_do_mapping_tool(self, mock_cleanup, mock_generate_map, mock_copy_file, mock_cdf):
        self.assertTrue(hasattr(main, "logger"))
        main.logger = Mock()

        mock_configuration = Mock()

        hi_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI, sensor="90",
                                              quantity_suffix="TEST")

        mock_configuration.get_map_descriptor.return_value = hi_descriptor
        mock_configuration.raw_config = "config: something \n another_thing: something_2"

        mock_generate_map.side_effect = [
            Path('path/to/cdf/imap_hi_l3_h90-ena-h-sf-sp-ram-hae-2deg-6mo_20250101_v000.cdf'),
            Path('path/to/cdf/imap_hi_l3_h90-ena-h-sf-sp-ram-hae-2deg-6mo_20260101_v000.cdf'),
        ]

        map_date_ranges = [
            (datetime(2025, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 1, tzinfo=timezone.utc)),
            (datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2027, 1, 1, tzinfo=timezone.utc))
        ]

        mock_configuration.get_map_date_ranges.return_value = map_date_ranges
        mock_configuration.output_directory = Path("path/to/output")
        mock_configuration.quantity_suffix = "TEST"

        mock_cdf_file_1 = Mock()
        mock_cdf_file_2 = Mock()
        mock_cdf.return_value.__enter__.side_effect = [mock_cdf_file_1, mock_cdf_file_2]

        mock_cdf_file_1.attrs = {
            "Logical_source": "old logical source",
            "Logical_file_id": "old logical file_id",
            "Data_type": [f"L2_{hi_descriptor.to_string()}>other_stuff"],
        }

        mock_cdf_file_2.attrs = {
            "Logical_source": "old logical source",
            "Logical_file_id": "old logical file_id",
            "Data_type": [f"L2_{hi_descriptor.to_string()}>more_other_stuff"],
        }

        do_mapping_tool(mock_configuration)

        mock_configuration.get_map_descriptor.assert_called_once()
        mock_configuration.get_map_date_ranges.assert_called_once()

        main.logger.info.assert_has_calls([
            call('Generating map: h90-enaTEST-h-sf-sp-ram-hae-2deg-6mo 2025-01-01 to 2026-01-01'),
            call('Generating map: h90-enaTEST-h-sf-sp-ram-hae-2deg-6mo 2026-01-01 to 2027-01-01'),
        ])

        mock_generate_map.assert_has_calls([
            call(hi_descriptor, map_date_ranges[0][0], map_date_ranges[0][1]),
            call(hi_descriptor, map_date_ranges[1][0], map_date_ranges[1][1]),
        ])

        self.assertEqual('h90-enaTEST-h-sf-sp-ram-hae-2deg-6mo_generated-by-mapper-tool', mock_cdf_file_1.attrs["Logical_source"])
        self.assertEqual(mock_configuration.raw_config, mock_cdf_file_1.attrs.get("Mapper_tool_configuration"))
        self.assertEqual('imap_hi_l3_h90-enaTEST-h-sf-sp-ram-hae-2deg-6mo_20250101_v000',
                         mock_cdf_file_1.attrs["Logical_file_id"])
        self.assertEqual('L2_h90-enaTEST-h-sf-sp-ram-hae-2deg-6mo>other_stuff',
                         mock_cdf_file_1.attrs["Data_type"])

        self.assertEqual('h90-enaTEST-h-sf-sp-ram-hae-2deg-6mo_generated-by-mapper-tool', mock_cdf_file_2.attrs["Logical_source"])
        self.assertEqual(mock_configuration.raw_config, mock_cdf_file_2.attrs.get("Mapper_tool_configuration"))
        self.assertEqual('imap_hi_l3_h90-enaTEST-h-sf-sp-ram-hae-2deg-6mo_20260101_v000',
                         mock_cdf_file_2.attrs["Logical_file_id"])
        self.assertEqual('L2_h90-enaTEST-h-sf-sp-ram-hae-2deg-6mo>more_other_stuff',
                         mock_cdf_file_2.attrs["Data_type"])

        mock_copy_file.assert_has_calls([
            call(Path('path/to/cdf/imap_hi_l3_h90-ena-h-sf-sp-ram-hae-2deg-6mo_20250101_v000.cdf'),
                 Path('path/to/output/imap_hi_l3_h90-enaTEST-h-sf-sp-ram-hae-2deg-6mo_20250101_v000.cdf')),
            call(Path('path/to/cdf/imap_hi_l3_h90-ena-h-sf-sp-ram-hae-2deg-6mo_20260101_v000.cdf'),
                 Path('path/to/output/imap_hi_l3_h90-enaTEST-h-sf-sp-ram-hae-2deg-6mo_20260101_v000.cdf')),
        ])

        mock_cleanup.assert_has_calls([
            call(hi_descriptor),
            call(hi_descriptor),
        ])

    @patch('main.generate_map')
    def test_ena_maps_with_multiple_date_ranges_are_concatenated_into_a_single_cdf_file(self, mock_generate_map):
        l2_maps = [get_test_cdf_file_path() / 'l2_ena_20250115.cdf', get_test_cdf_file_path() / 'l2_ena_20250215.cdf']
        l3_maps = [get_test_cdf_file_path() / 'l3_ena_20250115.cdf', get_test_cdf_file_path() / 'l3_ena_20250215.cdf']
        for created_maps in [l2_maps, l3_maps]:
            with self.subTest():
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmp_path = Path(tmpdir)
                    map_config = create_configuration(output_directory=tmp_path)

                    mock_generate_map.side_effect = created_maps

                    expected_ena_intensity_shape = (2, 9, 180, 90)

                    do_mapping_tool(map_config)\

                    generated_cdf = next(tmp_path.glob('*.cdf'))

                    with CDF(str(generated_cdf)) as cdf:
                        self.assertEqual(cdf['epoch'].shape, (2,))
                        self.assertEqual(cdf['ena_intensity'].shape, expected_ena_intensity_shape)



    @patch('main.CDF')
    @patch('main.shutil.copy')
    @patch('main.cleanup_l2_l3_dependencies')
    @patch('main.generate_map')
    def test_continues_to_generate_maps_when_one_fails(self, mock_generate_map, mock_cleanup_l2_l3_dependencies,
                                                       _mock_copy, _mock_cdf):
        config = create_configuration(canonical_map_period=create_canonical_map_period(number_of_maps=3))

        mock_generate_map.side_effect = [Path('path/to/imap_l3_hi_h90-enaCUSTOM-h-sf-nsp-ram-eclipj2000-4deg-6mo'),
                                         Exception("Expected failure generating map"),
                                         Path('path/to/other/imap_l3_hi_h90-enaCUSTOM-h-sf-nsp-ram-eclipj2000-4deg-6mo')]

        with self.assertLogs(main.logger, logging.ERROR) as log_context:
            do_mapping_tool(config)
        log_message = log_context.output[0]
        self.assertIn("Failed to generate map:", log_message )
        self.assertIn("Expected failure generating map", log_message )

        map_descriptor = MappingToolDescriptor.from_string("h90-ena-h-sf-nsp-ram-eclipj2000-4deg-6mo")

        mock_generate_map.assert_has_calls([
            call(map_descriptor, datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc),
                 datetime(2025, 7, 2, 15, 0, tzinfo=timezone.utc)),
            call(map_descriptor, datetime(2025, 7, 2, 15, 0, tzinfo=timezone.utc),
                 datetime(2026, 1, 1, 6, 0, tzinfo=timezone.utc)),
            call(map_descriptor, datetime(2026, 1, 1, 6, 0, tzinfo=timezone.utc),
                 datetime(2026, 7, 2, 21, 0, tzinfo=timezone.utc)),
        ])

        mock_cleanup_l2_l3_dependencies.assert_has_calls([
            call(map_descriptor),
            call(map_descriptor),
            call(map_descriptor)
        ])

    def test_cleanup_dependencies(self):
        for one_of_the_deps_failed_to_generate in [True, False]:
            with self.subTest(f"One of the dependencies failed to generate: {one_of_the_deps_failed_to_generate}"):
                original_imap_data_dir = imap_data_access.config["DATA_DIR"]
                try:
                    with tempfile.TemporaryDirectory() as tmpdir:
                        test_deletes_stuff_here = Path(tmpdir)
                        imap_data_access.config["DATA_DIR"] = test_deletes_stuff_here

                        descriptor = MappingToolDescriptor.from_string("h90-ena-h-sf-sp-full-custom-4deg-6mo")

                        l1c_dir = test_deletes_stuff_here / "imap/hi/l1c/2025/06"
                        l2_imap_data_folder_path = test_deletes_stuff_here / "imap/hi/l2/2025/06/"
                        l3_imap_data_folder_path = test_deletes_stuff_here / "imap/hi/l3/2025/06/"
                        lo_l2_dir = test_deletes_stuff_here / "imap/lo/l2"
                        l1c_dir.mkdir(parents=True)
                        l2_imap_data_folder_path.mkdir(parents=True)
                        lo_l2_dir.mkdir(parents=True)

                        l3 = l3_imap_data_folder_path / "imap_hi_l3_h90-ena-h-sf-sp-full-custom-4deg-6mo_20250606_v000.cdf"
                        l2_ram = l2_imap_data_folder_path / "imap_hi_l2_h90-ena-h-sf-nsp-ram-custom-4deg-6mo_20250606_v000.cdf"
                        l2_anti = l2_imap_data_folder_path / "imap_hi_l2_h90-ena-h-sf-nsp-anti-custom-4deg-6mo_20250606_v000.cdf"
                        l1c = l1c_dir / "imap_hi_l1c_pset_20250606_v000.cdf"

                        if not one_of_the_deps_failed_to_generate:
                            l3_imap_data_folder_path.mkdir(parents=True)
                            l3.touch()

                        l2_ram.touch()
                        l2_anti.touch()
                        l1c.touch()

                        cleanup_l2_l3_dependencies(descriptor)

                        data_folder = test_deletes_stuff_here / "imap"
                        expected_folder_structure = [
                            data_folder / "hi",
                            data_folder / "lo",
                            data_folder / "hi/l1c",
                            data_folder / "lo/l2",
                            data_folder / "hi/l1c/2025",
                            data_folder / "hi/l1c/2025/06",
                            data_folder / "hi/l1c/2025/06/imap_hi_l1c_pset_20250606_v000.cdf",
                        ]

                        self.assertEqual(expected_folder_structure, list(data_folder.rglob("*")))
                finally:
                    imap_data_access.config["DATA_DIR"] = original_imap_data_dir

    @patch("main.generate_map")
    def test_tool_does_not_generate_map_if_file_already_exists(self, mock_generate_map):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = create_configuration(output_directory=Path(tmpdir))
            existing_file = Path(
                tmpdir) / f"imap_hi_l2_{config.get_map_descriptor().to_mapping_tool_string()}_20250101_v000.cdf"
            existing_file.write_text("text")

            do_mapping_tool(config)

            mock_generate_map.assert_not_called()
            self.assertEqual("text", existing_file.read_text())

    @run_periodically(timedelta(days=1))
    def test_main_integration(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            tmp_dir = Path(temporary_directory)

            shutil.copy(get_example_config_path() / "integration_test_config.json", tmp_dir / "config.json")
            shutil.copy(get_example_config_path() / "imap_science_100.tf", tmp_dir / "spice_kernel.tf")

            process_result = subprocess.run([sys.executable, main.__file__, "config.json"], cwd=temporary_directory,
                                            text=True)

            if process_result.returncode != 0:
                self.fail("Process failed:\n" + process_result.stderr)

            self.assertTrue(
                (tmp_dir / "imap_hi_l3_h90-enaTEST-h-sf-sp-ram-imaphae-4deg-3mo_20250702_v000.cdf").exists())
