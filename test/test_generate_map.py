import dataclasses
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, Mock, call

from imap_processing.ena_maps.utils.naming import MappableInstrumentShortName
from imap_l3_processing.models import InputMetadata
from imap_data_access import ProcessingInputCollection, ScienceInput, SPICEInput

from mapping_tool.configuration import DataLevel
from mapping_tool.generate_map import get_dependencies_for_l3_map, get_data_level_for_descriptor, generate_l3_map, \
    generate_l2_map
from test.test_builders import create_map_descriptor, create_l2_map_descriptor


class TestGenerateMap(unittest.TestCase):
    def test_get_dependencies_for_l3_map_returns_correct_dependencies(self):
        spectral_index_descriptor = create_map_descriptor(principal_data="spx")
        ena_descriptor = create_map_descriptor(principal_data="ena")

        sp_ram_descriptor = create_map_descriptor(survival_corrected="sp", spin_phase="ram")
        nsp_ram_descriptor = create_map_descriptor(survival_corrected="nsp", spin_phase="ram")

        sp_anti_descriptor = create_map_descriptor(survival_corrected="sp", spin_phase="anti")
        nsp_anti_descriptor = create_map_descriptor(survival_corrected="nsp", spin_phase="anti")

        sp_full_descriptor = create_map_descriptor(survival_corrected="sp", spin_phase="full")

        combined_descriptor = create_map_descriptor(sensor="combined")
        sensor90_descriptor = create_map_descriptor(sensor="90")
        sensor45_descriptor = create_map_descriptor(sensor="45")

        descriptor_with_no_dependencies = create_map_descriptor(survival_corrected="nsp", sensor="90")

        cases = [
            (spectral_index_descriptor, [ena_descriptor]),
            (sp_ram_descriptor, [nsp_ram_descriptor]),
            (sp_anti_descriptor, [nsp_anti_descriptor]),
            (sp_full_descriptor, [sp_ram_descriptor, sp_anti_descriptor]),
            (combined_descriptor, [sensor90_descriptor, sensor45_descriptor]),
            (descriptor_with_no_dependencies, []),
        ]

        for input_descriptor, expected_dependencies in cases:
            with self.subTest(input_descriptor.to_string()):
                actual_dependencies = get_dependencies_for_l3_map(input_descriptor)
                self.assertEqual(expected_dependencies, actual_dependencies)

    def test_get_data_level_for_descriptor_returns_correct_data_level(self):
        sp_descriptor = create_map_descriptor(survival_corrected="sp")
        combined_descriptor = create_map_descriptor(sensor="combined")
        spx_descriptor = create_map_descriptor(principal_data="spx")
        glows_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.GLOWS)
        idex_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.IDEX)
        l2_nsp_descriptor = create_map_descriptor(survival_corrected="nsp")

        cases = [
            (sp_descriptor, DataLevel.L3),
            (combined_descriptor, DataLevel.L3),
            (spx_descriptor, DataLevel.L3),
            (glows_descriptor, DataLevel.NA),
            (idex_descriptor, DataLevel.NA),
            (l2_nsp_descriptor, DataLevel.L2)
        ]

        for descriptor, expected_data_level in cases:
            with self.subTest(descriptor.to_string()):
                actual_data_level = get_data_level_for_descriptor(descriptor)
                self.assertEqual(expected_data_level, actual_data_level)

    @patch('mapping_tool.generate_map.spiceypy.furnsh')
    @patch('mapping_tool.generate_map.imap_data_access.download')
    @patch("mapping_tool.generate_map.DependencyCollector.collect_spice_kernels")
    @patch("mapping_tool.generate_map.HiProcessor")
    @patch("mapping_tool.generate_map.LoProcessor")
    @patch("mapping_tool.generate_map.UltraProcessor")
    def test_generate_l3_map(self, mock_ultra, mock_lo, mock_hi, mock_collect_spice_kernels, mock_download,
                             mock_furnsh):
        hi_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI)
        lo_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.LO)
        ultra_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.ULTRA)

        cases = [
            (hi_descriptor, mock_hi),
            (lo_descriptor, mock_lo),
            (ultra_descriptor, mock_ultra),
        ]

        start_date = datetime(2020, 1, 1)
        end_date = datetime(2020, 1, 2)

        for descriptor, mock_processor in cases:
            with self.subTest(descriptor.to_string()):
                mock_collect_spice_kernels.reset_mock()
                mock_download.reset_mock()
                mock_furnsh.reset_mock()

                mock_collect_spice_kernels.return_value = [Path('spice_1'), Path('spice_2')]
                mock_download.return_value = Path('path/to/spice_file')

                expected_path = Path('returned_path')
                mock_processor.return_value.process.return_value = [expected_path]
                actual_path = generate_l3_map(descriptor, start_date, end_date,
                                              [Path("imap_hi_l2_h90-ena-h-sf-nsp-ram-hae-4deg-6mo_20250101_v000.cdf"),
                                               Path("imap_hi_l2_h90-ena-h-sf-nsp-ram-hae-4deg-6mo_20250102_v001.cdf")])
                self.assertEqual(expected_path, actual_path)
                expected_science_inputs = [
                    "imap_hi_l2_h90-ena-h-sf-nsp-ram-hae-4deg-6mo_20250101_v000.cdf",
                    "imap_hi_l2_h90-ena-h-sf-nsp-ram-hae-4deg-6mo_20250102_v001.cdf"
                ]

                expected_input_metadata = InputMetadata(
                    instrument=descriptor.instrument.name.lower(),
                    data_level='l3',
                    start_date=start_date,
                    end_date=end_date,
                    version='v000',
                    descriptor=descriptor.to_string(),
                )

                actual_processing_input_collection, actual_input_metadata = mock_processor.call_args.args
                actual_input_filename_lists = [processing_input.filename_list[0] for processing_input in
                                               actual_processing_input_collection.processing_input]
                self.assertEqual(expected_science_inputs, actual_input_filename_lists)
                self.assertEqual(expected_input_metadata, actual_input_metadata)

                mock_collect_spice_kernels.assert_called_once_with(start_date=start_date, end_date=end_date)

                mock_download.assert_has_calls([
                    call(Path('spice_1')),
                    call(Path('spice_2')),
                ])

                mock_furnsh.assert_has_calls([
                    call('path/to/spice_file'),
                    call('path/to/spice_file'),
                ])

                mock_processor.return_value.process.assert_called_once()

    @patch("mapping_tool.generate_map.DependencyCollector.collect_spice_kernels")
    @patch("mapping_tool.generate_map.spiceypy.furnsh")
    @patch("mapping_tool.generate_map.imap_data_access.download")
    @patch("mapping_tool.generate_map.HiProcessor")
    def test_generate_l3_map_raises_processing_failed_exception(self, mock_hi, mock_download, mock_furnsh,
                                                                mock_collect_spice_kernels):
        mock_collect_spice_kernels.return_value = []

        error_cases = [
            ("L3 processing did not return any files!", []),
            ("L3 processing returned too many files!", [Path(""), Path("")])
        ]

        for err_string, returned_paths in error_cases:
            with self.subTest(err_string):
                mock_hi.return_value.process.return_value = returned_paths

                with self.assertRaises(ValueError) as e:
                    generate_l3_map(create_map_descriptor(), datetime(2020, 1, 1, tzinfo=timezone.utc),
                                    datetime(2020, 1, 2, tzinfo=timezone.utc), [])

                self.assertIn(err_string, str(e.exception))

    @patch("mapping_tool.generate_map.DependencyCollector.collect_spice_kernels")
    @patch("mapping_tool.generate_map.spiceypy.furnsh")
    @patch("mapping_tool.generate_map.imap_data_access.download")
    @patch("mapping_tool.generate_map.HiProcessor.process")
    def test_generate_l3_map_gracefully_handles_processing_exceptions(self, mock_process, mock_download,
                                                                      mock_furnsh, mock_collect_spice_kernels):
        mock_collect_spice_kernels.return_value = []
        mock_process.side_effect = ValueError("L3 processing failed")

        hi_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI)
        with self.assertRaises(ValueError) as e:
            generate_l3_map(hi_descriptor, datetime(2020, 1, 1, tzinfo=timezone.utc),
                            datetime(2020, 1, 2, tzinfo=timezone.utc), [])
        self.assertEqual(f"Processing for {hi_descriptor.to_string()} failed: L3 processing failed", str(e.exception))

    @patch("mapping_tool.generate_map.DependencyCollector.collect_spice_kernels")
    @patch("mapping_tool.generate_map.DependencyCollector.get_pointing_sets")
    @patch("mapping_tool.generate_map.Hi")
    @patch("mapping_tool.generate_map.Lo")
    @patch("mapping_tool.generate_map.Ultra")
    def test_generate_l2_map(self, mock_ultra, mock_lo, mock_hi, mock_get_pointing_sets, mock_collect_spice_kernels):
        mock_collect_spice_kernels.return_value = [Path("spice_file_1"), Path("spice_file_2")]
        mock_get_pointing_sets.return_value = ["pset_1", "pset_2"]
        hi_descriptor = create_l2_map_descriptor(instrument=MappableInstrumentShortName.HI)
        lo_descriptor = create_l2_map_descriptor(instrument=MappableInstrumentShortName.LO)
        ultra_descriptor = create_l2_map_descriptor(instrument=MappableInstrumentShortName.ULTRA)

        cases = [
            (hi_descriptor, mock_hi),
            (lo_descriptor, mock_lo),
            (ultra_descriptor, mock_ultra),
        ]

        start_date = datetime(2020, 1, 1)
        end_date = datetime(2020, 1, 2)

        for descriptor, mock_processor in cases:
            with self.subTest(descriptor.to_string()):
                generate_l2_map(descriptor, start_date, end_date)

                mock_collect_spice_kernels.assert_called_once_with(start_date=start_date, end_date=end_date)
                mock_get_pointing_sets.assert_called_once_with(descriptor, start_date, end_date)

                expected_dependency_str = ProcessingInputCollection(
                    ScienceInput("pset_1"), ScienceInput("pset_2"),
                    SPICEInput("spice_file_1"), SPICEInput("spice_file_2")
                ).serialize()

                mock_processor.assert_called_once_with(
                    data_level="l2", data_descriptor=descriptor.to_string(),
                    dependency_str=expected_dependency_str,
                    start_date=start_date.strftime("%Y%m%d"),
                    repointing=None,
                    version="0",
                    upload_to_sdc=False
                )

                mock_processor.return_value.pre_processing.assert_called_once()

                pre_processing_result = mock_processor.return_value.pre_processing.return_value
                mock_processor.return_value.do_processing.assert_called_once_with(pre_processing_result)

                do_processing_result = mock_processor.return_value.do_processing.return_value
                mock_processor.return_value.post_processing.assert_called_once_with(
                    do_processing_result, pre_processing_result)
