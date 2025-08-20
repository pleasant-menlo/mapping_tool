from datetime import datetime, timezone, timedelta
from pathlib import Path

import jsonschema.exceptions
from typing import Dict
from unittest import TestCase
from unittest.mock import patch

import yaml

from mapping_tool import config_schema
from mapping_tool.configuration import Configuration, CanonicalMapPeriod, DataLevel, TimeRange
from imap_processing.spice.geometry import SpiceFrame

from mapping_tool.mapping_tool_descriptor import CustomSpiceFrame
from test.test_builders import create_configuration, create_config_dict, create_canonical_map_period, \
    create_map_descriptor, create_canonical_map_period_dict, create_utc_datetime
from test.test_helpers import get_example_config_path
from imap_processing.ena_maps.utils.naming import MappableInstrumentShortName


class TestConfiguration(TestCase):
    def test_from_file(self):
        for extension in ["json", "yaml"]:
            with self.subTest(extension):
                example_config_path = get_example_config_path() / f"test_l2_config.{extension}"
                config: Configuration = Configuration.from_file(example_config_path)

                expected_config: Configuration = Configuration(
                    canonical_map_period=CanonicalMapPeriod(year=2025, quarter=1, map_period=6, number_of_maps=1),
                    instrument="Hi 90",
                    spin_phase="Ram",
                    reference_frame_type="spacecraft",
                    survival_corrected=True,
                    spice_frame_name="ECLIPJ2000",
                    pixelation_scheme="square",
                    pixel_parameter=2,
                    map_data_type="ENA Intensity",
                    lo_species=None,
                    output_directory=Path('.'),
                    quantity_suffix="CUSTOM",
                    kernel_path=Path("path/to/another_kernel"),
                    raw_config=yaml.dump(yaml.safe_load(example_config_path.read_text()))
                )

                self.assertEqual(expected_config, config)

    def test_from_file_parses_time_ranges(self):
        for extension in ["json", "yaml"]:
            with self.subTest(extension):
                example_config_path = get_example_config_path() / f"test_l2_config_defined_time_ranges.{extension}"
                config: Configuration = Configuration.from_file(example_config_path)

                expected_config: Configuration = Configuration(
                    time_ranges=[
                        TimeRange(start=datetime(2025, 1, 1, 1, 1, 1, 100000, tzinfo=timezone(timedelta(seconds=3600))),
                                  end=datetime(2025, 1, 2, 2, 2, 2, 200000, tzinfo=timezone(timedelta(seconds=7200)))),
                        TimeRange(start=datetime(2025, 1, 3, 3, 3, 3, 300000, tzinfo=timezone.utc),
                                  end=datetime(2025, 1, 4, 0, 0, tzinfo=timezone.utc))
                    ],
                    instrument="Hi 90",
                    spin_phase="Ram",
                    reference_frame_type="spacecraft",
                    survival_corrected=True,
                    spice_frame_name="ECLIPJ2000",
                    pixelation_scheme="square",
                    pixel_parameter=2,
                    map_data_type="ENA Intensity",
                    lo_species=None,
                    output_directory=Path('.'),
                    quantity_suffix="CUSTOM",
                    kernel_path=Path("path/to/another_kernel"),
                    raw_config=yaml.dump(yaml.safe_load(example_config_path.read_text()))
                )

                self.assertEqual(expected_config, config)

    def test_from_file_throws_error_if_passed_bad_file_type(self):
        file_name = "test_l2_config.bad"
        with self.assertRaises(ValueError) as context:
            Configuration.from_file(Path(file_name))
        self.assertIn(f'Configuration file {file_name} must have .json or .yaml extension', str(context.exception))

    def test_from_file_with_optional_config_fields(self):
        for extension in ["json", "yaml"]:
            with self.subTest(extension):
                example_config_path = get_example_config_path() / f"test_config_with_optionals.{extension}"
                config: Configuration = Configuration.from_file(example_config_path)

                expected_config: Configuration = Configuration(
                    raw_config=yaml.dump(yaml.safe_load(example_config_path.read_text())),
                    canonical_map_period=CanonicalMapPeriod(year=2025, quarter=1, map_period=6, number_of_maps=1),
                    instrument='Ultra 45',
                    spin_phase="Ram",
                    reference_frame_type="spacecraft",
                    survival_corrected=True,
                    spice_frame_name="IMAP_HNU",
                    pixelation_scheme="square",
                    pixel_parameter=2,
                    map_data_type="ENA Intensity",
                    lo_species="h",
                    output_directory=Path('path/to/output'),
                    quantity_suffix="custom",
                    kernel_path=Path("path/to/kernel")
                )

                self.assertEqual(expected_config, config)

    @patch("mapping_tool.configuration.validate")
    def test_from_file_calls_validate_with_the_configuration_schema(self, mock_validate):
        for extension in ["json", "yaml"]:
            with self.subTest(extension):
                example_config_path = get_example_config_path() / f"test_l2_config.{extension}"
                Configuration.from_file(example_config_path)

                expected_config: Dict = {
                    "canonical_map_period": CanonicalMapPeriod(
                        year=2025,
                        quarter=1,
                        map_period=6,
                        number_of_maps=1
                    ),
                    "instrument": "Hi 90",
                    "spin_phase": "Ram",
                    "reference_frame_type": "spacecraft",
                    "survival_corrected": True,
                    "spice_frame_name": "ECLIPJ2000",
                    "pixelation_scheme": "square",
                    "pixel_parameter": 2,
                    "map_data_type": "ENA Intensity",
                    "kernel_path": Path("path/to/another_kernel")
                }

                mock_validate.assert_called_with(expected_config, config_schema.schema)

    @patch("mapping_tool.configuration.json.loads")
    def test_from_file_fails_validation_with_invalid_config(self, mock_loads):
        validation_error_cases = [
            ("invalid instrument", {"instrument": "90", **create_canonical_map_period_dict()}),
            ("invalid spin phase", {"spin_phase": "none", **create_canonical_map_period_dict()}),
            ("invalid reference frame", {"reference_frame_type": "spacecraft kinematic", **create_canonical_map_period_dict()}),
            ("invalid survival probability corrected", {"survival_corrected": "YES", **create_canonical_map_period_dict()}),
            ("invalid cannot have both canonical and time_ranges included", {"time_ranges": {"start": "2025-01-03T03:03:03.3", "stop": "2025-01-04T03:03:03.3"}}),
            ("invalid must include either time ranges or canonical map period", {}),
            ("invalid map_data_type", {"map_data_type": "Directions", **create_canonical_map_period_dict()}),

        ]
        for name, case in validation_error_cases:
            with self.subTest(name):
                mock_loads.return_value = create_config_dict(case)
                with self.assertRaises(jsonschema.exceptions.ValidationError):
                    Configuration.from_file(get_example_config_path() / "test_l2_config.json")

    def test_get_map_descriptors_frame_descriptors(self):
        cases = [
            ("spacecraft", "sf"),
            ("heliospheric", "hf"),
            ("heliospheric kinematic", "hk"),
        ]

        for case, expected in cases:
            with self.subTest(f"{case}, {expected}"):
                input_config = create_configuration(reference_frame_type=case)
                descriptor = input_config.get_map_descriptor()
                self.assertEqual(expected, descriptor.frame_descriptor)

    def test_get_map_descriptors_principal_data(self):
        cases = [
            ("ENA Intensity", "ena", DataLevel.L2),
            ("Spectral Index", "spx", DataLevel.L3)
        ]

        for case, expected_descriptor, expected_data_level in cases:
            with self.subTest(f"{case}, {expected_descriptor}"):
                input_config = create_configuration(map_data_type=case)
                descriptor = input_config.get_map_descriptor()
                self.assertEqual(expected_descriptor, descriptor.principal_data)

    def test_get_map_descriptors_spin_phase(self):
        cases = [
            ("Ram", "ram"),
            ("ram", "ram"),
            ("Anti-ram", "anti"),
            ("anti-ram", "anti"),
            ("Full spin", "full"),
            ("full spin", "full")
        ]

        for case, expected in cases:
            with self.subTest(f"{case}, {expected}"):
                input_config = create_configuration(spin_phase=case)
                descriptor = input_config.get_map_descriptor()
                self.assertEqual(expected, descriptor.spin_phase)

    def test_get_map_descriptors_spice_frame_name_and_path(self):
        cases = [
            ("ECLIPJ2000", None, "eclipj2000", SpiceFrame),
            ("hae", None, "hae", SpiceFrame),
            ("IMAP_HNU", None, "imaphnu", SpiceFrame),
            ("IMAP_CUSTOM", Path("path_to_custom_kernel"), "imapcustom", CustomSpiceFrame),
            ("ECLIPJ2000", Path("path_to_custom_kernel"), "eclipj2000", CustomSpiceFrame),
        ]
        for spice_frame_name, spice_path, expected_name, expected_type in cases:
            with self.subTest(f"{spice_frame_name}, {expected_name}"):
                input_config = create_configuration(spice_frame_name=spice_frame_name, kernel_path=spice_path)
                descriptor = input_config.get_map_descriptor()
                self.assertIsInstance(descriptor.spice_frame, expected_type)
                self.assertEqual(expected_name, descriptor.coordinate_system)
                self.assertEqual(spice_path, descriptor.kernel_path)

    def test_get_map_descriptors_raises_error_for_invalid_spice_frame_name(self):
        spice_frame_name = "Bad"
        input_config = create_configuration(spice_frame_name=spice_frame_name)

        with self.assertRaises(ValueError) as error:
            _ = input_config.get_map_descriptor()

        self.assertEqual(str(error.exception),
                         f"Unknown Spice Frame {spice_frame_name} with no custom kernel path provided")

    def test_get_map_descriptors_resolution(self):
        cases = [
            ("square", 2, "2deg"),
            ("Square", 2, "2deg"),
            ("HEALPIX", 128, "nside128"),
            ("healpix", 128, "nside128"),
        ]

        for scheme, parameter, expected in cases:
            with self.subTest(f"{scheme}, {parameter}, {expected}"):
                input_config = create_configuration(pixelation_scheme=scheme, pixel_parameter=parameter)
                descriptor = input_config.get_map_descriptor()
                self.assertEqual(expected, descriptor.resolution_str)

    def test_get_map_descriptors_duration(self):
        start_1 = create_utc_datetime()
        end_1 = start_1 + timedelta(hours=1)
        start_2 = end_1 + timedelta(days=23)
        end_2 = start_2 + timedelta(hours=24)
        time_ranges = [
            TimeRange(start=start_1, end=end_1),
            TimeRange(start=start_2, end=end_2),
        ]

        cases = [
            ({"canonical_map_period": create_canonical_map_period()}, "6mo"),
            ({"time_ranges": time_ranges}, "0mo"),
        ]

        for timing_type, expected in cases:
            with self.subTest(f"{timing_type},{expected}"):
                input_config = create_configuration(**timing_type)
                descriptor = input_config.get_map_descriptor()
                self.assertEqual(expected, descriptor.duration)

    def test_get_map_descriptors_instrument_and_sensor(self):
        cases = [
            ("hi 45", MappableInstrumentShortName.HI, "45", "h45"),
            ("Hi 90", MappableInstrumentShortName.HI, "90", "h90"),
            ("hi combined", MappableInstrumentShortName.HI, "combined", "hic"),
            ("Ultra 45", MappableInstrumentShortName.ULTRA, "45", "u45"),
            ("ultra 90", MappableInstrumentShortName.ULTRA, "90", "u90"),
            ("Ultra combined", MappableInstrumentShortName.ULTRA, "combined", "ulc"),
            ("Lo", MappableInstrumentShortName.LO, "", "ilo"),
            ("lo", MappableInstrumentShortName.LO, "", "ilo"),
            ("GLOWS", MappableInstrumentShortName.GLOWS, "", "glx"),
            ("glows", MappableInstrumentShortName.GLOWS, "", "glx"),
            ("IDEX", MappableInstrumentShortName.IDEX, "", "idx"),
            ("idex", MappableInstrumentShortName.IDEX, "", "idx"),
        ]
        for case, instrument, sensor, instrument_descriptor in cases:
            with self.subTest(f"{case}, {instrument}, {sensor}"):
                input_config = create_configuration(instrument=case)
                descriptor = input_config.get_map_descriptor()
                self.assertEqual(instrument, descriptor.instrument)
                self.assertEqual(sensor, descriptor.sensor)
                self.assertEqual(instrument_descriptor, descriptor.instrument_descriptor)

    def test_get_map_date_ranges_when_config_has_date_ranges(self):
        start_1 = create_utc_datetime()
        end_1 = start_1 + timedelta(hours=1)
        start_2 = end_1 + timedelta(days=23)
        end_2 = start_2 + timedelta(hours=24)
        time_ranges = [
            TimeRange(start=start_1, end=end_1),
            TimeRange(start=start_2, end=end_2),
        ]
        input_config = create_configuration(time_ranges=time_ranges)

        actual_date_ranges = input_config.get_map_date_ranges()
        expected_date_ranges = [(start_1, end_1), (start_2, end_2)]

        self.assertEqual(expected_date_ranges, actual_date_ranges)

    def test_get_map_date_ranges_sorts_input_ranges(self):
        start_1 = create_utc_datetime()
        end_1 = start_1 + timedelta(hours=1)
        start_2 = end_1 + timedelta(days=23)
        end_2 = start_2 + timedelta(hours=24)
        time_ranges = [
            TimeRange(start=start_2, end=end_2),
            TimeRange(start=start_1, end=end_1),
        ]
        input_config = create_configuration(time_ranges=time_ranges)

        actual_date_ranges = input_config.get_map_date_ranges()
        expected_date_ranges = [(start_1, end_1), (start_2, end_2)]

        self.assertEqual(expected_date_ranges, actual_date_ranges)

    def test_get_map_date_ranges_canonical(self):
        # @formatter:off
        cases = [
            (2010, 1, 3, 1, [(datetime(2010, 1, 1, 0, 0, tzinfo=timezone.utc), datetime(2010, 4, 2, 7, 30, tzinfo=timezone.utc))]),
            (2012, 2, 3, 1, [(datetime(2012, 4, 1, 7, 30, tzinfo=timezone.utc), datetime(2012, 7, 1, 15, 0, tzinfo=timezone.utc))]),
            (2013, 3, 3, 1, [(datetime(2013, 7, 2, 15, 0, tzinfo=timezone.utc), datetime(2013, 10, 1, 22, 30, tzinfo=timezone.utc))]),
            (2017, 4, 3, 1, [(datetime(2017, 10, 1, 22, 30, tzinfo=timezone.utc), datetime(2018, 1, 1, 6, 0, tzinfo=timezone.utc))]),

            (2010, 1, 6, 1, [(datetime(2010, 1, 1, 0, 0, tzinfo=timezone.utc), datetime(2010, 7, 2, 15, 0, tzinfo=timezone.utc))]),
            (2012, 2, 6, 1, [(datetime(2012, 4, 1, 7, 30, tzinfo=timezone.utc), datetime(2012, 9, 30, 22, 30, tzinfo=timezone.utc))]),
            (2013, 3, 6, 1, [(datetime(2013, 7, 2, 15, 0, tzinfo=timezone.utc), datetime(2014, 1, 1, 6, 0, tzinfo=timezone.utc))]),
            (2017, 4, 6, 1, [(datetime(2017, 10, 1, 22, 30, tzinfo=timezone.utc), datetime(2018, 4, 2, 13, 30, tzinfo=timezone.utc))]),

            (2010, 1, 12, 1, [(datetime(2010, 1, 1, 0, 0, tzinfo=timezone.utc), datetime(2011, 1, 1, 6, 0, tzinfo=timezone.utc))]),
            (2012, 2, 12, 1, [(datetime(2012, 4, 1, 7, 30, tzinfo=timezone.utc), datetime(2013, 4, 1, 13, 30, tzinfo=timezone.utc))]),
            (2013, 3, 12, 1, [(datetime(2013, 7, 2, 15, 0, tzinfo=timezone.utc), datetime(2014, 7, 2, 21, 0, tzinfo=timezone.utc))]),
            (2017, 4, 12, 1, [(datetime(2017, 10, 1, 22, 30, tzinfo=timezone.utc), datetime(2018, 10, 2, 4, 30, tzinfo=timezone.utc))]),

            (2010, 1, 3, 2, [(datetime(2010, 1, 1, 0, 0, tzinfo=timezone.utc), datetime(2010, 4, 2, 7, 30, tzinfo=timezone.utc)),
                             (datetime(2010, 4, 2, 7, 30, tzinfo=timezone.utc), datetime(2010, 7, 2, 15, 0, tzinfo=timezone.utc))]),
            (2010, 2, 12, 2, [(datetime(2010, 4, 2, 7, 30, tzinfo=timezone.utc), datetime(2011, 4, 2, 13, 30, tzinfo=timezone.utc)),
                              (datetime(2011, 4, 2, 13, 30, tzinfo=timezone.utc), datetime(2012, 4, 1, 19, 30, tzinfo=timezone.utc))]),
            (2012, 4, 6, 3, [(datetime(2012, 9, 30, 22, 30, tzinfo=timezone.utc), datetime(2013, 4, 1, 13, 30, tzinfo=timezone.utc)),
                             (datetime(2013, 4, 1, 13, 30, tzinfo=timezone.utc), datetime(2013, 10, 1, 4, 30, tzinfo=timezone.utc)),
                             (datetime(2013, 10, 1, 4, 30, tzinfo=timezone.utc), datetime(2014, 4, 1, 19, 30, tzinfo=timezone.utc))]),
        ]
        # @formatter:on
        for year, quarter, period, number_of_maps, expected in cases:
            with self.subTest(f"year: {year}, quarter: {quarter}, period: {period}, num_maps: {number_of_maps}"):
                canonical_map_period = create_canonical_map_period(year=year, quarter=quarter, map_period=period,
                                                                   number_of_maps=number_of_maps)
                input_config = create_configuration(canonical_map_period=canonical_map_period)

                date_range = input_config.get_map_date_ranges()

                self.assertEqual(expected, date_range)




