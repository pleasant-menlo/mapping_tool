from unittest import TestCase

from mapping_tool.configuration import Configuration, CanonicalMapPeriod
from test.test_builders import create_configuration
from test.test_helpers import get_example_config_path
from imap_processing.ena_maps.utils.naming import MapDescriptor, MappableInstrumentShortName


class TestConfiguration(TestCase):
    def test_from_json(self):
        example_config_path = get_example_config_path() / "example_config.json"
        config: Configuration = Configuration.from_json(example_config_path)

        expected_config: Configuration = Configuration(
            canonical_map_period=CanonicalMapPeriod(year=2025, quarter=1, map_period=6, number_of_maps=1),
            instrument="Hi 90",
            spin_phase="Ram",
            reference_frame="spacecraft",
            survival_corrected=True,
            coordinate_system="hae",
            pixelation_scheme="square",
            pixel_parameter=2,
            map_data_type="ENA Intensity",
            lo_species="h"
        )

        self.assertEqual(expected_config, config)

    def test_get_map_descriptor(self):
        config: Configuration = Configuration(
            canonical_map_period=CanonicalMapPeriod(year=2025, quarter=1, map_period=6, number_of_maps=1),
            instrument="hi 90",
            spin_phase="Ram",
            reference_frame="spacecraft",
            survival_corrected=True,
            coordinate_system="hae",
            pixelation_scheme="square",
            pixel_parameter=2,
            map_data_type="ENA Intensity",
            lo_species="h"
        )

        expected_descriptor: MapDescriptor = MapDescriptor(
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
        )

        descriptor = config.get_map_descriptors()

        self.assertEqual(expected_descriptor, descriptor)

    def test_get_map_descriptors_frame_descriptors(self):
        cases = [
            ("spacecraft", "sf"),
            ("heliospheric", "hf"),
            ("heliospheric kinematic", "hk"),
        ]

        for case, expected in cases:
            with self.subTest(f"{case}, {expected}"):
                input_config = create_configuration(reference_frame=case)
                descriptor = input_config.get_map_descriptors()
                self.assertEqual(expected, descriptor.frame_descriptor)

    def test_get_map_descriptors_principal_data(self):
        cases = [
            ("ENA Intensity", "ena"),
            ("Spectral Index", "spx")
        ]

        for case, expected in cases:
            with self.subTest(f"{case}, {expected}"):
                input_config = create_configuration(map_data_type=case)
                descriptor = input_config.get_map_descriptors()
                self.assertEqual(expected, descriptor.principal_data)

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
                descriptor = input_config.get_map_descriptors()
                self.assertEqual(expected, descriptor.spin_phase)

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
                descriptor = input_config.get_map_descriptors()
                self.assertEqual(expected, descriptor.resolution_str)

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
                descriptor = input_config.get_map_descriptors()
                self.assertEqual(instrument, descriptor.instrument)
                self.assertEqual(sensor, descriptor.sensor)
                self.assertEqual(instrument_descriptor, descriptor.instrument_descriptor)
