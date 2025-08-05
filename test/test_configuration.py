import datetime
from datetime import datetime, timezone
from pathlib import Path

import jsonschema.exceptions
from typing import Dict
from unittest import TestCase
from unittest.mock import patch

from mapping_tool import config_schema
from mapping_tool.configuration import Configuration, CanonicalMapPeriod, DataLevel
from test.test_builders import create_configuration, create_config_dict, create_canonical_map_period
from test.test_helpers import get_example_config_path
from imap_processing.ena_maps.utils.naming import MapDescriptor, MappableInstrumentShortName


class TestConfiguration(TestCase):
    def test_from_file(self):
        for extension in ["json", "yaml"]:
            with self.subTest(extension):
                example_config_path = get_example_config_path() / f"test_l2_config.{extension}"
                config: Configuration = Configuration.from_file(example_config_path)

                expected_config: Configuration = Configuration(
                    canonical_map_period=CanonicalMapPeriod(year=2025, quarter=1, map_period=6, number_of_maps=1),
                    instruments=["Hi 90"],
                    spin_phase="Ram",
                    reference_frame="spacecraft",
                    survival_corrected=True,
                    coordinate_system="hae",
                    pixelation_scheme="square",
                    pixel_parameter=2,
                    map_data_type="ENA Intensity",
                    lo_species=None,
                    output_directory=Path('.'),
                    quantity_suffix=""
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
                    canonical_map_period=CanonicalMapPeriod(year=2025, quarter=1, map_period=6, number_of_maps=1),
                    instruments=["Hi 90", 'Ultra 45'],
                    spin_phase="Ram",
                    reference_frame="spacecraft",
                    survival_corrected=True,
                    coordinate_system="hnu",
                    pixelation_scheme="square",
                    pixel_parameter=2,
                    map_data_type="ENA Intensity",
                    lo_species="h",
                    output_directory=Path('path/to/output'),
                    quantity_suffix="custom"
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
                    "instruments": ["Hi 90"],
                    "spin_phase": "Ram",
                    "reference_frame": "spacecraft",
                    "survival_corrected": True,
                    "coordinate_system": "hae",
                    "pixelation_scheme": "square",
                    "pixel_parameter": 2,
                    "map_data_type": "ENA Intensity",
                }

                mock_validate.assert_called_with(expected_config, config_schema.schema)

    @patch("mapping_tool.configuration.json.load")
    def test_from_file_fails_validation_with_invalid_config(self, mock_load):
        validation_error_cases = [
            ("invalid instrument", {"instruments": "90"}),
            ("invalid spin phase", {"spin_phase": "none"}),
            ("invalid reference frame", {"reference_frame": "spacecraft kinematic"}),
            ("invalid survival probability corrected", {"survival_corrected": "YES"}),
            ("invalid map_data_type", {"map_data_type": "Directions"})
        ]
        for name, case in validation_error_cases:
            with self.subTest(name):
                mock_load.return_value = create_config_dict(case)
                with self.assertRaises(jsonschema.exceptions.ValidationError):
                    Configuration.from_file(get_example_config_path() / "test_l2_config.json")

    def test_get_map_descriptors_returns_descriptors_for_each_instrument(self):
        config: Configuration = Configuration(
            canonical_map_period=CanonicalMapPeriod(year=2025, quarter=1, map_period=6, number_of_maps=2),
            instruments=["hi 90", "Lo"],
            spin_phase="Ram",
            reference_frame="spacecraft",
            survival_corrected=True,
            coordinate_system="hae",
            pixelation_scheme="square",
            pixel_parameter=2,
            map_data_type="ENA Intensity",
            lo_species="h"
        )

        expected_descriptors_and_levels: list[tuple[MapDescriptor, DataLevel]] = ([
            (MapDescriptor(
                frame_descriptor="sf",
                resolution_str="2deg",
                duration="6mo",
                instrument=MappableInstrumentShortName["HI"],
                sensor="90",
                principal_data="ena",
                species="h",
                survival_corrected="sp",
                spin_phase="ram",
                coordinate_system="hae"
            ), DataLevel.L3),
            (MapDescriptor(
                frame_descriptor="sf",
                resolution_str="2deg",
                duration="6mo",
                instrument=MappableInstrumentShortName["LO"],
                sensor="",
                principal_data="ena",
                species="h",
                survival_corrected="sp",
                spin_phase="ram",
                coordinate_system="hae"
            ), DataLevel.L3)
        ])

        descriptors_and_levels = config.get_map_descriptors()

        self.assertEqual(expected_descriptors_and_levels, descriptors_and_levels)

    def test_get_map_descriptors_frame_descriptors(self):
        cases = [
            ("spacecraft", "sf"),
            ("heliospheric", "hf"),
            ("heliospheric kinematic", "hk"),
        ]

        for case, expected in cases:
            with self.subTest(f"{case}, {expected}"):
                input_config = create_configuration(reference_frame=case)
                [(descriptor, data_level)] = input_config.get_map_descriptors()
                self.assertEqual(expected, descriptor.frame_descriptor)
                self.assertEqual(DataLevel.L2, data_level)

    def test_get_map_descriptors_principal_data(self):
        cases = [
            ("ENA Intensity", "ena", DataLevel.L2),
            ("Spectral Index", "spx", DataLevel.L3)
        ]

        for case, expected_descriptor, expected_data_level in cases:
            with self.subTest(f"{case}, {expected_descriptor}"):
                input_config = create_configuration(map_data_type=case)
                [(descriptor, data_level)] = input_config.get_map_descriptors()
                self.assertEqual(expected_descriptor, descriptor.principal_data)
                self.assertEqual(expected_data_level, data_level)

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
                [(descriptor, _)] = input_config.get_map_descriptors()
                self.assertEqual(expected, descriptor.spin_phase)

    def test_get_map_descriptors_coordinate_system(self):
        cases = [
            ("HAE", "hae"),
            ("hae", "hae")
        ]

        for case, expected in cases:
            with self.subTest(f"{case}, {expected}"):
                input_config = create_configuration(coordinate_system=case)
                [(descriptor, data_level)] = input_config.get_map_descriptors()
                self.assertEqual(expected, descriptor.coordinate_system)
                self.assertEqual(DataLevel.L2, data_level)

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
                [(descriptor, data_level)] = input_config.get_map_descriptors()
                self.assertEqual(expected, descriptor.resolution_str)
                self.assertEqual(DataLevel.L2, data_level)

    def test_get_map_descriptors_instrument_and_sensor(self):
        cases = [
            (["hi 45"], MappableInstrumentShortName.HI, "45", "h45", DataLevel.L2),
            (["Hi 90"], MappableInstrumentShortName.HI, "90", "h90", DataLevel.L2),
            (["hi combined"], MappableInstrumentShortName.HI, "combined", "hic", DataLevel.L3),
            (["Ultra 45"], MappableInstrumentShortName.ULTRA, "45", "u45", DataLevel.L2),
            (["ultra 90"], MappableInstrumentShortName.ULTRA, "90", "u90", DataLevel.L2),
            (["Ultra combined"], MappableInstrumentShortName.ULTRA, "combined", "ulc", DataLevel.L3),
            (["Lo"], MappableInstrumentShortName.LO, "", "ilo", DataLevel.L2),
            (["lo"], MappableInstrumentShortName.LO, "", "ilo", DataLevel.L2),
            (["GLOWS"], MappableInstrumentShortName.GLOWS, "", "glx", DataLevel.NA),
            (["glows"], MappableInstrumentShortName.GLOWS, "", "glx", DataLevel.NA),
            (["IDEX"], MappableInstrumentShortName.IDEX, "", "idx", DataLevel.L2),
            (["idex"], MappableInstrumentShortName.IDEX, "", "idx", DataLevel.L2),
        ]
        for case, instrument, sensor, instrument_descriptor, expected_data_level in cases:
            with self.subTest(f"{case}, {instrument}, {sensor}"):
                input_config = create_configuration(instruments=case)
                [(descriptor, data_level)] = input_config.get_map_descriptors()
                self.assertEqual(instrument, descriptor.instrument)
                self.assertEqual(sensor, descriptor.sensor)
                self.assertEqual(instrument_descriptor, descriptor.instrument_descriptor)
                self.assertEqual(expected_data_level, data_level)

    def test_get_data_level(self):
        cases = [
            ("ENA Intensity", True, ["Hi 45"], DataLevel.L3),
            ("ENA Intensity", False, ["Hi 45"], DataLevel.L2),
            ("ENA Intensity", False, ["Hi combined"], DataLevel.L3),
            ("Spectral Index", False, ["Hi 90"], DataLevel.L3),
            ("Spectral Index", True, ["Hi 90"], DataLevel.L3),
            ("Spectral Index", False, ["Lo"], DataLevel.L3),
            ("ENA Intensity", False, ["Lo"], DataLevel.L2),
        ]

        for product, sp, instrument, expected_data_level in cases:
            with self.subTest(f"{product}, {sp}, {instrument}"):
                input_config = create_configuration(instruments=instrument, survival_corrected=sp,
                                                    map_data_type=product)
                [(_, data_level)] = input_config.get_map_descriptors()
                self.assertEqual(expected_data_level, data_level)


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