class TestCanonicalMapPeriod(TestCase):
    def test_calculate_date_ranges(self):
        # @formatter:off
        cases = [
            (2010, 1, 3, 1, [(datetime(2010, 1, 1, 0, 0, tzinfo=timezone.utc), datetime(2010, 4, 2, 7, 30, tzinfo=timezone.utc))]),
            (2012, 2, 3, 1, [(datetime(2012, 4, 1, 7, 30, tzinfo=timezone.utc), datetime(2012, 7, 1, 15, 0, tzinfo=timezone.utc))]),
            (2013, 3, 3, 1, [(datetime(2013, 7, 2, 15, 0, tzinfo=timezone.utc), datetime(2013, 10, 1, 22, 30, tzinfo=timezone.utc))]),
            (2017, 4, 3, 1, [(datetime(2017, 10, 1, 22, 30, tzinfo=timezone.utc), datetime(2018, 1, 1, 6, 0, tzinfo=timezone.utc))]),

            (2010, 1, 6, 1, [(datetime(2010, 1, 1, 0, 0, tzinfo=timezone.utc), datetime(2010, 7, 2, 15, 0, tzinfo=timezone.utc))]),
            (2012, 2, 6, 1, [(datetime(2012, 4, 1, 7, 30, tzinfo=timezone.utc), datetime(2012, 9, 30, 22, 30, tzinfo=timezone.utc))]),
            (2013, 3, 6, 1, [(datetime(2013, 7, 2, 15, 0, tzinfo=timezone.utc), datetime(2014, 1, 1, 6, 0, tzinfo=timezone.utc))]),
            (2017, 4, 6, 1, [(datetime(2017, 10, 1, 22, 30, tzinfo=timezone.utc), datetime(2018, 4, 2, 13, 30, tzinfo=timezone.utc))]),

            (2010, 1, 12, 1, [(datetime(2010, 1, 1, 0, 0, tzinfo=timezone.utc), datetime(2011, 1, 1, 6, 0, tzinfo=timezone.utc))]),
            (2012, 2, 12, 1, [(datetime(2012, 4, 1, 7, 30, tzinfo=timezone.utc), datetime(2013, 4, 1, 13, 30, tzinfo=timezone.utc))]),
            (2013, 3, 12, 1, [(datetime(2013, 7, 2, 15, 0, tzinfo=timezone.utc), datetime(2014, 7, 2, 21, 0, tzinfo=timezone.utc))]),
            (2017, 4, 12, 1, [(datetime(2017, 10, 1, 22, 30, tzinfo=timezone.utc), datetime(2018, 10, 2, 4, 30, tzinfo=timezone.utc))]),

            (2010, 1, 3, 2, [(datetime(2010, 1, 1, 0, 0, tzinfo=timezone.utc), datetime(2010, 4, 2, 7, 30, tzinfo=timezone.utc)),
                             (datetime(2010, 4, 2, 7, 30, tzinfo=timezone.utc), datetime(2010, 7, 2, 15, 0, tzinfo=timezone.utc))]),
            (2010, 2, 12, 2, [(datetime(2010, 4, 2, 7, 30, tzinfo=timezone.utc), datetime(2011, 4, 2, 13, 30, tzinfo=timezone.utc)),
                              (datetime(2011, 4, 2, 13, 30, tzinfo=timezone.utc), datetime(2012, 4, 1, 19, 30, tzinfo=timezone.utc))]),
            (2012, 4, 6, 3, [(datetime(2012, 9, 30, 22, 30, tzinfo=timezone.utc), datetime(2013, 4, 1, 13, 30, tzinfo=timezone.utc)),
                             (datetime(2013, 4, 1, 13, 30, tzinfo=timezone.utc), datetime(2013, 10, 1, 4, 30, tzinfo=timezone.utc)),
                             (datetime(2013, 10, 1, 4, 30, tzinfo=timezone.utc), datetime(2014, 4, 1, 19, 30, tzinfo=timezone.utc))]),
        ]
        # @formatter:on
        for year, quarter, period, number_of_maps, expected in cases:
            with self.subTest(f"year: {year}, quarter: {quarter}, period: {period}, num_maps: {number_of_maps}"):
                canonical_map_period = create_canonical_map_period(year=year, quarter=quarter, map_period=period,
                                                                   number_of_maps=number_of_maps)
                date_range = canonical_map_period.calculate_date_ranges()

                self.assertEqual(expected, date_range)
