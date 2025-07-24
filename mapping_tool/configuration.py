from datetime import timedelta, datetime, timezone
import json
from dataclasses import dataclass
from typing import Optional

import imap_data_access
from imap_processing.ena_maps.utils.naming import MapDescriptor, MappableInstrumentShortName

from pathlib import Path

from jsonschema import validate

from mapping_tool import config_schema


@dataclass
class CanonicalMapPeriod:
    year: int
    quarter: int
    map_period: int
    number_of_maps: int

    def calculate_date_ranges(self) -> list[tuple[datetime, datetime]]:
        dates = []

        one_year = timedelta(days=365.25)
        jan_1 = datetime(year=self.year, month=1, day=1)
        start = jan_1 + (one_year * (self.quarter - 1) / 4)
        for _ in range(self.number_of_maps):
            end = start + (one_year * self.map_period / 12)
            dates.append((start.replace(tzinfo=timezone.utc), end.replace(tzinfo=timezone.utc)))
            start = end
        return dates


@dataclass
class Configuration:
    canonical_map_period: CanonicalMapPeriod
    instrument: list[str]
    spin_phase: str
    reference_frame: str
    survival_corrected: bool
    coordinate_system: str
    pixelation_scheme: str
    pixel_parameter: int
    map_data_type: str
    lo_species: Optional[str] = None
    output_directory: Optional[Path] = Path('.')

    @classmethod
    def from_json(cls, config_path: Path):
        with open(str(config_path), 'r') as f:
            config = json.load(f)
            schema = config_schema.schema
            validate(config, schema)
            config["canonical_map_period"] = CanonicalMapPeriod(**config["canonical_map_period"])
            config["output_directory"] = Path(config["output_directory"])
            return cls(**config)

    def get_map_descriptors(self) -> MapDescriptor:
        frame_descriptors = {
            "spacecraft": "sf",
            "heliospheric": "hf",
            "heliospheric kinematic": "hk",
        }

        principal_data = {
            "ENA Intensity": "ena",
            "Spectral Index": "spx"
        }

        spin_phase = {
            "ram": "ram",
            "anti-ram": "anti",
            "full spin": "full"
        }

        resolution = f"{self.pixel_parameter}deg" if self.pixelation_scheme.lower() == "square" else f"nside{self.pixel_parameter}"
        duration = str(self.canonical_map_period.map_period) + "mo"

        descriptors = []
        for instrument_sensor in self.instrument:
            instrument_split = instrument_sensor.split(' ')
            instrument = instrument_split[0]
            if len(instrument_split) > 1:
                sensor = instrument_split[1]
            else:
                sensor = ""
            instrument = MappableInstrumentShortName[instrument.upper()]

            descriptor = MapDescriptor(
                frame_descriptor=frame_descriptors[self.reference_frame],
                resolution_str=resolution,
                duration=duration,
                instrument=instrument,
                sensor=sensor,
                principal_data=principal_data[self.map_data_type],
                species=self.lo_species or 'h',
                survival_corrected="sp" if self.survival_corrected else "nsp",
                spin_phase=spin_phase[self.spin_phase.lower()],
                coordinate_system=self.coordinate_system.lower()
            )
            descriptors.append(descriptor)
        return descriptors
