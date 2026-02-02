import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, call, Mock

import imap_data_access
from imap_processing.ena_maps.utils.naming import MapDescriptor, MappableInstrumentShortName
from imap_data_access.processing_input import AncillaryInput, ScienceInput

from mapping_tool.dependency_collector import DependencyCollector
from test import test_helpers
from test.test_builders import create_map_descriptor
from spacepy.pycdf import CDF


class TestDependencyCollector(unittest.TestCase):
    @patch('mapping_tool.dependency_collector.imap_data_access.query')
    def test_get_pointing_sets(self, mock_query):
        expected_pointing_sets = ["pset_1", "pset_2", "pset_3"]
        mock_query.return_value = [{"file_path": f"path/to/{file_name}", "start_date": file_name, "version": "v000"} for
                                   file_name in
                                   expected_pointing_sets]

        start_date = datetime(2025, 1, 1)
        end_date = datetime(2025, 2, 1)
        cases = [
            ("sf", MappableInstrumentShortName.HI, "90", "90sensor-pset"),
            ("sf", MappableInstrumentShortName.HI, "45", "45sensor-pset"),
            ("sf", MappableInstrumentShortName.LO, "90", "pset"),
            ("sf", MappableInstrumentShortName.ULTRA, "90", "90sensor-spacecraftpset"),
            ("sf", MappableInstrumentShortName.ULTRA, "45", "45sensor-spacecraftpset"),
            ("hf", MappableInstrumentShortName.ULTRA, "90", "90sensor-heliopset"),
            ("hf", MappableInstrumentShortName.ULTRA, "45", "45sensor-heliopset"),
        ]

        for frame_descriptor, instrument, sensor, expected_descriptor in cases:
            with self.subTest(f"{frame_descriptor} {instrument} {sensor}"):
                mock_query.reset_mock()
                descriptor = create_map_descriptor(
                    frame_descriptor=frame_descriptor,
                    resolution_str="2deg",
                    duration="2",
                    instrument=instrument,
                    sensor=sensor,
                    principal_data="ena",
                    species='h',
                    survival_corrected="nsp",
                    spin_phase="ram",
                    coordinate_system="hae"
                )

                dependency_collector = DependencyCollector(descriptor, start_date, end_date)
                pointing_sets = dependency_collector.get_pointing_sets()

                mock_query.assert_called_once_with(
                    instrument=instrument.name.lower(),
                    start_date=start_date.strftime("%Y%m%d"),
                    end_date=end_date.strftime("%Y%m%d"),
                    data_level="l1c",
                    descriptor=expected_descriptor
                )
                self.assertEqual(expected_pointing_sets, pointing_sets)

    @patch('mapping_tool.dependency_collector.imap_data_access.query')
    def test_get_pointing_sets_for_ultra_combined(self, mock_query):
        expected_pointing_sets = ["u45-pset1", "u45-pset2", "u90-pset1", "u90-pset2"]
        mock_query.side_effect = [
            [{"file_path": "u45-pset1", "start_date": "u45-pset1", "version": "v000"},
             {"file_path": "u45-pset2", "start_date": "u45-pset2", "version": "v000"}],
            [{"file_path": "u90-pset1", "start_date": "u90-pset1", "version": "v000"},
             {"file_path": "u90-pset2", "start_date": "u90-pset2", "version": "v000"}]
        ]

        descriptor = create_map_descriptor(
            frame_descriptor="sf",
            resolution_str="nside2",
            duration="2",
            instrument=MappableInstrumentShortName.ULTRA,
            sensor="combined",
            principal_data="ena",
            species='h',
            survival_corrected="sp",
            spin_phase="ram",
            coordinate_system="hae"
        )
        dependency_collector = DependencyCollector(descriptor, datetime(2025, 1, 1), datetime(2025, 2, 1))
        pointing_sets = dependency_collector.get_pointing_sets()

        mock_query.assert_has_calls([
            call(instrument="ultra", data_level="l1c", descriptor="45sensor-spacecraftpset", start_date="20250101",
                 end_date="20250201"),
            call(instrument="ultra", data_level="l1c", descriptor="90sensor-spacecraftpset", start_date="20250101",
                 end_date="20250201")
        ])

        self.assertEqual(expected_pointing_sets, pointing_sets)

    @patch('mapping_tool.dependency_collector.imap_data_access.query')
    def test_get_pointing_sets_for_hi_combined(self, mock_query):
        expected_pointing_sets = [
            "h45-pset1", "h45-pset2",
            "h90-pset1", "h90-pset2",
        ]

        mock_query.side_effect = [
            [{"file_path": "h45-pset1", "start_date": "h45-pset1", "version": "v000"},
             {"file_path": "h45-pset2", "start_date": "h45-pset2", "version": "v000"}],
            [{"file_path": "h90-pset1", "start_date": "h90-pset1", "version": "v000"},
             {"file_path": "h90-pset2", "start_date": "h90-pset2", "version": "v000"}]
        ]

        descriptor = create_map_descriptor(
            frame_descriptor="sf",
            resolution_str="nside2",
            duration="2",
            instrument=MappableInstrumentShortName.HI,
            sensor="combined",
            principal_data="ena",
            species='h',
            survival_corrected="sp",
            spin_phase="ram",
            coordinate_system="hae"
        )

        dependency_collector = DependencyCollector(descriptor, datetime(2025, 1, 1), datetime(2025, 2, 1))
        pointing_sets = dependency_collector.get_pointing_sets()

        mock_query.assert_has_calls([
            call(instrument="hi", data_level="l1c", descriptor="45sensor-pset", start_date="20250101",
                 end_date="20250201"),
            call(instrument="hi", data_level="l1c", descriptor="90sensor-pset", start_date="20250101",
                 end_date="20250201")
        ])

        self.assertEqual(expected_pointing_sets, pointing_sets)

    @patch('mapping_tool.dependency_collector.imap_data_access.query')
    def test_get_pointing_sets_for_lo_survival_corrected(self, mock_query):
        expected_pointing_sets = [
            "l90-pset1", "l90-pset2",
        ]

        mock_query.side_effect = [
            [{"file_path": "l90-pset1", "start_date": "l90-pset1", "version": "v000"},
             {"file_path": "l90-pset2", "start_date": "l90-pset2", "version": "v000"}],
        ]

        descriptor = create_map_descriptor(
            frame_descriptor="sf",
            resolution_str="nside2",
            duration="2",
            instrument=MappableInstrumentShortName.LO,
            sensor="90",
            principal_data="ena",
            species='h',
            survival_corrected="sp",
            spin_phase="ram",
            coordinate_system="hae"
        )
        dependency_collector = DependencyCollector(descriptor, datetime(2025, 1, 1), datetime(2025, 2, 1))
        pointing_sets = dependency_collector.get_pointing_sets()

        mock_query.assert_has_calls([
            call(instrument="lo", data_level="l1c", descriptor="pset", start_date="20250101",
                 end_date="20250201")
        ])

        self.assertEqual(expected_pointing_sets, pointing_sets)

    @patch('mapping_tool.dependency_collector.imap_data_access.query')
    def test_get_files_returns_latest_file_versions(self, mock_query):
        mock_query.side_effect = [
            [{"file_path": "imap_hi_l1c_45sensor-pset_20260101_v001.cdf", "version": "v001", "start_date": "20260101"},
             {"file_path": "imap_hi_l1c_45sensor-pset_20260101_v002.cdf", "version": "v002", "start_date": "20260101"},
             {"file_path": "imap_hi_l1c_45sensor-pset_20260102_v001.cdf", "version": "v001", "start_date": "20260102"}]
        ]
        descriptor = create_map_descriptor(
            frame_descriptor="sf",
            resolution_str="nside2",
            duration="2",
            instrument=MappableInstrumentShortName.LO,
            sensor="90",
            principal_data="ena",
            species='h',
            survival_corrected="sp",
            spin_phase="ram",
            coordinate_system="hae"
        )
        start_date = datetime(2026, 1, 1)
        end_date = datetime(2026, 2, 1)

        dependency_collector = DependencyCollector(descriptor, start_date, end_date)
        psets = dependency_collector.get_pointing_sets()

        expected_psets = ["imap_hi_l1c_45sensor-pset_20260101_v002.cdf", "imap_hi_l1c_45sensor-pset_20260102_v001.cdf"]
        self.assertEqual(expected_psets, psets)

    @patch('mapping_tool.dependency_collector.imap_data_access.query')
    def test_get_latest_version_of_ancillary_dependencies(self, mock_query):
        sensors = ["90", "45"]

        for sensor in sensors:
            with self.subTest(sensor):
                mock_query.side_effect = [
                    [
                        create_imap_query_response_item(descriptor="45sensor-cal-prod", version="v002"),
                        create_imap_query_response_item(descriptor="45sensor-cal-prod", version="v001"),
                        create_imap_query_response_item(descriptor="45sensor-esa-energies", version="v002"),
                        create_imap_query_response_item(descriptor="45sensor-esa-energies", version="v001"),
                        create_imap_query_response_item(descriptor="45sensor-esa-eta-fit-factors", version="v002"),
                        create_imap_query_response_item(descriptor="45sensor-esa-eta-fit-factors", version="v001"),
                        create_imap_query_response_item(descriptor="90sensor-cal-prod", version="v001"),
                        create_imap_query_response_item(descriptor="90sensor-cal-prod", version="v002"),
                        create_imap_query_response_item(descriptor="90sensor-esa-energies", version="v001"),
                        create_imap_query_response_item(descriptor="90sensor-esa-energies", version="v002"),
                        create_imap_query_response_item(descriptor="90sensor-esa-eta-fit-factors", version="v001"),
                        create_imap_query_response_item(descriptor="90sensor-esa-eta-fit-factors", version="v002"),
                    ]
                ]

                end_date = datetime(2026, 2, 1, tzinfo=timezone.utc)
                descriptor = create_map_descriptor(
                    frame_descriptor="sf",
                    resolution_str="6",
                    duration="2",
                    instrument=MappableInstrumentShortName.HI,
                    sensor=sensor,
                    principal_data="ena",
                    species='h',
                    survival_corrected="nsp",
                    spin_phase="ram",
                    coordinate_system="hae"
                )

                dependency_collector = DependencyCollector(descriptor, Mock(), end_date)
                ancillary_dependencies = dependency_collector.get_ancillary_dependencies()

                mock_query.assert_called_with(table="ancillary", instrument="hi")
                expected_ancillary_dependencies = [AncillaryInput(f"imap_hi_{sensor}sensor-cal-prod_20240101_v002.csv"),
                                                   AncillaryInput(
                                                       f"imap_hi_{sensor}sensor-esa-energies_20240101_v002.csv"),
                                                   AncillaryInput(
                                                       f"imap_hi_{sensor}sensor-esa-eta-fit-factors_20240101_v002.csv")]

                test_helpers.assert_imap_processing_inputs_match(expected_ancillary_dependencies,
                                                                 ancillary_dependencies)

    @patch('mapping_tool.dependency_collector.imap_data_access.query')
    def test_get_ancillary_dependencies_finds_nearest_files_to_map_end_date(self, mock_query):
        mock_query.side_effect = [
            [
                create_imap_query_response_item(descriptor="45sensor-cal-prod", version="v001", start_date="20270101"),
                create_imap_query_response_item(descriptor="45sensor-cal-prod", version="v001", start_date="20250101"),
                create_imap_query_response_item(descriptor="45sensor-cal-prod", version="v002", start_date="20250101"),
                create_imap_query_response_item(descriptor="45sensor-cal-prod", version="v001", start_date="20240101"),
            ]
        ]

        end_date = datetime(2026, 2, 1, tzinfo=timezone.utc)
        descriptor = create_map_descriptor(
            frame_descriptor="sf",
            resolution_str="6",
            duration="2",
            instrument=MappableInstrumentShortName.HI,
            sensor="45",
            principal_data="ena",
            species='h',
            survival_corrected="nsp",
            spin_phase="ram",
            coordinate_system="hae"
        )

        dependency_collector = DependencyCollector(descriptor, start_date=Mock(), end_date=end_date)
        ancillary_dependencies = dependency_collector.get_ancillary_dependencies()

        mock_query.assert_called_with(table="ancillary", instrument="hi")
        expected_ancillary_dependencies = [AncillaryInput("imap_hi_45sensor-cal-prod_20250101_v002.csv")]
        test_helpers.assert_imap_processing_inputs_match(expected_ancillary_dependencies, ancillary_dependencies)

    @patch('mapping_tool.dependency_collector.imap_data_access.query')
    def test_get_ancillary_dependencies_correctly_filters_ancillary_inputs(self, mock_query):
        cases = [
            (create_map_descriptor(instrument=MappableInstrumentShortName.HI, sensor="90", survival_corrected="nsp"),
             ["90sensor-cal-prod", "90sensor-esa-energies", "90sensor-esa-eta-fit-factors"]),
            (create_map_descriptor(instrument=MappableInstrumentShortName.HI, sensor="45", survival_corrected="nsp"),
             ["45sensor-cal-prod", "45sensor-esa-energies", "45sensor-esa-eta-fit-factors"]),
            (create_map_descriptor(instrument=MappableInstrumentShortName.LO, survival_corrected="nsp"),
             ["esa-eta-fit-factors"]),
            (create_map_descriptor(instrument=MappableInstrumentShortName.ULTRA, principal_data="spx",
                                   sensor="combined"), ["ulc-spx-energy-ranges"]),
            (create_map_descriptor(instrument=MappableInstrumentShortName.ULTRA, principal_data="spx", sensor="45"),
             ["ulc-spx-energy-ranges"]),
            (create_map_descriptor(instrument=MappableInstrumentShortName.ULTRA, principal_data="ena"),
             ["l2-energy-bin-group-sizes"]),
            (create_map_descriptor(instrument=MappableInstrumentShortName.LO, survival_corrected="sp"), [])
        ]

        mock_query.return_value = [
            create_imap_query_response_item(instrument="ultra", descriptor="l2-energy-bin-group-sizes",
                                            version="v001",
                                            start_date="20250101"),
            create_imap_query_response_item(instrument="ultra", descriptor="ulc-spx-energy-ranges",
                                            version="v001",
                                            start_date="20250101"),
            create_imap_query_response_item(instrument="hi", descriptor="90sensor-cal-prod",
                                            version="v001",
                                            start_date="20250101"),
            create_imap_query_response_item(instrument="hi", descriptor="90sensor-esa-energies",
                                            version="v001",
                                            start_date="20250101"),
            create_imap_query_response_item(instrument="hi", descriptor="90sensor-esa-eta-fit-factors",
                                            version="v001",
                                            start_date="20250101"),
            create_imap_query_response_item(instrument="hi", descriptor="45sensor-cal-prod",
                                            version="v001",
                                            start_date="20250101"),
            create_imap_query_response_item(instrument="hi", descriptor="45sensor-esa-energies",
                                            version="v001",
                                            start_date="20250101"),
            create_imap_query_response_item(instrument="hi", descriptor="45sensor-esa-eta-fit-factors",
                                            version="v001",
                                            start_date="20250101"),
            create_imap_query_response_item(instrument="lo", descriptor="esa-eta-fit-factors",
                                            version="v001",
                                            start_date="20250101"),
            create_imap_query_response_item(instrument="ultra", descriptor="90sensor-sc-pointing-phi")
        ]

        for descriptor, expected_ancillary_descriptors in cases:
            mock_query.reset_mock()
            with self.subTest(descriptor=descriptor.to_string()):
                end_date = datetime(2026, 2, 1, tzinfo=timezone.utc)

                dependency_collector = DependencyCollector(descriptor, Mock(), end_date)
                ancillary_dependencies = dependency_collector.get_ancillary_dependencies()

                mock_query.assert_called_with(table="ancillary", instrument=descriptor.instrument.name.lower())
                self.assertEqual(set(expected_ancillary_descriptors), {d.descriptor for d in ancillary_dependencies})

    @patch('mapping_tool.dependency_collector.imap_data_access.query')
    def test_get_ancillary_dependencies_writes_energy_bin_edges_to_imap_dir(self, mock_query):
        mock_query.side_effect = [
            [
                create_imap_query_response_item(instrument="ultra", descriptor="l2-energy-bin-group-sizes",
                                                start_date="19990101"),
                create_imap_query_response_item(instrument="ultra", descriptor="ancillary-2", version="v001",
                                                start_date="20260101")
            ]
        ]

        end_date = datetime(2026, 2, 1, tzinfo=timezone.utc)
        descriptor = create_map_descriptor(
            frame_descriptor="sf",
            resolution_str="6",
            duration="2",
            instrument=MappableInstrumentShortName.ULTRA,
            sensor="45",
            principal_data="ena",
            species='h',
            survival_corrected="sp",
            spin_phase="ram",
            coordinate_system="hae"
        )

        original_imap_data_dir = imap_data_access.config["DATA_DIR"]
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                test_deletes_stuff_here = Path(tmpdir)
                imap_data_access.config["DATA_DIR"] = test_deletes_stuff_here
                ancillary_ultra_dir = test_deletes_stuff_here / "imap/ancillary/ultra"
                ultra_dep = ancillary_ultra_dir / "imap_ultra_l2-energy-bin-group-sizes_20250924_v000.csv"

                dependency_collector = DependencyCollector(descriptor, Mock(), end_date, "0, 10, 20, 40")
                ancillary_dependencies = dependency_collector.get_ancillary_dependencies()

                self.assertTrue(ultra_dep.is_file())
                self.assertEqual("0,10,20,40", ultra_dep.read_text())
                mock_query.assert_called_once_with(table="ancillary", instrument="ultra")
                expected_ancillary_dependencies = [
                    AncillaryInput("imap_ultra_l2-energy-bin-group-sizes_20250924_v000.csv")]
                test_helpers.assert_imap_processing_inputs_match(expected_ancillary_dependencies,
                                                                 ancillary_dependencies)
        finally:
            imap_data_access.config["DATA_DIR"] = original_imap_data_dir

    @patch('mapping_tool.dependency_collector.requests')
    def test_furnish_spice(self, mock_requests):
        desired_spice_start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        desired_spice_end = datetime(2025, 3, 1, tzinfo=timezone.utc)

        mock_naif_json = [
            {
                "file_name": "lsk/naif0012.tls",
                "min_date_datetime": "2024-12-01, 00:00:00",
                "max_date_datetime": "2025-05-01, 00:00:00"
            },
        ]

        mock_sclk_json = [
            {
                "file_name": "lsk/imap_sclk_0000.tsc",
                "min_date_datetime": "2024-12-01, 00:00:00",
                "max_date_datetime": "2025-05-01, 00:00:00"
            },
        ]

        mock_dps_json = [
            {
                "file_name": "ck/imap_dps_2024_270_2026_335_01.ah.bc",
                "min_date_datetime": "2024-09-01, 00:00:00",
                "max_date_datetime": "2024-12-01, 00:00:00",
            },
            {
                "file_name": "ck/imap_dps_2024_335_2025_031_01.ah.bc",
                "min_date_datetime": "2024-12-01, 00:00:00",
                "max_date_datetime": "2025-02-01, 00:00:00",
            },
            {
                "file_name": "ck/imap_dps_2025_031_2025_120_01.ah.bc",
                "min_date_datetime": "2025-02-01, 00:00:00",
                "max_date_datetime": "2025-05-01, 00:00:00",
            },
        ]

        mock_imap_frame_json = [
            {
                "file_name": "fk/imap_001.tf",
                "min_date_datetime": "2024-12-01, 00:00:00",
                "max_date_datetime": "2025-05-01, 00:00:00"
            },
        ]

        mock_science_frame_json = [
            {
                "file_name": "fk/imap_science_0001.tf",
                "min_date_datetime": "2024-12-01, 00:00:00",
                "max_date_datetime": "2025-05-01, 00:00:00"
            }
        ]

        mock_planetary_ephemeris_json = [
            {
                "file_name": "spk/de440.bsp",
                "min_date_datetime": "2024-12-01, 00:00:00",
                "max_date_datetime": "2025-05-01, 00:00:00"
            }
        ]

        mock_ephemeris_reconstructed_json = [
            {
                "file_name": "spk/imap_recon_od004_20250924_20251002_v01.bsp",
                "min_date_datetime": "2024-12-01, 00:00:00",
                "max_date_datetime": "2025-05-01, 00:00:00"
            }
        ]

        mock_planetary_constants_json = [
            {
                "file_name": "pck/pck00010.tpc",
                "min_date_datetime": "2024-12-01, 00:00:00",
                "max_date_datetime": "2025-05-01, 00:00:00"
            }
        ]

        mock_naif_response = Mock(json=Mock(return_value=mock_naif_json))
        mock_sclk_response = Mock(json=Mock(return_value=mock_sclk_json))
        mock_dps_response = Mock(json=Mock(return_value=mock_dps_json))
        mock_imap_frame_response = Mock(json=Mock(return_value=mock_imap_frame_json))
        mock_science_frame_response = Mock(json=Mock(return_value=mock_science_frame_json))
        mock_planetary_ephemeris_response = Mock(json=Mock(return_value=mock_planetary_ephemeris_json))
        mock_ephemeris_reconstructed_response = Mock(json=Mock(return_value=mock_ephemeris_reconstructed_json))
        mock_planetary_constants_response = Mock(json=Mock(return_value=mock_planetary_constants_json))

        mock_requests.get.side_effect = [
            mock_naif_response,
            mock_sclk_response,
            mock_dps_response,
            mock_imap_frame_response,
            mock_science_frame_response,
            mock_planetary_ephemeris_response,
            mock_ephemeris_reconstructed_response,
            mock_planetary_constants_response
        ]

        previous_imap_data_access_url = imap_data_access.config["DATA_ACCESS_URL"]
        previous_imap_data_access_token = imap_data_access.config["ACCESS_TOKEN"]

        imap_data_access.config["DATA_ACCESS_URL"] = "expected-url"
        imap_data_access.config["ACCESS_TOKEN"] = "expected-access-token"

        dependency_collector = DependencyCollector(create_map_descriptor(), desired_spice_start, desired_spice_end)
        spice_kernels = dependency_collector.collect_spice_kernels()

        imap_data_access.config["DATA_ACCESS_URL"] = previous_imap_data_access_url
        imap_data_access.config["ACCESS_TOKEN"] = previous_imap_data_access_token

        expected_auth_header = {"Authorization": r"Bearer expected-access-token"}
        mock_requests.get.assert_has_calls([
            call("expected-url/spice-query?type=leapseconds&start_time=0", headers=expected_auth_header),
            call("expected-url/spice-query?type=spacecraft_clock&start_time=0", headers=expected_auth_header),
            call("expected-url/spice-query?type=pointing_attitude&start_time=0", headers=expected_auth_header),
            call("expected-url/spice-query?type=imap_frames&start_time=0", headers=expected_auth_header),
            call("expected-url/spice-query?type=science_frames&start_time=0", headers=expected_auth_header),
            call("expected-url/spice-query?type=planetary_ephemeris&start_time=0", headers=expected_auth_header),
            call("expected-url/spice-query?type=ephemeris_reconstructed&start_time=0", headers=expected_auth_header),
            call("expected-url/spice-query?type=planetary_constants&start_time=0", headers=expected_auth_header),
        ])
        self.assertEqual(["naif0012.tls",
                          "imap_sclk_0000.tsc",
                          "imap_dps_2024_335_2025_031_01.ah.bc",
                          "imap_dps_2025_031_2025_120_01.ah.bc",
                          "imap_001.tf",
                          "imap_science_0001.tf",
                          "de440.bsp",
                          "imap_recon_od004_20250924_20251002_v01.bsp",
                          "pck00010.tpc"], spice_kernels)

    @patch('mapping_tool.dependency_collector.imap_data_access.query')
    def test_get_sp_dependencies(self, mock_query):
        hi90_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI, sensor="90", )
        hi45_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.HI, sensor="45", )
        ultra_sf_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.ULTRA, sensor="90",
                                                    frame_descriptor="sf")
        ultra_hf_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.ULTRA, sensor="90",
                                                    frame_descriptor="hf")
        lo_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.LO)

        test_cases = [
            (hi90_descriptor, "hi", "survival-probability-hi-90"),
            (hi45_descriptor, "hi", "survival-probability-hi-45"),
            (ultra_sf_descriptor, "ultra", "survival-probability-ul-sf"),
            (ultra_hf_descriptor, "ultra", "survival-probability-ul-hf"),
            (lo_descriptor, "lo", "survival-probability-lo")
        ]

        for descriptor, instrument_name, expected_glows_descriptor in test_cases:
            mock_query.reset_mock()

            with self.subTest(str(descriptor)):
                start_date = datetime(2025, 1, 1)
                end_date = datetime(2025, 2, 1)

                with tempfile.TemporaryDirectory() as tmpdir:
                    tmpdir = Path(tmpdir)

                    input_l2_path = tmpdir / f'imap_{instrument_name}_l2_map_20250101_v000.cdf'

                    with CDF(str(input_l2_path), masterpath="") as cdf:
                        cdf.attrs["Parents"] = [
                            f"imap_{instrument_name}_l1c_pset_20250615_v001.cdf",
                            f"imap_{instrument_name}_l1c_pset_20250616_v001.cdf"
                        ]

                    mock_query.return_value = [
                        {"file_path": f"imap_glows_l3e_{expected_glows_descriptor}_20250101_v000.cdf"}]

                    dependency_collector = DependencyCollector(descriptor, start_date=start_date, end_date=end_date)
                    sp_deps = dependency_collector.get_survival_probability_dependencies([input_l2_path])

                    mock_query.assert_called_once_with(
                        instrument="glows",
                        descriptor=expected_glows_descriptor,
                        start_date="20250101",
                        end_date="20250201",
                        version='latest'
                    )

                    expected_inputs = [
                        ScienceInput(f"imap_glows_l3e_{expected_glows_descriptor}_20250101_v000.cdf"),
                        ScienceInput(f"imap_{instrument_name}_l1c_pset_20250615_v001.cdf"),
                        ScienceInput(f"imap_{instrument_name}_l1c_pset_20250616_v001.cdf")
                    ]

                    test_helpers.assert_imap_processing_inputs_match(expected_inputs, sp_deps, any_order=True)

    def test_get_sp_deps_returns_empty_list_if_descriptor_is_nsp(self):
        nsp_map_descriptor = create_map_descriptor(survival_corrected="nsp")

        dependency_collector = DependencyCollector(nsp_map_descriptor, Mock(), Mock())
        sp_deps = dependency_collector.get_survival_probability_dependencies([])
        self.assertEqual([], sp_deps)

    @patch('mapping_tool.dependency_collector.requests')
    def test_raises_error_if_http_request_fails(self, mock_requests):
        desired_spice_start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        desired_spice_end = datetime(2025, 3, 1, tzinfo=timezone.utc)

        expected_exception = Exception("unauthenticated")
        mock_requests.get.return_value.raise_for_status.side_effect = expected_exception

        imap_data_access.config["DATA_ACCESS_URL"] = "expected-url"
        imap_data_access.config["ACCESS_TOKEN"] = "bad-token"

        dependency_collector = DependencyCollector(Mock(), desired_spice_start, desired_spice_end)
        with self.assertRaises(Exception) as cm:
            spice_kernels = dependency_collector.collect_spice_kernels()

        self.assertEqual(expected_exception, cm.exception)


def create_imap_query_response_item(instrument="hi", descriptor="descriptor", version="v001", start_date="20240101"):
    return {"file_path": f"imap_{instrument}_{descriptor}_{start_date}_{version}.csv",
            "version": version,
            "start_date": start_date, "descriptor": descriptor}
