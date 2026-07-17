import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, call, Mock

import imap_data_access
from imap_processing.ena_maps.utils.naming import MappableInstrumentShortName
from imap_data_access.processing_input import AncillaryInput, ScienceInput

from imap_l3_processing.utils import FurnishMetakernelOutput, SpiceKernelTypes
from mapping_tool.dependency_collector import (
    DependencyCollector,
    MAPPING_TOOL_KERNEL_TYPES,
    temporary_workaround_for_version_latest,
)
from test import test_helpers
from test.test_builders import create_map_descriptor
from spacepy.pycdf import CDF

from test.test_helpers import get_test_cdf_file_path

MODULE = "mapping_tool.dependency_collector"


class TestDependencyCollector(unittest.TestCase):
    @patch(f"{MODULE}.temporary_workaround_for_version_latest")
    @patch(f"{MODULE}.imap_data_access.query")
    def test_get_pointing_sets(self, mock_query, mock_temporary_workaround_for_version_latest):
        day_one = datetime(2025, 1, 1, tzinfo=timezone.utc)
        day_two = datetime(2025, 1, 2, tzinfo=timezone.utc)
        day_three = datetime(2025, 1, 3, tzinfo=timezone.utc)
        final_day = datetime(2025, 2, 1, tzinfo=timezone.utc)
        mock_temporary_workaround_for_version_latest.return_value = [
            {
                "file_path": "path/to/pset_1",
                "start_date": day_one.strftime("%Y%m%d"),
                "major_version": 1,
                "minor_version": 2,
                "version": "v001.0002",
            },
            {
                "file_path": "path/to/pset_2",
                "start_date": day_two.strftime("%Y%m%d"),
                "major_version": 1,
                "minor_version": 2,
                "version": "v001.0002",
            },
            {
                "file_path": "path/to/pset_3",
                "start_date": day_three.strftime("%Y%m%d"),
                "major_version": 1,
                "minor_version": 2,
                "version": "v001.0002",
            },
        ]
        expected_pointing_sets = ["pset_1", "pset_2", "pset_3"]

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
                mock_temporary_workaround_for_version_latest.reset_mock()
                descriptor = create_map_descriptor(
                    frame_descriptor=frame_descriptor,
                    resolution_str="2deg",
                    duration="2",
                    instrument=instrument,
                    sensor=sensor,
                    principal_data="ena",
                    species="h",
                    survival_corrected="nsp",
                    spin_phase="ram",
                    coordinate_system="hae",
                )

                dependency_collector = DependencyCollector(descriptor, [(day_one, final_day)], False)
                pointing_sets = dependency_collector.get_pointing_sets()

                mock_query.assert_called_once_with(
                    instrument=instrument.name.lower(),
                    start_date=day_one.strftime("%Y%m%d"),
                    end_date=final_day.strftime("%Y%m%d"),
                    data_level="l1c",
                    descriptor=expected_descriptor,
                    major_version=1,
                )
                mock_temporary_workaround_for_version_latest.assert_called_once_with(mock_query.return_value)
                self.assertEqual(expected_pointing_sets, pointing_sets)

    @patch(f"{MODULE}.imap_data_access.query")
    def test_get_pointing_sets_for_multiple_time_ranges(self, mock_query):
        day_one = datetime(2025, 1, 1, tzinfo=timezone.utc)
        day_two = datetime(2025, 1, 2, tzinfo=timezone.utc)
        day_three = datetime(2025, 1, 3, tzinfo=timezone.utc)
        expected_pointing_sets = ["pset_1", "pset_3"]

        mock_query.return_value = [
            create_imap_query_response_item(file_path="path/to/pset_1", start_date=day_one.strftime("%Y%m%d"), version="v000"),
            create_imap_query_response_item(file_path="path/to/pset_2", start_date=day_two.strftime("%Y%m%d"), version="v000"),
            create_imap_query_response_item(file_path="path/to/pset_3", start_date=day_three.strftime("%Y%m%d"), version="v000"),
        ]

        frame_descriptor, instrument, sensor, expected_descriptor = (
            "sf",
            MappableInstrumentShortName.HI,
            "90",
            "90sensor-pset",
        )

        mock_query.reset_mock()
        descriptor = create_map_descriptor(
            frame_descriptor=frame_descriptor,
            resolution_str="2deg",
            duration="2",
            instrument=instrument,
            sensor=sensor,
            principal_data="ena",
            species="h",
            survival_corrected="nsp",
            spin_phase="ram",
            coordinate_system="hae",
        )

        day_one_utc = day_one.replace(tzinfo=timezone.utc)
        day_three_utc = day_three.replace(tzinfo=timezone.utc)

        dependency_collector = DependencyCollector(
            descriptor, [(day_one_utc, day_one_utc), (day_three_utc, day_three_utc)], False
        )
        pointing_sets = dependency_collector.get_pointing_sets()

        mock_query.assert_called_once_with(
            instrument=instrument.name.lower(),
            start_date=day_one.strftime("%Y%m%d"),
            end_date=day_three.strftime("%Y%m%d"),
            data_level="l1c",
            descriptor=expected_descriptor,
            major_version=1,
        )
        self.assertEqual(expected_pointing_sets, pointing_sets)

    @patch(f"{MODULE}.imap_data_access.query")
    def test_get_pointing_sets_for_ultra_combined(self, mock_query):
        expected_pointing_sets = ["u45-pset1", "u45-pset2", "u90-pset1", "u90-pset2"]
        mock_query.side_effect = [
            [
                create_imap_query_response_item(file_path="u45-pset1", start_date="20250107", version="v000"),
                create_imap_query_response_item(file_path="u45-pset2", start_date="20250115", version="v000"),
            ],
            [
                create_imap_query_response_item(file_path="u90-pset1", start_date="20250107", version="v000"),
                create_imap_query_response_item(file_path="u90-pset2", start_date="20250115", version="v000"),
            ],
        ]

        descriptor = create_map_descriptor(
            frame_descriptor="sf",
            resolution_str="nside2",
            duration="2",
            instrument=MappableInstrumentShortName.ULTRA,
            sensor="combined",
            principal_data="ena",
            species="h",
            survival_corrected="sp",
            spin_phase="ram",
            coordinate_system="hae",
        )

        time_ranges = [
            (
                datetime(2025, 1, 1, tzinfo=timezone.utc),
                datetime(2025, 2, 1, tzinfo=timezone.utc),
            )
        ]

        dependency_collector = DependencyCollector(descriptor, time_ranges, False)
        pointing_sets = dependency_collector.get_pointing_sets()

        mock_query.assert_has_calls(
            [
                call(
                    instrument="ultra",
                    data_level="l1c",
                    descriptor="45sensor-spacecraftpset",
                    start_date="20250101",
                    end_date="20250201",
                    major_version=1,
                ),
                call(
                    instrument="ultra",
                    data_level="l1c",
                    descriptor="90sensor-spacecraftpset",
                    start_date="20250101",
                    end_date="20250201",
                    major_version=1,
                ),
            ]
        )

        self.assertEqual(expected_pointing_sets, pointing_sets)

    @patch(f"{MODULE}.imap_data_access.query")
    def test_get_pointing_sets_for_hi_combined(self, mock_query):
        expected_pointing_sets = [
            "h45-pset1",
            "h45-pset2",
            "h90-pset1",
            "h90-pset2",
        ]

        mock_query.side_effect = [
            [
                create_imap_query_response_item(file_path="h45-pset1", start_date="20250105", version="v000"),
                create_imap_query_response_item(file_path="h45-pset2", start_date="20250107", version="v000"),
            ],
            [
                create_imap_query_response_item(file_path="h90-pset1", start_date="20250120", version="v000"),
                create_imap_query_response_item(file_path="h90-pset2", start_date="20250201", version="v000"),
            ],
        ]

        descriptor = create_map_descriptor(
            frame_descriptor="sf",
            resolution_str="nside2",
            duration="2",
            instrument=MappableInstrumentShortName.HI,
            sensor="combined",
            principal_data="ena",
            species="h",
            survival_corrected="sp",
            spin_phase="ram",
            coordinate_system="hae",
        )

        time_ranges = [
            (
                datetime(2025, 1, 1, tzinfo=timezone.utc),
                datetime(2025, 2, 1, tzinfo=timezone.utc),
            )
        ]
        dependency_collector = DependencyCollector(descriptor, time_ranges, False)
        pointing_sets = dependency_collector.get_pointing_sets()

        mock_query.assert_has_calls(
            [
                call(
                    instrument="hi",
                    data_level="l1c",
                    descriptor="45sensor-pset",
                    start_date="20250101",
                    end_date="20250201",
                    major_version=1,
                ),
                call(
                    instrument="hi",
                    data_level="l1c",
                    descriptor="90sensor-pset",
                    start_date="20250101",
                    end_date="20250201",
                    major_version=1,
                ),
            ]
        )

        self.assertEqual(expected_pointing_sets, pointing_sets)

    @patch(f"{MODULE}.imap_data_access.query")
    def test_get_pointing_sets_for_lo_survival_corrected(self, mock_query):
        expected_pointing_sets = [
            "l90-pset1",
            "l90-pset2",
        ]

        mock_query.side_effect = [
            [
                create_imap_query_response_item(file_path="l90-pset1", start_date="20250104", version="v000"),
                create_imap_query_response_item(file_path="l90-pset2", start_date="20250122", version="v000"),
            ],
        ]

        descriptor = create_map_descriptor(
            frame_descriptor="sf",
            resolution_str="nside2",
            duration="2",
            instrument=MappableInstrumentShortName.LO,
            sensor="90",
            principal_data="ena",
            species="h",
            survival_corrected="sp",
            spin_phase="ram",
            coordinate_system="hae",
        )
        time_ranges = [
            (
                datetime(2025, 1, 1, tzinfo=timezone.utc),
                datetime(2025, 2, 1, tzinfo=timezone.utc),
            )
        ]
        dependency_collector = DependencyCollector(descriptor, time_ranges, False)
        pointing_sets = dependency_collector.get_pointing_sets()

        mock_query.assert_has_calls(
            [
                call(
                    instrument="lo",
                    data_level="l1c",
                    descriptor="pset",
                    start_date="20250101",
                    end_date="20250201",
                    major_version=1,
                )
            ]
        )

        self.assertEqual(expected_pointing_sets, pointing_sets)

    @patch(f"{MODULE}.imap_data_access.query")
    def test_get_ancillary_dependencies_finds_nearest_files_to_map_end_date(self, mock_query):
        mock_query.side_effect = [
            [
                create_imap_query_response_item(
                    descriptor="45sensor-cal-prod",
                    version="v002",
                    start_date="20250101",
                ),
                create_imap_query_response_item(
                    descriptor="45sensor-cal-prod",
                    version="v001",
                    start_date="20240101",
                ),
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
            species="h",
            survival_corrected="nsp",
            spin_phase="ram",
            coordinate_system="hae",
        )

        dependency_collector = DependencyCollector(descriptor, [(Mock(), end_date)], False)
        ancillary_dependencies = dependency_collector.get_ancillary_dependencies()

        mock_query.assert_called_with(table="ancillary", instrument="hi", end_date="20260201", version="latest")
        expected_ancillary_dependencies = [AncillaryInput("imap_hi_45sensor-cal-prod_20250101_v002.csv")]
        test_helpers.assert_imap_processing_inputs_match(expected_ancillary_dependencies, ancillary_dependencies)

    @patch(f"{MODULE}.imap_data_access.query")
    def test_get_ancillary_dependencies_correctly_filters_ancillary_inputs(self, mock_query):
        cases = [
            (
                create_map_descriptor(instrument=MappableInstrumentShortName.HI, sensor="90", survival_corrected="nsp"),
                ["90sensor-cal-prod", "90sensor-esa-energies", "90sensor-esa-eta-fit-factors"],
            ),
            (
                create_map_descriptor(instrument=MappableInstrumentShortName.HI, sensor="45", survival_corrected="nsp"),
                ["45sensor-cal-prod", "45sensor-esa-energies", "45sensor-esa-eta-fit-factors"],
            ),
            (
                create_map_descriptor(instrument=MappableInstrumentShortName.LO, survival_corrected="nsp"),
                ["esa-eta-fit-factors"],
            ),
            (
                create_map_descriptor(
                    instrument=MappableInstrumentShortName.ULTRA, principal_data="spx", sensor="combined"
                ),
                ["ulc-spx-energy-ranges"],
            ),
            (
                create_map_descriptor(instrument=MappableInstrumentShortName.ULTRA, principal_data="spx", sensor="45"),
                ["ulc-spx-energy-ranges"],
            ),
            (
                create_map_descriptor(instrument=MappableInstrumentShortName.ULTRA, principal_data="ena"),
                ["l2-energy-bin-group-sizes"],
            ),
            (create_map_descriptor(instrument=MappableInstrumentShortName.LO, survival_corrected="sp"), []),
        ]

        mock_query.return_value = [
            create_imap_query_response_item(
                instrument="ultra", descriptor="l2-energy-bin-group-sizes", version="v001", start_date="20250101"
            ),
            create_imap_query_response_item(
                instrument="ultra", descriptor="ulc-spx-energy-ranges", version="v001", start_date="20250101"
            ),
            create_imap_query_response_item(
                instrument="hi", descriptor="90sensor-cal-prod", version="v001", start_date="20250101"
            ),
            create_imap_query_response_item(
                instrument="hi", descriptor="90sensor-esa-energies", version="v001", start_date="20250101"
            ),
            create_imap_query_response_item(
                instrument="hi", descriptor="90sensor-esa-eta-fit-factors", version="v001", start_date="20250101"
            ),
            create_imap_query_response_item(
                instrument="hi", descriptor="45sensor-cal-prod", version="v001", start_date="20250101"
            ),
            create_imap_query_response_item(
                instrument="hi", descriptor="45sensor-esa-energies", version="v001", start_date="20250101"
            ),
            create_imap_query_response_item(
                instrument="hi", descriptor="45sensor-esa-eta-fit-factors", version="v001", start_date="20250101"
            ),
            create_imap_query_response_item(
                instrument="lo", descriptor="esa-eta-fit-factors", version="v001", start_date="20250101"
            ),
            create_imap_query_response_item(instrument="ultra", descriptor="90sensor-sc-pointing-phi"),
        ]

        for descriptor, expected_ancillary_descriptors in cases:
            mock_query.reset_mock()
            with self.subTest(descriptor=descriptor.to_string()):
                end_date = datetime(2026, 2, 1, tzinfo=timezone.utc)

                dependency_collector = DependencyCollector(descriptor, [(Mock(), end_date)], False)
                ancillary_dependencies = dependency_collector.get_ancillary_dependencies()

                mock_query.assert_called_with(
                    table="ancillary",
                    instrument=descriptor.instrument.name.lower(),
                    end_date="20260201",
                    version="latest",
                )
                self.assertEqual(set(expected_ancillary_descriptors), {d.descriptor for d in ancillary_dependencies})

    @patch(f"{MODULE}.imap_data_access.query")
    def test_get_ancillary_dependencies_writes_energy_bin_edges_to_imap_dir(self, mock_query):
        mock_query.side_effect = [
            [
                create_imap_query_response_item(
                    instrument="ultra", descriptor="l2-energy-bin-group-sizes", start_date="19990101"
                ),
                create_imap_query_response_item(
                    instrument="ultra", descriptor="ancillary-2", version="v001", start_date="20260101"
                ),
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
            species="h",
            survival_corrected="sp",
            spin_phase="ram",
            coordinate_system="hae",
        )

        original_imap_data_dir = imap_data_access.config["DATA_DIR"]
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                test_deletes_stuff_here = Path(tmpdir)
                imap_data_access.config["DATA_DIR"] = test_deletes_stuff_here
                ancillary_ultra_dir = test_deletes_stuff_here / "imap/ancillary/ultra"
                ultra_dep = ancillary_ultra_dir / "imap_ultra_l2-energy-bin-group-sizes_20250924_v000.csv"

                dependency_collector = DependencyCollector(descriptor, [(Mock(), end_date)], False, "0, 10, 20, 40")
                ancillary_dependencies = dependency_collector.get_ancillary_dependencies()

                self.assertTrue(ultra_dep.is_file())
                self.assertEqual("0,10,20,40", ultra_dep.read_text())
                mock_query.assert_called_once_with(
                    table="ancillary",
                    instrument="ultra",
                    end_date="20260201",
                    version="latest",
                )
                expected_ancillary_dependencies = [
                    AncillaryInput("imap_ultra_l2-energy-bin-group-sizes_20250924_v000.csv")
                ]
                test_helpers.assert_imap_processing_inputs_match(
                    expected_ancillary_dependencies, ancillary_dependencies
                )
        finally:
            imap_data_access.config["DATA_DIR"] = original_imap_data_dir

    @patch(f"{MODULE}.temporary_workaround_for_version_latest")
    @patch(f"{MODULE}.imap_data_access.query")
    def test_get_sp_dependencies(self, mock_query, mock_temporary_workaround_for_version_latest):
        hi90_descriptor = create_map_descriptor(
            instrument=MappableInstrumentShortName.HI,
            sensor="90",
        )
        hi45_descriptor = create_map_descriptor(
            instrument=MappableInstrumentShortName.HI,
            sensor="45",
        )
        ultra_sf_descriptor = create_map_descriptor(
            instrument=MappableInstrumentShortName.ULTRA, sensor="90", frame_descriptor="sf"
        )
        ultra_hf_descriptor = create_map_descriptor(
            instrument=MappableInstrumentShortName.ULTRA, sensor="90", frame_descriptor="hf"
        )
        lo_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.LO)

        test_cases = [
            (hi90_descriptor, "hi", "survival-probability-hi-90"),
            (hi45_descriptor, "hi", "survival-probability-hi-45"),
            (ultra_sf_descriptor, "ultra", "survival-probability-ul-sf"),
            (ultra_hf_descriptor, "ultra", "survival-probability-ul-hf"),
            (lo_descriptor, "lo", "survival-probability-lo"),
        ]

        for descriptor, instrument_name, expected_glows_descriptor in test_cases:
            mock_query.reset_mock()
            mock_temporary_workaround_for_version_latest.reset_mock()

            with self.subTest(str(descriptor)):
                start_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
                end_date = datetime(2025, 2, 1, tzinfo=timezone.utc)

                with tempfile.TemporaryDirectory() as tmpdir:
                    tmpdir = Path(tmpdir)

                    input_l2_path = tmpdir / f"imap_{instrument_name}_l2_map_20250101_v000.cdf"

                    with CDF(str(input_l2_path), masterpath="") as cdf:
                        cdf.attrs["Parents"] = [
                            f"imap_{instrument_name}_l1c_pset_20250615_v001.cdf",
                            f"imap_{instrument_name}_l1c_pset_20250616_v001.cdf",
                        ]

                    mock_temporary_workaround_for_version_latest.return_value = [
                        {
                            "file_path": f"imap_glows_l3e_{expected_glows_descriptor}_20250101_v000.cdf",
                            "start_date": "20250101",
                        }
                    ]

                    dependency_collector = DependencyCollector(descriptor, [(start_date, end_date)], False)
                    sp_deps = dependency_collector.get_survival_probability_dependencies([input_l2_path])

                    mock_query.assert_called_once_with(
                        instrument="glows",
                        descriptor=expected_glows_descriptor,
                        start_date="20250101",
                        end_date="20250201",
                        major_version=1,
                    )
                    mock_temporary_workaround_for_version_latest.assert_called_once_with(mock_query.return_value)

                    expected_inputs = [
                        ScienceInput(f"imap_glows_l3e_{expected_glows_descriptor}_20250101_v000.cdf"),
                        ScienceInput(f"imap_{instrument_name}_l1c_pset_20250615_v001.cdf"),
                        ScienceInput(f"imap_{instrument_name}_l1c_pset_20250616_v001.cdf"),
                    ]

                    test_helpers.assert_imap_processing_inputs_match(expected_inputs, sp_deps, any_order=True)

    @patch(f"{MODULE}.imap_data_access.query")
    def test_get_sp_dependencies_for_combined_hi_maps(self, mock_query):
        hi_combined_descriptor = create_map_descriptor(
            instrument=MappableInstrumentShortName.HI,
            sensor="combined",
        )

        expected_glows_descriptor = ["survival-probability-hi-45", "survival-probability-hi-90"]

        start_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2025, 2, 1, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            l2_map_inputs = []
            for sensor in ["45", "90"]:
                l2_map_inputs.append(tmpdir / f"imap_hi_l2_{sensor}-map_20250101_v000.cdf")
                with CDF(str(l2_map_inputs[-1]), masterpath="") as cdf:
                    cdf.attrs["Parents"] = [
                        f"imap_hi_l1c_{sensor}sensor-pset_20250615_v001.cdf",
                        f"imap_hi_l1c_{sensor}sensor-pset_20250616_v001.cdf",
                    ]

            mock_query.side_effect = [
                [
                    create_imap_query_response_item(file_path=f"imap_glows_l3e_{expected_glows_descriptor[0]}_20250101_v000.cdf", start_date="20250101"),
                    create_imap_query_response_item(file_path=f"imap_glows_l3e_{expected_glows_descriptor[0]}_20250102_v000.cdf", start_date="20250102")
                ],
                [
                    create_imap_query_response_item(file_path=f"imap_glows_l3e_{expected_glows_descriptor[1]}_20250101_v000.cdf", start_date="20250101"),
                    create_imap_query_response_item(file_path=f"imap_glows_l3e_{expected_glows_descriptor[1]}_20250102_v000.cdf", start_date="20250102")
                ],
            ]

            dependency_collector = DependencyCollector(hi_combined_descriptor, [(start_date, end_date)], False)
            sp_deps = dependency_collector.get_survival_probability_dependencies(l2_map_inputs)

            mock_query.assert_has_calls(
                [
                    call(
                        instrument="glows",
                        descriptor=expected_glows_descriptor[0],
                        start_date="20250101",
                        end_date="20250201",
                        major_version=1,
                    ),
                    call(
                        instrument="glows",
                        descriptor=expected_glows_descriptor[1],
                        start_date="20250101",
                        end_date="20250201",
                        major_version=1,
                    ),
                ]
            )

            expected_inputs = [
                ScienceInput(f"imap_glows_l3e_{expected_glows_descriptor[0]}_20250101_v000.cdf"),
                ScienceInput(f"imap_glows_l3e_{expected_glows_descriptor[0]}_20250102_v000.cdf"),
                ScienceInput(f"imap_glows_l3e_{expected_glows_descriptor[1]}_20250101_v000.cdf"),
                ScienceInput(f"imap_glows_l3e_{expected_glows_descriptor[1]}_20250102_v000.cdf"),
                ScienceInput(f"imap_hi_l1c_45sensor-pset_20250615_v001.cdf"),
                ScienceInput(f"imap_hi_l1c_45sensor-pset_20250616_v001.cdf"),
                ScienceInput(f"imap_hi_l1c_90sensor-pset_20250615_v001.cdf"),
                ScienceInput(f"imap_hi_l1c_90sensor-pset_20250616_v001.cdf"),
            ]

            test_helpers.assert_imap_processing_inputs_match(expected_inputs, sp_deps, any_order=True)

    @patch(f"{MODULE}.imap_data_access.query")
    def test_get_sp_dependencies_for_combine_data_across_time_ranges(self, mock_query):
        hi90_descriptor = create_map_descriptor(
            instrument=MappableInstrumentShortName.HI,
            sensor="90",
        )
        hi45_descriptor = create_map_descriptor(
            instrument=MappableInstrumentShortName.HI,
            sensor="45",
        )
        ultra_sf_descriptor = create_map_descriptor(
            instrument=MappableInstrumentShortName.ULTRA,
            sensor="90",
            frame_descriptor="sf",
        )
        ultra_hf_descriptor = create_map_descriptor(
            instrument=MappableInstrumentShortName.ULTRA,
            sensor="90",
            frame_descriptor="hf",
        )
        lo_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.LO)

        test_cases = [
            (hi90_descriptor, "hi", "survival-probability-hi-90"),
            (hi45_descriptor, "hi", "survival-probability-hi-45"),
            (ultra_sf_descriptor, "ultra", "survival-probability-ul-sf"),
            (ultra_hf_descriptor, "ultra", "survival-probability-ul-hf"),
            (lo_descriptor, "lo", "survival-probability-lo"),
        ]

        for descriptor, instrument_name, expected_glows_descriptor in test_cases:
            mock_query.reset_mock()

            with self.subTest(str(descriptor)):
                day_one = datetime(2025, 1, 1, tzinfo=timezone.utc)
                day_three = datetime(2025, 1, 3, tzinfo=timezone.utc)

                with tempfile.TemporaryDirectory() as tmpdir:
                    tmpdir = Path(tmpdir)

                    input_l2_path = tmpdir / f"imap_{instrument_name}_l2_map_20250101_v000.cdf"

                    with CDF(str(input_l2_path), masterpath="") as cdf:
                        cdf.attrs["Parents"] = [
                            f"imap_{instrument_name}_l1c_pset_20250615_v001.cdf",
                            f"imap_{instrument_name}_l1c_pset_20250616_v001.cdf",
                        ]

                    mock_query.return_value = [
                        create_imap_query_response_item(file_path=f"imap_glows_l3e_{expected_glows_descriptor}_20250101_v000.cdf",
                                                        start_date="20250101"),
                        create_imap_query_response_item(file_path=f"imap_glows_l3e_{expected_glows_descriptor}_20250102_v000.cdf",
                                                        start_date="20250102"),
                        create_imap_query_response_item(file_path=f"imap_glows_l3e_{expected_glows_descriptor}_20250103_v000.cdf",
                                                        start_date="20250103")
                    ]

                    dependency_collector = DependencyCollector(
                        descriptor, [(day_one, day_one), (day_three, day_three)], False
                    )
                    sp_deps = dependency_collector.get_survival_probability_dependencies([input_l2_path])

                    mock_query.assert_called_once_with(
                        instrument="glows",
                        descriptor=expected_glows_descriptor,
                        start_date="20250101",
                        end_date="20250103",
                        major_version=1,
                    )

                    expected_inputs = [
                        ScienceInput(f"imap_glows_l3e_{expected_glows_descriptor}_20250101_v000.cdf"),
                        ScienceInput(f"imap_glows_l3e_{expected_glows_descriptor}_20250103_v000.cdf"),
                        ScienceInput(f"imap_{instrument_name}_l1c_pset_20250615_v001.cdf"),
                        ScienceInput(f"imap_{instrument_name}_l1c_pset_20250616_v001.cdf"),
                    ]

                    test_helpers.assert_imap_processing_inputs_match(expected_inputs, sp_deps, any_order=True)

    @patch(f"{MODULE}.imap_data_access.query")
    def test_get_sp_dependencies_for_ultra_nsp_combined(self, _):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            input_l2_45_path = tmpdir / f"imap_ultra_l2_map45_20250101_v000.cdf"
            with CDF(str(input_l2_45_path), masterpath="") as cdf:
                cdf.attrs["Parents"] = [
                    f"imap_ultra_l1c_45pset_20250615_v001.cdf",
                    f"imap_ultra_l1c_45pset_20250616_v001.cdf",
                ]

            input_l2_90_path = tmpdir / f"imap_ultra_l2_map90_20250101_v000.cdf"
            with CDF(str(input_l2_90_path), masterpath="") as cdf:
                cdf.attrs["Parents"] = [
                    f"imap_ultra_l1c_90pset_20250615_v001.cdf",
                    f"imap_ultra_l1c_90pset_20250616_v001.cdf",
                ]

            dependency_collector = DependencyCollector(
                create_map_descriptor(
                    instrument=MappableInstrumentShortName.ULTRA,
                    sensor="combined",
                    survival_corrected="nsp",
                ),
                [(datetime(2026, 2, 6), datetime(2026, 2, 7))],
                False,
            )

            sp_deps = dependency_collector.get_survival_probability_dependencies(
                [
                    input_l2_45_path,
                    input_l2_90_path,
                ]
            )

            expected_inputs = [
                ScienceInput(f"imap_ultra_l1c_45pset_20250615_v001.cdf"),
                ScienceInput(f"imap_ultra_l1c_45pset_20250616_v001.cdf"),
                ScienceInput(f"imap_ultra_l1c_90pset_20250615_v001.cdf"),
                ScienceInput(f"imap_ultra_l1c_90pset_20250616_v001.cdf"),
            ]

            test_helpers.assert_imap_processing_inputs_match(expected_inputs, sp_deps, any_order=True)

    def test_get_sp_deps_returns_empty_list_for_hi_combined_nsp(self):
        nsp_map_descriptor = create_map_descriptor(
            instrument=MappableInstrumentShortName.HI,
            sensor="combined",
            survival_corrected="nsp",
        )

        dependency_collector = DependencyCollector(nsp_map_descriptor, [((Mock(), Mock()))], False)
        sp_deps = dependency_collector.get_survival_probability_dependencies(
            [get_test_cdf_file_path() / "l2_ena_20250115.cdf"]
        )
        self.assertEqual([], sp_deps)

    def test_get_sp_deps_returns_empty_list_for_spx_maps(self):
        hi_spx_sp_descriptor = create_map_descriptor(
            instrument=MappableInstrumentShortName.HI,
            sensor="combined",
            principal_data="spx",
        )

        lo_spx_sp_descriptor = create_map_descriptor(instrument=MappableInstrumentShortName.LO, principal_data="spx")

        lo_spxnbs_sp_descriptor = create_map_descriptor(
            instrument=MappableInstrumentShortName.LO, principal_data="spxnbs"
        )

        hi_spx_descriptor = create_map_descriptor(
            instrument=MappableInstrumentShortName.HI,
            sensor="combined",
            survival_corrected="nsp",
            principal_data="spx",
        )

        lo_spx_descriptor = create_map_descriptor(
            instrument=MappableInstrumentShortName.LO,
            survival_corrected="nsp",
            principal_data="spx",
        )

        ultra_spx_descriptor = create_map_descriptor(
            instrument=MappableInstrumentShortName.ULTRA,
            survival_corrected="nsp",
            principal_data="spx",
        )

        cases = [
            ("hi", hi_spx_descriptor),
            ("lo", lo_spx_descriptor),
            ("hi sp", hi_spx_sp_descriptor),
            ("lo sp", lo_spx_sp_descriptor),
            ("lo spxnbs", lo_spxnbs_sp_descriptor),
            ("ultra", ultra_spx_descriptor),
        ]

        for case, descriptor in cases:
            with self.subTest(case):
                dependency_collector = DependencyCollector(descriptor, [(Mock(), Mock())], False)
                sp_deps = dependency_collector.get_survival_probability_dependencies(
                    [get_test_cdf_file_path() / "l2_ena_20250115.cdf"]
                )
                self.assertEqual([], sp_deps)

    @patch(f"{MODULE}.furnish_spice_metakernel")
    def test_furnish_spice_kernels(self, mock_furnish):
        expected_output = Mock(spec=FurnishMetakernelOutput)
        mock_furnish.return_value = expected_output

        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 3, 1, tzinfo=timezone.utc)
        dc = DependencyCollector(create_map_descriptor(), [(start, end)], False)

        result = dc.furnish_spice_kernels()

        mock_furnish.assert_called_once_with(
            datetime(2025, 1, 1),
            datetime(2025, 3, 1),
            MAPPING_TOOL_KERNEL_TYPES,
        )
        self.assertIs(expected_output, result)

    @patch(f"{MODULE}.furnish_spice_metakernel")
    def test_furnish_spice_kernels_uses_predicted_ephemeris_when_flag_is_set(self, mock_furnish):
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 3, 1, tzinfo=timezone.utc)
        dc = DependencyCollector(create_map_descriptor(), [(start, end)], include_predicted_ephemeris=True)
        dc.furnish_spice_kernels()

        mock_furnish.assert_called_once_with(
            datetime(2025, 1, 1),
            datetime(2025, 3, 1),
            MAPPING_TOOL_KERNEL_TYPES + [SpiceKernelTypes.EphemerisPredicted],
        )

    @patch(f"{MODULE}.furnish_spice_metakernel")
    def test_furnish_spice_kernels_strips_timezone(self, mock_furnish):
        mock_furnish.return_value = Mock(spec=FurnishMetakernelOutput)

        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 3, 1, tzinfo=timezone.utc)
        dc = DependencyCollector(create_map_descriptor(), [(start, end)], False)

        dc.furnish_spice_kernels()

        self.assertIsNone(mock_furnish.call_args[0][0].tzinfo)
        self.assertIsNone(mock_furnish.call_args[0][1].tzinfo)

    @patch(f"{MODULE}.furnish_spice_metakernel")
    def test_furnish_spice_kernels_propagates_errors(self, mock_furnish):
        mock_furnish.side_effect = ConnectionError("network failure")
        dc = DependencyCollector(
            create_map_descriptor(),
            [
                (
                    datetime(2025, 1, 1, tzinfo=timezone.utc),
                    datetime(2025, 3, 1, tzinfo=timezone.utc),
                )
            ],
            False,
        )
        with self.assertRaises(ConnectionError):
            dc.furnish_spice_kernels()

    @patch(f"{MODULE}.get_spice_kernels_file_names")
    def test_get_spice_kernel_names(self, mock_get_spice_kernels_file_names):
        mock_get_spice_kernels_file_names.return_value = [
            "imap/spice/lsk/naif0012.tls",
            "imap/spice/spk/de440.bsp",
        ]
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 3, 1, tzinfo=timezone.utc)
        dc = DependencyCollector(create_map_descriptor(), [(start, end)], False)

        result = dc.get_spice_kernel_names()

        mock_get_spice_kernels_file_names.assert_called_once_with(
            datetime(2025, 1, 1),
            datetime(2025, 3, 1),
            MAPPING_TOOL_KERNEL_TYPES,
        )
        self.assertEqual(["naif0012.tls", "de440.bsp"], result)

    @patch(f"{MODULE}.get_spice_kernels_file_names")
    def test_get_spice_kernel_names_uses_predicted_ephemeris_when_flag_is_set(self, mock_get_spice_kernels_file_names):
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 3, 1, tzinfo=timezone.utc)
        dc = DependencyCollector(create_map_descriptor(), [(start, end)], include_predicted_ephemeris=True)
        dc.get_spice_kernel_names()

        mock_get_spice_kernels_file_names.assert_called_once_with(
            datetime(2025, 1, 1),
            datetime(2025, 3, 1),
            MAPPING_TOOL_KERNEL_TYPES + [SpiceKernelTypes.EphemerisPredicted],
        )

    @patch(f"{MODULE}.get_spice_kernels_file_names")
    def test_get_spice_kernel_names_strips_timezone(self, mock_get_spice_kernels_file_names):
        mock_get_spice_kernels_file_names.return_value = []

        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 3, 1, tzinfo=timezone.utc)
        dc = DependencyCollector(create_map_descriptor(), [(start, end)], False)

        dc.get_spice_kernel_names()

        self.assertIsNone(mock_get_spice_kernels_file_names.call_args[0][0].tzinfo)
        self.assertIsNone(mock_get_spice_kernels_file_names.call_args[0][1].tzinfo)

    @patch(f"{MODULE}.get_spice_kernels_file_names")
    def test_get_spice_kernel_names_propagates_errors(self, mock_get_spice_kernels_file_names):
        mock_get_spice_kernels_file_names.side_effect = ConnectionError("network failure")
        dc = DependencyCollector(
            create_map_descriptor(),
            [(datetime(2025, 1, 1, tzinfo=timezone.utc), datetime(2025, 3, 1, tzinfo=timezone.utc))],
            False,
        )
        with self.assertRaises(ConnectionError):
            dc.get_spice_kernel_names()

    def test_temporary_workaround_for_version_latest(self):
        day_1_higher_version = create_imap_query_response_item(start_date="20260501", version="v001.0002")
        day_1_lower_version = create_imap_query_response_item(start_date="20260501", version="v001.0001")
        day_2_lower_version = create_imap_query_response_item(start_date="20260502", version="v001.0001")
        day_2_higher_version = create_imap_query_response_item(start_date="20260502", version="v001.0003")
        day_1_old_version_format = create_imap_query_response_item(start_date="20260501", version="v002")
        alt_descriptor_v1 = create_imap_query_response_item(
            descriptor="different", start_date="20260501", version="v001.0001"
        )
        alt_descriptor_v2 = create_imap_query_response_item(
            descriptor="different", start_date="20260501", version="v001.0002"
        )
        alt_repointing_v1 = create_imap_query_response_item(repointing=2, start_date="20260501", version="v001.0001")
        alt_repointing_v2 = create_imap_query_response_item(repointing=2, start_date="20260501", version="v001.0002")
        no_repointing_v1 = create_imap_query_response_item(repointing=None, start_date="20260501", version="v001.0001")
        no_repointing_v2 = create_imap_query_response_item(repointing=None, start_date="20260501", version="v001.0002")
        unique_data_level = create_imap_query_response_item(data_level="l2", start_date="20260501", version="v001.0002")
        unique_instrument = create_imap_query_response_item(instrument="idex", start_date="20260501", version="v001.0002")

        input_query_results = [
            day_1_lower_version, day_1_higher_version,
            day_2_lower_version, day_2_higher_version,
            alt_descriptor_v1, alt_descriptor_v2,
            alt_repointing_v1, alt_repointing_v2,
            no_repointing_v1, no_repointing_v2,
            unique_data_level, unique_instrument,
            day_1_old_version_format
        ]
        output_query_results = [
            day_1_higher_version, day_2_higher_version, alt_descriptor_v2, alt_repointing_v2, no_repointing_v2,
            unique_data_level, unique_instrument,
        ]

        self.assertEqual(output_query_results, temporary_workaround_for_version_latest(input_query_results))

def create_imap_query_response_item(file_path=None,instrument="hi", data_level="l3", descriptor="descriptor", version="v001", start_date="20240101", repointing:int|None=1):
    return {"file_path": file_path or f"imap_{instrument}_{descriptor}_{start_date}_{version}.csv",
            "instrument": instrument,
            "data_level": data_level,
            "version": version,
            "start_date": start_date, "descriptor": descriptor,
            "repointing": repointing,
    }
