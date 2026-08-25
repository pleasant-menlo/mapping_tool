import logging
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, Mock, call, MagicMock

from imap_data_access.file_validation import Version
from imap_l3_processing.utils import FurnishMetakernelOutput
from imap_processing.ena_maps.utils.naming import MappableInstrumentShortName, MapDescriptor
from imap_l3_processing.models import InputMetadata, VersionMap
from imap_data_access import ProcessingInputCollection, ScienceInput, SPICEInput, AncillaryInput
from imap_processing.spice.geometry import SpiceFrame

from mapping_tool.configuration import DataLevel
from mapping_tool.dependency_collector import DependencyCollector
from mapping_tool.generate_map import get_dependencies_for_l3_map, get_data_level_for_descriptor, generate_l3_map, \
    generate_l2_map, generate_map
from test.test_builders import create_map_descriptor

MODULE = "mapping_tool.generate_map"


class TestGenerateMap(unittest.TestCase):
    def setUp(self):
        download_patch = patch(f"{MODULE}.imap_data_access.download")
        self.mock_download = download_patch.start()
        self.addCleanup(download_patch.stop)

    def test_get_dependencies_for_l3_map_returns_correct_dependencies(self):
        # @formatter:off
        ultra_sp_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.ULTRA, spin_phase='full', survival_corrected='sp')
        ultra_nsp_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.ULTRA, spin_phase='full', survival_corrected='nsp')

        ultra_combined_nsp_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.ULTRA, sensor='combined', spin_phase='full', survival_corrected='nsp')
        ultra_45_nsp_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.ULTRA, sensor='45', spin_phase='full', survival_corrected='nsp')
        ultra_90_nsp_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.ULTRA, sensor='90', spin_phase='full', survival_corrected='nsp')

        ultra_combined_sp_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.ULTRA, sensor='combined', spin_phase='full', survival_corrected='sp')

        ultra_spectral_index_sp_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.ULTRA, spin_phase='full', survival_corrected='sp', principal_data="spx")
        ultra_spectral_index_nsp_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.ULTRA, spin_phase='full', survival_corrected='nsp', principal_data="spx")

        lo_sp_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.LO, spin_phase='ram', survival_corrected='sp', sensor='')
        lo_nsp_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.LO, spin_phase='ram', survival_corrected='nsp', sensor='')
        lo_sp_spx_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.LO, spin_phase='ram', survival_corrected='sp', sensor='', principal_data="spx")
        lo_nsp_spx_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.LO, spin_phase='ram', survival_corrected='nsp', sensor='', principal_data="spx")

        hi_spectral_index_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI, principal_data="spx")
        hi_ena_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI, principal_data="ena")

        hi_sp_ram_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI, survival_corrected="sp", spin_phase="ram")
        hi_nsp_ram_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI, survival_corrected="nsp", spin_phase="ram")

        hi_sp_anti_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI, survival_corrected="sp", spin_phase="anti")
        hi_nsp_anti_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI, survival_corrected="nsp", spin_phase="anti")

        hi_sp_full_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI, survival_corrected="sp", spin_phase="full")

        hi_combined_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI, sensor="combined", survival_corrected='sp')
        hi_sensor90_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI, sensor="90", survival_corrected='sp')
        hi_sensor45_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI, sensor="45", survival_corrected='sp')
        # @formatter:on

        cases = [
            (ultra_sp_descriptor, [ultra_nsp_descriptor]),
            (ultra_combined_nsp_descriptor, [ultra_45_nsp_descriptor, ultra_90_nsp_descriptor]),
            (ultra_combined_sp_descriptor, [ultra_45_nsp_descriptor, ultra_90_nsp_descriptor]),
            (ultra_spectral_index_sp_descriptor, [ultra_sp_descriptor]),
            (ultra_spectral_index_nsp_descriptor, [ultra_nsp_descriptor]),
            (lo_sp_descriptor, [lo_nsp_descriptor]),
            (lo_sp_spx_descriptor, [lo_sp_descriptor]),
            (lo_nsp_spx_descriptor, [lo_nsp_descriptor]),
            (hi_spectral_index_descriptor, [hi_ena_descriptor]),
            (hi_sp_ram_descriptor, [hi_nsp_ram_descriptor]),
            (hi_sp_anti_descriptor, [hi_nsp_anti_descriptor]),
            (hi_sp_full_descriptor, [hi_nsp_ram_descriptor, hi_nsp_anti_descriptor]),
            (hi_combined_descriptor, [hi_sensor90_descriptor, hi_sensor45_descriptor])
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

    @patch(f'{MODULE}.DependencyCollector')
    @patch(f'{MODULE}.generate_l3_map')
    @patch(f'{MODULE}.generate_l2_map')
    def test_generate_map(self, mock_generate_l2, mock_generate_l3, mock_dependency_collector_class):
        map_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI, principal_data="spx",
                                               spin_phase="full")

        time_ranges = [
            (datetime(2020, 1, 1), datetime(2020, 7, 1)),
            (datetime(2021, 1, 1), datetime(2021, 7, 1)),
        ]

        l2_ram_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI, survival_corrected='nsp',
                                                  spin_phase="ram")
        l2_antiram_map_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI,
                                                          survival_corrected='nsp',
                                                          spin_phase="anti")
        l3_ena_map_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI, spin_phase="full")

        l2_ram_dependency_collector = Mock(
            descriptor=l2_ram_descriptor,
            time_ranges=time_ranges,
            include_predicted_ephemeris=True,
        )
        l2_antiram_dependency_collector = Mock(
            descriptor=l2_antiram_map_descriptor,
            time_ranges=time_ranges,
            include_predicted_ephemeris=True,
        )
        l3_ena_dependency_collector = Mock(
            descriptor=l3_ena_map_descriptor,
            time_ranges=time_ranges,
            include_predicted_ephemeris=True,
        )

        mock_dependency_collector_class.side_effect = [
            l3_ena_dependency_collector,
            l2_ram_dependency_collector,
            l2_antiram_dependency_collector,
        ]

        l2_ram_map = Path("ram")
        l2_antiram_map = Path("anti")
        l3_full_map = Path("full")
        l3_spx_map = Path("spx")
        mock_generate_l2.side_effect = [l2_ram_map, l2_antiram_map]
        mock_generate_l3.side_effect = [l3_full_map, l3_spx_map]

        spx_dependency_collector = DependencyCollector(map_descriptor, time_ranges, True)
        output_map = generate_map(spx_dependency_collector)

        mock_dependency_collector_class.assert_has_calls([
            call(create_map_descriptor(instrument=MappableInstrumentShortName.HI, spin_phase="full"),
                 time_ranges, True),
            call(create_map_descriptor(instrument=MappableInstrumentShortName.HI, survival_corrected='nsp',
                                       spin_phase="ram"), time_ranges, True),
            call(create_map_descriptor(instrument=MappableInstrumentShortName.HI, survival_corrected='nsp',
                                       spin_phase="anti"), time_ranges, True),
        ])

        mock_generate_l2.assert_has_calls([
            call(l2_ram_dependency_collector), call(l2_antiram_dependency_collector)
        ])

        mock_generate_l3.assert_has_calls([
            call(l3_ena_dependency_collector, [l2_ram_map, l2_antiram_map]),
            call(spx_dependency_collector, [l3_full_map])
        ])

        self.assertEqual(l3_spx_map, output_map)

    def test_generate_l3_map_raises_exception_when_called_with_non_l2_or_l3_map(self):
        map_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.GLOWS, principal_data="spx",
                                               spin_phase="full")
        start_date = datetime(2020, 1, 1)
        end_date = datetime(2020, 7, 1)

        dependency_collector = DependencyCollector(map_descriptor, [(start_date, end_date)], False)

        with self.assertRaises(ValueError) as context:
            generate_map(dependency_collector)

        self.assertIn(f"Cannot produce map for instrument: {map_descriptor.instrument_descriptor}",
                      str(context.exception))

    @patch(f'{MODULE}.spiceypy.furnsh')
    @patch(f"{MODULE}.HiProcessor")
    @patch(f"{MODULE}.LoProcessor")
    @patch(f"{MODULE}.UltraProcessor")
    def test_generate_l3_map(self, mock_ultra, mock_lo, mock_hi, mock_furnsh):
        hi_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI,
                                              kernel_path=Path('custom/kernel/path'))
        lo_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.LO,
                                              kernel_path=Path('custom/kernel/path'))
        ultra_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.ULTRA,
                                                 kernel_path=Path('custom/kernel/path'))

        spx_descriptor = create_map_descriptor(principal_data="spx",
                                               kernel_path=Path('custom/kernel/path'))
        spx_esa_specified_descriptor = create_map_descriptor(principal_data="spx",
                                                             spectral_index_energy_step_range="0207",
                                                             kernel_path=Path('custom/kernel/path'))

        cases = [
            (hi_descriptor, mock_hi, hi_descriptor.to_l3_input_string()),
            (lo_descriptor, mock_lo, lo_descriptor.to_l3_input_string()),
            (ultra_descriptor, mock_ultra, ultra_descriptor.to_l3_input_string()),
            (spx_descriptor, mock_hi, spx_descriptor.to_l3_input_string()),
            (spx_esa_specified_descriptor, mock_hi, spx_esa_specified_descriptor.to_l3_input_string()),
        ]

        start_date = datetime(2020, 1, 1)
        end_date = datetime(2020, 1, 2)

        for descriptor, mock_processor, expected_descriptor_string in cases:
            mock_furnsh.reset_mock()
            with self.subTest(descriptor.to_string()):
                mock_dependency_collector = Mock(descriptor=descriptor, start_date=start_date, end_date=end_date)

                mock_dependency_collector.furnish_spice_kernels.return_value = Mock(spec=FurnishMetakernelOutput)
                mock_dependency_collector.get_survival_probability_dependencies.return_value = [
                    ScienceInput('imap_glows_l3e_science_20250101_v000.cdf'),
                    ScienceInput('imap_hi_l1c_pset_20250101_v000.cdf')
                ]
                mock_dependency_collector.get_ancillary_dependencies.return_value = [
                    AncillaryInput('imap_hi_ancillary_20250101_v000.dat')
                ]

                expected_path = Path('returned_path')
                mock_processor.return_value.process.return_value = [expected_path]

                input_maps = [Path("imap_hi_l2_h90-ena-h-sf-nsp-ram-hae-4deg-6mo_20250101_v000.cdf"),
                              Path("imap_hi_l2_h90-ena-h-sf-nsp-ram-hae-4deg-6mo_20250102_v001.cdf")]

                actual_path = generate_l3_map(mock_dependency_collector, input_maps)
                self.assertEqual(expected_path, actual_path)
                expected_inputs = [
                    "imap_hi_l2_h90-ena-h-sf-nsp-ram-hae-4deg-6mo_20250101_v000.cdf",
                    "imap_hi_l2_h90-ena-h-sf-nsp-ram-hae-4deg-6mo_20250102_v001.cdf",
                    "imap_glows_l3e_science_20250101_v000.cdf",
                    "imap_hi_l1c_pset_20250101_v000.cdf",
                    "imap_hi_ancillary_20250101_v000.dat",
                ]

                expected_input_metadata = InputMetadata(
                    instrument=descriptor.instrument.name.lower(),
                    data_level='l3',
                    start_date=start_date,
                    end_date=end_date,
                    version=VersionMap({expected_descriptor_string:Version(0,0)}),
                    descriptor=expected_descriptor_string,
                )

                actual_processing_input_collection, actual_input_metadata = mock_processor.call_args.args
                actual_input_filename_lists = [processing_input.filename_list[0] for processing_input in
                                               actual_processing_input_collection.processing_input]
                self.assertEqual(expected_inputs, actual_input_filename_lists)
                self.assertEqual(expected_input_metadata, actual_input_metadata)

                mock_processor.return_value.process.assert_called_once_with(descriptor.spice_frame)
                mock_dependency_collector.furnish_spice_kernels.assert_called_once()
                mock_dependency_collector.get_survival_probability_dependencies.assert_called_once_with(input_maps)
                mock_dependency_collector.get_ancillary_dependencies.assert_called_once()

                mock_furnsh.assert_called_once_with(os.path.join('custom', 'kernel', 'path'))

                mock_processor.return_value.process.assert_called_once()
                mock_processor.reset_mock()
                mock_furnsh.reset_mock()

    @patch(f"{MODULE}.spiceypy.furnsh")
    @patch(f"{MODULE}.HiProcessor")
    def test_generate_l3_map_does_not_furnsh_when_no_custom_kernel(self, mock_hi, mock_furnsh):
        mock_dependency_collector = Mock(
            descriptor=create_map_descriptor(kernel_path=None),
            start_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2020, 1, 2, tzinfo=timezone.utc)
        )
        mock_dependency_collector.furnish_spice_kernels.return_value = Mock(spec=FurnishMetakernelOutput)
        mock_dependency_collector.get_survival_probability_dependencies.return_value = []
        mock_dependency_collector.get_ancillary_dependencies.return_value = []
        mock_hi.return_value.process.return_value = [Path('result')]

        generate_l3_map(mock_dependency_collector, [])

        mock_furnsh.assert_not_called()

    @patch(f"{MODULE}.HiProcessor")
    def test_generate_l3_map_raises_error_when_less_or_more_than_one_file_is_returned(self, mock_hi):
        mock_dependency_collector = Mock(
            descriptor=create_map_descriptor(),
            start_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2020, 1, 2, tzinfo=timezone.utc)
        )
        mock_dependency_collector.furnish_spice_kernels.return_value = Mock(spec=FurnishMetakernelOutput)
        mock_dependency_collector.get_survival_probability_dependencies.return_value = []
        mock_dependency_collector.get_ancillary_dependencies.return_value = []

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
                        generate_l3_map(mock_dependency_collector, [])

                self.assertIn(err_string, str(e.exception))

    @patch(f"{MODULE}.HiProcessor.process")
    def test_generate_l3_map_gracefully_handles_processing_exceptions(self, mock_process):
        mock_dependency_collector = Mock(
            descriptor=create_map_descriptor(),
            start_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2020, 1, 2, tzinfo=timezone.utc)
        )
        mock_dependency_collector.furnish_spice_kernels.return_value = Mock(spec=FurnishMetakernelOutput)
        mock_dependency_collector.get_survival_probability_dependencies.return_value = []
        mock_dependency_collector.get_ancillary_dependencies.return_value = []
        mock_process.side_effect = ValueError("L3 processing failed")

        hi_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI)
        with self.assertRaises(ValueError) as e:
            logger = logging.getLogger('generate_l2_map')
            with self.assertLogs(logger, logging.ERROR) as log_context:
                generate_l3_map(mock_dependency_collector, [])
        self.assertIn(f"Processing for {hi_descriptor.to_l3_input_string()} failed",
                      str(e.exception.__notes__))

    @patch(f"{MODULE}.HiProcessor.process")
    def test_generate_l3_map_patches_l3_processing_get_map_coord_frame(self, mock_process):
        descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI, spice_frame=SpiceFrame.IMAP_RTN)
        start_date = datetime(2020, 1, 1)
        end_date = datetime(2020, 1, 2)

        mock_dependency_collector = Mock(descriptor=descriptor, start_date=start_date, end_date=end_date)

        mock_dependency_collector.get_spice_kernel_names.return_value = ["imap_science_0001.tf", "imap_sclk_0000.tsc"]
        mock_dependency_collector.get_ancillary_dependencies.return_value = []
        mock_dependency_collector.get_survival_probability_dependencies.return_value = []
        mock_dependency_collector.get_pointing_sets.return_value = ["imap_hi_l1c_pset-1_20250101_v000.cdf",
                                                                    "imap_hi_l1c_pset-2_20250101_v000.cdf"]

        def mock_do_processing(deps):
            self.assertEqual(SpiceFrame.IMAP_RTN,
                             MapDescriptor.from_string(descriptor.to_string()).map_spice_coord_frame)
            return ["One whole processed file"]

        # mock_process.return_value = [Path("some_path")]
        mock_process.side_effect = mock_do_processing

        _ = generate_l3_map(mock_dependency_collector, [])

        normal_pipeline_descriptor = "h90-ena-h-sf-nsp-ram-hae-2deg-6mo"
        self.assertEqual(SpiceFrame.IMAP_HAE,
                         MapDescriptor.from_string(normal_pipeline_descriptor).map_spice_coord_frame)

    @patch(f"{MODULE}.spiceypy")
    @patch(f"{MODULE}.Hi")
    @patch(f"{MODULE}.Lo")
    @patch(f"{MODULE}.Ultra")
    def test_generate_l2_map(self, mock_ultra, mock_lo, mock_hi, mock_spiceypy):
        mock_dependency_collector = Mock()

        mock_dependency_collector.get_ancillary_dependencies.return_value = [
            AncillaryInput("imap_hi_45sensor-cal-prod_20240101_v002.csv"),
            AncillaryInput("imap_hi_45sensor-esa-energies_20240101_v002.csv")
        ]
        mock_dependency_collector.get_spice_kernel_names.return_value = ["imap_science_0001.tf", "imap_sclk_0000.tsc"]
        mock_dependency_collector.get_pointing_sets.return_value = [
            "imap_hi_l1c_pset-1_20250101_v000.cdf",
            "imap_hi_l1c_pset-2_20250101_v000.cdf"
        ]

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
                mock_dependency_collector.reset_mock()
                mock_dependency_collector.descriptor = descriptor
                mock_dependency_collector.start_date = start_date
                mock_dependency_collector.end_date = end_date

                expected_map = Mock()
                mock_processor = mock_processor_class.return_value
                mock_processor.post_processing.return_value = [expected_map]

                actual_map = generate_l2_map(mock_dependency_collector)

                mock_dependency_collector.get_ancillary_dependencies.assert_called_once()
                mock_dependency_collector.get_spice_kernel_names.assert_called_once()
                mock_dependency_collector.get_pointing_sets.assert_called_once()

                self.mock_download.assert_has_calls([
                    call("imap_hi_l1c_pset-1_20250101_v000.cdf"),
                    call("imap_hi_l1c_pset-2_20250101_v000.cdf"),
                ])

                expected_dependency_str = ProcessingInputCollection(
                    ScienceInput("imap_hi_l1c_pset-1_20250101_v000.cdf"),
                    ScienceInput("imap_hi_l1c_pset-2_20250101_v000.cdf"),
                    SPICEInput("imap_science_0001.tf"), SPICEInput("imap_sclk_0000.tsc"),
                    AncillaryInput("imap_hi_45sensor-cal-prod_20240101_v002.csv"),
                    AncillaryInput("imap_hi_45sensor-esa-energies_20240101_v002.csv"),
                ).serialize()

                mock_processor_class.assert_called_once_with(
                    data_level="l2", data_descriptor=descriptor.to_string(),
                    dependency_str=expected_dependency_str,
                    start_date=start_date.strftime("%Y%m%d"),
                    repointing=None,
                    version="v000.0000",
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

    @patch(f"{MODULE}.Hi")
    def test_generate_l2_map_patches_l2_processing_get_map_coord_frame(self, mock_hi_processor_class):
        descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI, spice_frame=SpiceFrame.IMAP_RTN)
        start_date = datetime(2020, 1, 1)
        end_date = datetime(2020, 1, 2)

        mock_dependency_collector = Mock(descriptor=descriptor, start_date=start_date, end_date=end_date)

        mock_hi_processor = mock_hi_processor_class.return_value
        mock_dependency_collector.get_spice_kernel_names.return_value = ["imap_science_0001.tf", "imap_sclk_0000.tsc"]
        mock_dependency_collector.get_ancillary_dependencies.return_value = []
        mock_dependency_collector.get_pointing_sets.return_value = ["imap_hi_l1c_pset-1_20250101_v000.cdf",
                                                                    "imap_hi_l1c_pset-2_20250101_v000.cdf"]

        def mock_do_processing(deps):
            self.assertEqual(deps, mock_hi_processor.pre_processing.return_value)
            self.assertEqual(SpiceFrame.IMAP_RTN,
                             MapDescriptor.from_string(descriptor.to_string()).map_spice_coord_frame)

        mock_hi_processor.post_processing.return_value = [Path("some_path")]
        mock_hi_processor.do_processing.side_effect = mock_do_processing

        _ = generate_l2_map(mock_dependency_collector)

        normal_pipeline_descriptor = "h90-ena-h-sf-nsp-ram-hae-2deg-6mo"
        self.assertEqual(SpiceFrame.IMAP_HAE,
                         MapDescriptor.from_string(normal_pipeline_descriptor).map_spice_coord_frame)

    @patch(f"{MODULE}.Hi")
    def test_generate_l2_map_raises_error_when_less_or_more_than_one_file_is_returned(self, mock_hi):
        mock_dependency_collector = MagicMock(spec=DependencyCollector, descriptor=create_map_descriptor(),
                                              start_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
                                              end_date=datetime(2020, 1, 2, tzinfo=timezone.utc))

        mock_dependency_collector.get_pointing_sets.return_value = ["imap_hi_l1c_pset_20250101_v000.cdf"]

        error_cases = [
            ("L2 processing did not return any files!", []),
            ("L2 processing returned too many files!", [Path(""), Path("")])
        ]

        for err_string, returned_paths in error_cases:
            with self.subTest(err_string):
                mock_hi.return_value.post_processing.return_value = returned_paths
                with self.assertRaises(ValueError) as e:
                    generate_l2_map(mock_dependency_collector)

                self.assertIn(err_string, str(e.exception))

    @patch(f"{MODULE}.DependencyCollector.get_pointing_sets")
    @patch(f"{MODULE}.DependencyCollector.get_spice_kernel_names")
    @patch(f"{MODULE}.DependencyCollector.get_ancillary_dependencies")
    @patch(f"{MODULE}.Hi")
    def test_generate_l2_map_gracefully_handles_processing_exceptions(self, mock_hi, mock_ancillary_dependencies,
                                                                      mock_get_spice_kernel_names,
                                                                      mock_get_pointing_sets):
        mock_get_spice_kernel_names.return_value = []
        mock_ancillary_dependencies.return_value = []
        mock_get_pointing_sets.return_value = ["imap_hi_l1c_pset_20250101_v000.cdf"]
        mock_hi.return_value.do_processing.side_effect = ValueError("L2 processing failed")

        hi_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI)
        dependency_collector = DependencyCollector(
            hi_descriptor,
            [
                (datetime(2020, 1, 1, tzinfo=timezone.utc),
                datetime(2020, 1, 2, tzinfo=timezone.utc))
            ],
            False,
        )
        with self.assertRaises(ValueError) as e:
            generate_l2_map(dependency_collector)
        self.assertIn(f"Processing for {hi_descriptor.to_string()} failed", e.exception.__notes__)

    @patch(f"{MODULE}.Hi")
    def test_generate_l2_map_raises_exception_if_called_with_no_psets(self, mock_hi):
        start_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2020, 1, 2, tzinfo=timezone.utc)
        hi_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI)
        map_details = f'{hi_descriptor.to_string()} {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")}'

        mock_dependency_collector = Mock(descriptor=hi_descriptor, start_date=start_date, end_date=end_date)
        mock_dependency_collector.get_pointing_sets.return_value = []

        with self.assertRaises(ValueError) as exception_context:
            generate_l2_map(mock_dependency_collector)
        self.assertIn(f"No pointing sets found for {map_details}", str(exception_context.exception))
