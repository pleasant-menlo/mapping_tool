import dataclasses
import logging
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, Mock, call

from imap_processing.ena_maps.utils.naming import MappableInstrumentShortName, MapDescriptor
from imap_l3_processing.models import InputMetadata
from imap_data_access import ProcessingInputCollection, ScienceInput, SPICEInput
from imap_processing.spice.geometry import SpiceFrame

from mapping_tool.configuration import DataLevel
from mapping_tool.generate_map import get_dependencies_for_l3_map, get_data_level_for_descriptor, generate_l3_map, \
    generate_l2_map, generate_map
from test.test_builders import create_map_descriptor


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

        descriptor_with_no_dependencies = create_map_descriptor(sensor="90", survival_corrected="nsp")

        cases = [
            (spectral_index_descriptor, [ena_descriptor]),
            (sp_ram_descriptor, [nsp_ram_descriptor]),
            (sp_anti_descriptor, [nsp_anti_descriptor]),
            (sp_full_descriptor, [nsp_ram_descriptor, nsp_anti_descriptor]),
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

    @patch('mapping_tool.generate_map.generate_l3_map')
    @patch('mapping_tool.generate_map.generate_l2_map')
    def test_generate_map(self, mock_generate_l2, mock_generate_l3):
        map_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI, principal_data="spx",
                                               spin_phase="full")

        l2_ram_map = Path("ram")
        l2_antiram_map = Path("anti")
        l3_full_map = Path("full")
        l3_spx_map = Path("spx")
        mock_generate_l2.side_effect = [l2_ram_map, l2_antiram_map]
        mock_generate_l3.side_effect = [l3_full_map, l3_spx_map]

        start_date = datetime(2020, 1, 1)
        end_date = datetime(2020, 7, 1)

        output_map = generate_map(map_descriptor, start_date, end_date)

        mock_generate_l2.assert_has_calls([
            call(create_map_descriptor(instrument=MappableInstrumentShortName.HI, survival_corrected='nsp',
                                       spin_phase="ram"), start_date, end_date),
            call(create_map_descriptor(instrument=MappableInstrumentShortName.HI, survival_corrected='nsp',
                                       spin_phase="anti"), start_date, end_date),
        ])

        mock_generate_l3.assert_has_calls([
            call(create_map_descriptor(instrument=MappableInstrumentShortName.HI, spin_phase="full"), start_date,
                 end_date, [l2_ram_map, l2_antiram_map]),
            call(create_map_descriptor(instrument=MappableInstrumentShortName.HI, principal_data='spx',
                                       spin_phase="full"), start_date, end_date, [l3_full_map]),
        ])

        self.assertEqual(l3_spx_map, output_map)

    def test_generate_l3_map_raises_exception_when_called_with_non_l2_or_l3_map(self):
        map_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.GLOWS, principal_data="spx",
                                               spin_phase="full")
        start_date = datetime(2020, 1, 1)
        end_date = datetime(2020, 7, 1)

        with self.assertRaises(ValueError) as context:
            generate_map(map_descriptor, start_date, end_date)

        self.assertIn(f"Cannot produce map for instrument: {map_descriptor.instrument_descriptor}",
                      str(context.exception))

    @patch('mapping_tool.generate_map.spiceypy.furnsh')
    @patch('mapping_tool.generate_map.imap_data_access.download')
    @patch("mapping_tool.generate_map.DependencyCollector.collect_spice_kernels")
    @patch("mapping_tool.generate_map.HiProcessor")
    @patch("mapping_tool.generate_map.LoProcessor")
    @patch("mapping_tool.generate_map.UltraProcessor")
    def test_generate_l3_map(self, mock_ultra, mock_lo, mock_hi, mock_collect_spice_kernels, mock_download,
                             mock_furnsh):
        hi_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI,
                                              kernel_path=Path('custom/kernel/path'))
        lo_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.LO,
                                              kernel_path=Path('custom/kernel/path'))
        ultra_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.ULTRA,
                                                 kernel_path=Path('custom/kernel/path'))

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

                mock_processor.return_value.process.assert_called_once_with(descriptor.spice_frame)
                mock_collect_spice_kernels.assert_called_once_with(start_date=start_date, end_date=end_date)

                mock_download.assert_has_calls([
                    call(Path('spice_1')),
                    call(Path('spice_2')),
                ])

                mock_furnsh.assert_has_calls([
                    call(os.path.join('path', 'to', 'spice_file')),
                    call(os.path.join('path', 'to', 'spice_file')),
                    call(os.path.join('custom', 'kernel', 'path')),
                ])

                mock_processor.return_value.process.assert_called_once()

    @patch("mapping_tool.generate_map.DependencyCollector.collect_spice_kernels")
    @patch("mapping_tool.generate_map.spiceypy.furnsh")
    @patch("mapping_tool.generate_map.imap_data_access.download")
    @patch("mapping_tool.generate_map.HiProcessor")
    def test_generate_l3_map_raises_error_when_less_or_more_than_one_file_is_returned(self, mock_hi, mock_download,
                                                                                      mock_furnsh,
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
                    logger = logging.getLogger('generate_l2_map')
                    with self.assertLogs(logger, logging.ERROR) as log_context:
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
            logger = logging.getLogger('generate_l2_map')
            with self.assertLogs(logger, logging.ERROR) as log_context:
                generate_l3_map(hi_descriptor, datetime(2020, 1, 1, tzinfo=timezone.utc),
                                datetime(2020, 1, 2, tzinfo=timezone.utc), [])
        self.assertIn(f"Processing for {hi_descriptor.to_string()} failed",
                      str(e.exception.__notes__))

    @patch("mapping_tool.generate_map.spiceypy")
    @patch("mapping_tool.generate_map.DependencyCollector.collect_spice_kernels")
    @patch("mapping_tool.generate_map.DependencyCollector.get_pointing_sets")
    @patch("mapping_tool.generate_map.Hi")
    @patch("mapping_tool.generate_map.Lo")
    @patch("mapping_tool.generate_map.Ultra")
    def test_generate_l2_map(self, mock_ultra, mock_lo, mock_hi, mock_get_pointing_sets, mock_collect_spice_kernels,
                             mock_spiceypy):
        mock_collect_spice_kernels.return_value = ["imap_science_0001.tf", "imap_sclk_0000.tsc"]
        mock_get_pointing_sets.return_value = ["imap_hi_l1c_pset-1_20250101_v000.cdf",
                                               "imap_hi_l1c_pset-2_20250101_v000.cdf"]
        hi_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI, survival_corrected="nsp",
                                              kernel_path=Path("path1"))
        lo_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.LO, survival_corrected="nsp",
                                              kernel_path=Path("path2"))
        ultra_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.ULTRA, survival_corrected="nsp")

        cases = [
            (hi_descriptor, mock_hi, 1),
            (lo_descriptor, mock_lo, 0),
            (ultra_descriptor, mock_ultra, 0),
        ]

        start_date = datetime(2020, 1, 1)
        end_date = datetime(2020, 1, 2)

        for descriptor, mock_processor_class, num_furnsh_calls in cases:
            with self.subTest(descriptor.to_string()):
                mock_collect_spice_kernels.reset_mock()
                mock_get_pointing_sets.reset_mock()
                expected_map = Mock()
                mock_processor = mock_processor_class.return_value
                mock_processor.post_processing.return_value = [expected_map]

                actual_map = generate_l2_map(descriptor, start_date, end_date)

                mock_collect_spice_kernels.assert_called_once_with(start_date=start_date, end_date=end_date)
                mock_get_pointing_sets.assert_called_once_with(descriptor, start_date, end_date)

                expected_dependency_str = ProcessingInputCollection(
                    ScienceInput("imap_hi_l1c_pset-1_20250101_v000.cdf"),
                    ScienceInput("imap_hi_l1c_pset-2_20250101_v000.cdf"),
                    SPICEInput("imap_science_0001.tf"), SPICEInput("imap_sclk_0000.tsc")
                ).serialize()

                mock_processor_class.assert_called_once_with(
                    data_level="l2", data_descriptor=descriptor.to_string(),
                    dependency_str=expected_dependency_str,
                    start_date=start_date.strftime("%Y%m%d"),
                    repointing=None,
                    version="0",
                    upload_to_sdc=False
                )

                mock_processor.pre_processing.assert_called_once()

                pre_processing_result = mock_processor.pre_processing.return_value
                mock_processor.do_processing.assert_called_once_with(pre_processing_result)

                do_processing_result = mock_processor.do_processing.return_value
                mock_processor.post_processing.assert_called_once_with(
                    do_processing_result, pre_processing_result)

                mock_processor.cleanup.assert_called_once()

                self.assertEqual(expected_map, actual_map)

        mock_spiceypy.furnsh.assert_has_calls([
            call("path1"),
            call("path2")
        ])
        self.assertEqual(2, mock_spiceypy.furnsh.call_count)

    @patch("mapping_tool.generate_map.DependencyCollector.collect_spice_kernels")
    @patch("mapping_tool.generate_map.DependencyCollector.get_pointing_sets")
    @patch("mapping_tool.generate_map.Hi")
    def test_generate_l2_map_patches_l2_processing_get_map_coord_frame(self, mock_hi_processor_class,
                                                                       mock_get_pointing_sets,
                                                                       mock_collect_spice_kernels):
        mock_hi_processor = mock_hi_processor_class.return_value
        mock_collect_spice_kernels.return_value = ["imap_science_0001.tf", "imap_sclk_0000.tsc"]
        mock_get_pointing_sets.return_value = ["imap_hi_l1c_pset-1_20250101_v000.cdf",
                                               "imap_hi_l1c_pset-2_20250101_v000.cdf"]

        start_date = datetime(2020, 1, 1)
        end_date = datetime(2020, 1, 2)
        descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI, spice_frame=SpiceFrame.IMAP_RTN)

        def mock_do_processing(deps):
            self.assertEqual(deps, mock_hi_processor.pre_processing.return_value)
            self.assertEqual(SpiceFrame.IMAP_RTN,
                             MapDescriptor.from_string(descriptor.to_string()).map_spice_coord_frame)

        mock_hi_processor.post_processing.return_value = [Path("some_path")]
        mock_hi_processor.do_processing.side_effect = mock_do_processing

        _ = generate_l2_map(descriptor, start_date, end_date)

        normal_pipeline_descriptor = "h90-ena-h-sf-nsp-ram-hae-2deg-6mo"
        self.assertEqual(SpiceFrame.IMAP_HAE,
                         MapDescriptor.from_string(normal_pipeline_descriptor).map_spice_coord_frame)

    @patch("mapping_tool.generate_map.DependencyCollector.get_pointing_sets")
    @patch("mapping_tool.generate_map.DependencyCollector.collect_spice_kernels")
    @patch("mapping_tool.generate_map.Hi")
    def test_generate_l2_map_raises_error_when_less_or_more_than_one_file_is_returned(self, mock_hi,
                                                                                      mock_collect_spice_kernels,
                                                                                      mock_get_pointing_sets):
        mock_collect_spice_kernels.return_value = []
        mock_get_pointing_sets.return_value = ["imap_hi_l1c_pset_20250101_v000.cdf"]

        error_cases = [
            ("L2 processing did not return any files!", []),
            ("L2 processing returned too many files!", [Path(""), Path("")])
        ]

        for err_string, returned_paths in error_cases:
            with self.subTest(err_string):
                mock_hi.return_value.post_processing.return_value = returned_paths
                with self.assertRaises(ValueError) as e:
                    generate_l2_map(create_map_descriptor(), datetime(2020, 1, 1, tzinfo=timezone.utc),
                                    datetime(2020, 1, 2, tzinfo=timezone.utc))

                self.assertIn(err_string, str(e.exception))

    @patch("mapping_tool.generate_map.DependencyCollector.get_pointing_sets")
    @patch("mapping_tool.generate_map.DependencyCollector.collect_spice_kernels")
    @patch("mapping_tool.generate_map.Hi")
    def test_generate_l2_map_gracefully_handles_processing_exceptions(self, mock_hi,
                                                                      mock_collect_spice_kernels,
                                                                      mock_get_pointing_sets):
        mock_collect_spice_kernels.return_value = []
        mock_get_pointing_sets.return_value = ["imap_hi_l1c_pset_20250101_v000.cdf"]
        mock_hi.return_value.do_processing.side_effect = ValueError("L2 processing failed")

        hi_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI)
        with self.assertRaises(ValueError) as e:
            generate_l2_map(hi_descriptor, datetime(2020, 1, 1, tzinfo=timezone.utc),
                            datetime(2020, 1, 2, tzinfo=timezone.utc))
        self.assertIn(f"Processing for {hi_descriptor.to_string()} failed", e.exception.__notes__)

    @patch("mapping_tool.generate_map.DependencyCollector.get_pointing_sets")
    @patch("mapping_tool.generate_map.DependencyCollector.collect_spice_kernels")
    @patch("mapping_tool.generate_map.Hi")
    def test_generate_l2_map_raises_exception_if_called_with_no_psets(self, mock_hi,
                                                                      mock_collect_spice_kernels,
                                                                      mock_get_pointing_sets):
        mock_collect_spice_kernels.return_value = []
        mock_get_pointing_sets.return_value = []

        start_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2020, 1, 2, tzinfo=timezone.utc)
        hi_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI)
        map_details = f'{hi_descriptor.to_string()} {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")}'
        with self.assertRaises(ValueError) as exception_context:
            logger = logging.getLogger('generate_l2_map')
            with self.assertLogs(logger, logging.ERROR) as log_context:
                generate_l2_map(hi_descriptor, start_date, end_date)
        self.assertIn(f"No pointing sets found for {map_details}", str(exception_context.exception))
        self.assertIn(f"ERROR:generate_l2_map:No pointing sets found for {map_details}", log_context.output)
