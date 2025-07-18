import json
from dataclasses import dataclass
from typing import Optional

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


@dataclass
class Configuration:
    canonical_map_period: CanonicalMapPeriod
    instrument: str
    spin_phase: str
    reference_frame: str
    survival_corrected: bool
    coordinate_system: str
    pixelation_scheme: str
    pixel_parameter: int
    map_data_type: str
    lo_species: Optional[str] = None

    @classmethod
    def from_json(cls, config_path: Path):
        with open(str(config_path), 'r') as f:
            config = json.load(f)
            schema = config_schema.schema
            validate(config, schema)
            config["canonical_map_period"] = CanonicalMapPeriod(**config["canonical_map_period"])
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
        instrument_split = self.instrument.split(' ')
        instrument = instrument_split[0]
        if len(instrument_split) > 1:
            sensor = instrument_split[1]
        else:
            sensor = ""
        instrument = MappableInstrumentShortName[instrument.upper()]

        return MapDescriptor(
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
