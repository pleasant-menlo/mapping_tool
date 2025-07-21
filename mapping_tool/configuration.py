import datetime
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

    def calculate_date_range(self):
        one_year = datetime.timedelta(days=365.25)
        jan_1 = datetime.datetime(year=self.year, month=1, day=1)
        start = jan_1 + (one_year * (self.quarter - 1) / 4)
        end = start + (one_year * self.map_period / 12)
        return start, end


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


def get_pointing_sets(descriptor: MapDescriptor, start_date: datetime.datetime, end_date: datetime.datetime):
    map_instrument_pset_descriptors = []

    if descriptor.instrument == MappableInstrumentShortName.HI:
        if descriptor.sensor in ["45", "combined"]:
            map_instrument_pset_descriptors.append(f"45sensor-pset")
        if descriptor.sensor in ["90", "combined"]:
            map_instrument_pset_descriptors.append(f"90sensor-pset")

    elif descriptor.instrument == MappableInstrumentShortName.LO:
        map_instrument_pset_descriptors.append("pset")

    elif descriptor.instrument == MappableInstrumentShortName.ULTRA:
        pset_string = "spacecraftpset" if descriptor.frame_descriptor == "sf" else "heliopset"
        if descriptor.sensor in ["45", "combined"]:
            map_instrument_pset_descriptors.append(f"45sensor-{pset_string}")
        if descriptor.sensor in ["90", "combined"]:
            map_instrument_pset_descriptors.append(f"90sensor-{pset_string}")

    assert len(map_instrument_pset_descriptors) > 0
    instrument_for_query = descriptor.instrument.name.lower()
    start_date = start_date.strftime("%Y%m%d")
    end_date = end_date.strftime("%Y%m%d")

    files = []
    for pset_descriptor in map_instrument_pset_descriptors:
        files.extend(imap_data_access.query(instrument=instrument_for_query,
                                            start_date=start_date, end_date=end_date,
                                            data_level="l1c", descriptor=pset_descriptor))

    if descriptor.survival_corrected == "sp":
        files.extend(imap_data_access.query(instrument="glows",
                                            start_date=start_date,
                                            end_date=end_date,
                                            data_level="l3e",
                                            descriptor=f"survival-probability-{instrument_for_query[:2]}"))

    return [pset['file_path'] for pset in files]
