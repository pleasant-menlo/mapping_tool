import logging
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, call, Mock, MagicMock
import imap_data_access
import numpy as np

from imap_processing.ena_maps.utils.naming import MappableInstrumentShortName
from spacepy.pycdf import CDF

import mapping_tool.cli as cli
from mapping_tool.cli import do_mapping_tool, cleanup_l2_l3_dependencies
from mapping_tool.configuration import TimeRange
from mapping_tool.mapping_tool_descriptor import MappingToolDescriptor
from test.test_builders import create_map_descriptor, create_configuration, create_canonical_map_period
from test.test_helpers import run_periodically, get_example_config_path, get_test_cdf_file_path, utcdatetime


class TestCli(unittest.TestCase):

    @patch('mapping_tool.cli.print')
    @patch('mapping_tool.cli.CDF')
    @patch('mapping_tool.cli.shutil.copy')
    @patch('mapping_tool.cli.generate_map')
    @patch('mapping_tool.cli.cleanup_l2_l3_dependencies')
    @patch('mapping_tool.cli.sort_cdfs_by_epoch')
    def test_do_mapping_tool(self, mock_sort_cdfs_by_epoch, mock_cleanup, mock_generate_map, mock_copy_file, mock_cdf, mock_print):
        self.assertTrue(hasattr(cli, "logger"))
        cli.logger.info = Mock()

        mock_configuration = Mock()

        hi_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI, sensor="90",
                                              quantity_suffix="TEST")

        mock_configuration.get_map_descriptor.return_value = hi_descriptor
        mock_configuration.raw_config = "config: something \n another_thing: something_2"

        generated_cdf_path_1 = Path('path/to/cdf/imap_hi_l3_h90-ena-h-sf-sp-ram-hae-2deg-6mo_20250101_v000.cdf')
        generated_cdf_path_2 = Path('path/to/cdf/imap_hi_l3_h90-ena-h-sf-sp-ram-hae-2deg-6mo_20260101_v000.cdf')
        mock_sort_cdfs_by_epoch.return_value = [generated_cdf_path_1, generated_cdf_path_2]
        mock_generate_map.side_effect = [
            generated_cdf_path_1,
            generated_cdf_path_2,
        ]

        map_date_ranges = [
            (datetime(2025, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 1, tzinfo=timezone.utc)),
            (datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2027, 1, 1, tzinfo=timezone.utc))
        ]

        mock_configuration.get_map_date_ranges.return_value = map_date_ranges
        mock_configuration.output_directory = Path("path/to/output")
        mock_configuration.quantity_suffix = "TEST"

        mock_cdf_file_1 = MagicMock()
        mock_cdf_file_2 = MagicMock()
        mock_cdf.return_value.__enter__.side_effect = [mock_cdf_file_1, mock_cdf_file_2]

        mock_cdf_file_1.attrs = {
            "Logical_source": "old logical source",
            "Logical_file_id": "old logical file_id",
            "Data_type": f"L3_{hi_descriptor.to_string()}>other_stuff",
        }

        mock_cdf_file_2.attrs = {
            "Logical_source": "old logical source",
            "Logical_file_id": "old logical file_id",
            "Data_type": f"L3_{hi_descriptor.to_string()}>more_other_stuff",
        }

        do_mapping_tool(mock_configuration)

        self.assertEqual(2, mock_configuration.get_map_descriptor.call_count)
        mock_configuration.get_map_date_ranges.assert_called_once()
        mock_sort_cdfs_by_epoch.assert_called_once_with([generated_cdf_path_1, generated_cdf_path_2])

        output_map_path = str(mock_configuration.output_directory /  'imap_hi_l3_h90-enaTEST-h-sf-sp-ram-hae-2deg-6mo-mapper_20250101_v000.cdf')
        mock_cdf.assert_has_calls([
            call(output_map_path, str(generated_cdf_path_1), readonly=False),
            call().__enter__(),
            call(str(generated_cdf_path_2)),
            call().__enter__(),
            call().__exit__(None, None, None),
            call().__exit__(None, None, None)
        ])
        self.assertEqual(2, mock_cdf.call_count)

        cli.logger.info.assert_has_calls([
            call('Generating map: h90-enaTEST-h-sf-sp-ram-hae-2deg-6mo-mapper 2025-01-01 to 2026-01-01'),
            call('Generating map: h90-enaTEST-h-sf-sp-ram-hae-2deg-6mo-mapper 2026-01-01 to 2027-01-01'),
        ])

        mock_generate_map.assert_has_calls([
            call(hi_descriptor, map_date_ranges[0][0], map_date_ranges[0][1]),
            call(hi_descriptor, map_date_ranges[1][0], map_date_ranges[1][1]),
        ])

        self.assertEqual('h90-enaTEST-h-sf-sp-ram-hae-2deg-6mo-mapper', mock_cdf_file_1.attrs["Logical_source"])
        self.assertEqual(mock_configuration.raw_config, mock_cdf_file_1.attrs.get("Mapper_tool_configuration"))
        self.assertEqual('imap_hi_l3_h90-enaTEST-h-sf-sp-ram-hae-2deg-6mo-mapper_20250101_v000',
                         mock_cdf_file_1.attrs["Logical_file_id"])
        self.assertEqual('L3_h90-enaTEST-h-sf-sp-ram-hae-2deg-6mo-mapper>other_stuff',
                         mock_cdf_file_1.attrs["Data_type"])

        mock_cleanup.assert_called_once_with(hi_descriptor)
        mock_print.assert_has_calls([
            call(f"Created file {output_map_path}")
        ])

    @patch('mapping_tool.cli.generate_map')
    def test_ena_maps_with_multiple_date_ranges_are_concatenated_into_a_single_cdf_file(self, mock_generate_map):
        l2_maps = ("l2_maps", [get_test_cdf_file_path() / 'l2_ena_20250215.cdf', get_test_cdf_file_path() / 'l2_ena_20250115.cdf'])
        l3_maps = ("l3_maps", [get_test_cdf_file_path() / 'l3_ena_20250215.cdf', get_test_cdf_file_path() / 'l3_ena_20250115.cdf'])
        for name, created_maps in [l2_maps, l3_maps]:
            with self.subTest(name):
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmp_path = Path(tmpdir)
                    map_config = create_configuration(
                        output_directory=tmp_path,
                        time_ranges=[TimeRange(utcdatetime(), utcdatetime()), TimeRange(utcdatetime(), utcdatetime())]
                    )

                    mock_generate_map.side_effect = created_maps

                    expected_data_variable_shape = (2, 9, 180, 90)
                    expected_energy_shape= (9,)

                    do_mapping_tool(map_config)

                    generated_cdf = next(tmp_path.glob('*.cdf'))

                    with CDF(str(generated_cdf)) as cdf:
                        expected_epochs = [datetime(2025, 1, 15, 0, 0),
                                           datetime(2025, 2, 15, 0, 0)]
                        np.testing.assert_array_equal(cdf['epoch'][...], expected_epochs)

                        np.testing.assert_array_equal(cdf['epoch_delta'][...], [100, 101])

                        self.assertEqual(expected_data_variable_shape, cdf['exposure_factor'].shape)
                        np.testing.assert_array_equal(cdf['exposure_factor'][:,0,0,0], [1,20])

                        self.assertEqual(expected_data_variable_shape, cdf['obs_date'].shape)
                        np.testing.assert_array_equal(cdf.raw_var('obs_date')[:, 0, 0, 0], [2, 21])

                        self.assertEqual(expected_data_variable_shape, cdf['ena_intensity'].shape)
                        np.testing.assert_array_equal(cdf['ena_intensity'][:, 0, 0, 0], [3, 22])

                        self.assertEqual(expected_data_variable_shape, cdf['ena_intensity_stat_unc'].shape)
                        np.testing.assert_array_equal(cdf['ena_intensity_stat_unc'][:, 0, 0, 0], [4, 23])

                        self.assertEqual(expected_data_variable_shape, cdf['ena_intensity_sys_err'].shape)
                        np.testing.assert_array_equal(cdf['ena_intensity_sys_err'][:, 0, 0, 0], [5, 24])

                        self.assertEqual(expected_data_variable_shape, cdf['obs_date_range'].shape)
                        np.testing.assert_array_equal(cdf['obs_date_range'][:, 0, 0, 0], [6, 25])

                        self.assertEqual(expected_energy_shape, cdf['energy'].shape)



    @patch('mapping_tool.cli.generate_map')
    def test_uses_custom_for_duration_of_custom_time_range_map(self, mock_generate_map):
        l2_maps = [get_test_cdf_file_path() / 'l2_ena_20250215.cdf', get_test_cdf_file_path() / 'l2_ena_20250115.cdf']
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            map_config = create_configuration(
                output_directory=tmp_path,
                time_ranges=[TimeRange(utcdatetime(), utcdatetime()), TimeRange(utcdatetime(), utcdatetime())]
            )

            mock_generate_map.side_effect = l2_maps

            do_mapping_tool(map_config)

            generated_cdf = next(tmp_path.glob('*.cdf'))

            self.assertEqual("imap_hi_l2_h90-ena-h-sf-nsp-ram-eclipj2000-4deg-custom-mapper_20250820_v000.cdf", generated_cdf.name)

            with CDF(str(generated_cdf)) as cdf:
                self.assertEqual("h90-ena-h-sf-nsp-ram-eclipj2000-4deg-custom-mapper", str(cdf.attrs["Logical_source"]))
                self.assertEqual("imap_hi_l2_h90-ena-h-sf-nsp-ram-eclipj2000-4deg-custom-mapper_20250820_v000", str(cdf.attrs["Logical_file_id"]))
                self.assertEqual("L2_h90-ena-h-sf-nsp-ram-eclipj2000-4deg-custom-mapper>Level-2 ENA Intensity Map for Hi90", str(cdf.attrs["Data_type"]))



    @patch('mapping_tool.cli.CDF')
    @patch('mapping_tool.cli.shutil.copy')
    @patch('mapping_tool.cli.cleanup_l2_l3_dependencies')
    @patch('mapping_tool.cli.generate_map')
    @patch('mapping_tool.cli.sort_cdfs_by_epoch')
    def test_generate_maps_raises_exception_when_one_map_fails(self, mock_sort_cdfs_by_epoch, mock_generate_map, mock_cleanup_l2_l3_dependencies,
                                                       _mock_copy, _mock_cdf):
        config = create_configuration(canonical_map_period=create_canonical_map_period(number_of_maps=3))

        mock_generate_map.side_effect = [Path('path/to/imap_l3_hi_h90-enaCUSTOM-h-sf-nsp-ram-eclipj2000-4deg-6mo'),
                                         Exception("Expected failure generating map")]

        with self.assertLogs(cli.logger, logging.ERROR) as log_context:
            do_mapping_tool(config)
        log_message = log_context.output[0]
        self.assertIn("Failed to generate map:", log_message )
        self.assertIn("Expected failure generating map", log_message )

        map_descriptor = MappingToolDescriptor.from_string("h90-ena-h-sf-nsp-ram-eclipj2000-4deg-6mo")


        mock_cleanup_l2_l3_dependencies.assert_called_once_with(map_descriptor)

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

    @patch("mapping_tool.cli.generate_map")
    def test_tool_does_not_generate_map_if_file_already_exists(self, mock_generate_map):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = create_configuration(output_directory=Path(tmpdir))
            existing_file = Path(
                tmpdir) / f"imap_hi_l2_{config.get_map_descriptor().to_mapping_tool_string()}_20250101_v000.cdf"
            existing_file.write_text("text")

            do_mapping_tool(config)

            mock_generate_map.assert_not_called()
            self.assertEqual("text", existing_file.read_text())

    @patch("mapping_tool.cli.generate_map")
    @patch("mapping_tool.cli.save_output_cdf")
    @patch("mapping_tool.cli.cleanup_l2_l3_dependencies")
    @patch("mapping_tool.cli.CDF")
    def test_cleanup_is_called_after_exception_on_save(self, mock_cdf, mock_cleanup, mock_save_output_cdf, mock_generate_map):
        config = create_configuration()

        mock_generate_map.return_value = Path("")
        mock_save_output_cdf.side_effect = Exception("injected exception")

        with self.assertLogs(cli.logger, logging.ERROR) as log_context:
            do_mapping_tool(config)

        mock_cleanup.assert_called_once_with(config.get_map_descriptor())
