from __future__ import annotations
import enum
import re
from datetime import timedelta, datetime, timezone
from dataclasses import dataclass
from typing import Optional

from imap_processing.ena_maps.utils.naming import MapDescriptor, MappableInstrumentShortName

from pathlib import Path

from imap_processing.spice.geometry import SpiceFrame
from jsonschema import validate

import yaml
from yaml import SafeLoader

from mapping_tool import config_schema
from mapping_tool.mapping_tool_descriptor import MappingToolDescriptor, CustomSpiceFrame


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


class DataLevel(enum.Enum):
    L2 = 'l2'
    L3 = 'l3'
    NA = 'no applicable level'


class MapSettings:
    descriptor: MapDescriptor
    spice_frame: str
    start_date: datetime
    end_date: datetime


@dataclass
class TimeRange:
    start: datetime
    end: datetime


def parse_yaml_no_datetime_conversion(text: str) -> dict:
    class NoDatesSafeLoader(SafeLoader):
        yaml_implicit_resolvers = {}

    for ch, resolvers in list(SafeLoader.yaml_implicit_resolvers.items()):
        NoDatesSafeLoader.yaml_implicit_resolvers[ch] = [(tag, regexp) for tag, regexp in resolvers
                                                         if tag != "tag:yaml.org,2002:timestamp"
                                                         ]

    return yaml.load(text, Loader=NoDatesSafeLoader)

@dataclass(frozen=True)
class Configuration:
    raw_config: str
    instrument: str
    spin_phase: str
    reference_frame_type: str
    survival_corrected: bool
    spice_frame_name: str
    pixelation_scheme: str
    pixel_parameter: int
    map_data_type: str
    canonical_map_period: Optional[CanonicalMapPeriod] = None
    time_ranges: Optional[list[TimeRange]] = None
    kernel_path: Path = None
    lo_species: Optional[str] = None
    output_directory: Optional[Path] = Path('.')
    quantity_suffix: str = ""


    @classmethod
    def from_file(cls, config_path: Path) -> Configuration:
        if config_path.suffix not in ['.json', '.yaml']:
            raise ValueError(f'Configuration file {config_path} must have .json or .yaml extension')
        with open(str(config_path), 'r') as f:
            raw_text = f.read()
            return cls.parse_config(raw_text)

    @classmethod
    def parse_config(cls, config_text: str) -> Configuration:
        config = parse_yaml_no_datetime_conversion(config_text)

        raw_yaml = yaml.dump(yaml.safe_load(config_text))

        schema = config_schema.schema
        validate(config, schema)

        if "time_ranges" in config:
            time_ranges = []
            for time_range in config["time_ranges"]:
                start = datetime.fromisoformat(time_range["start"])
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)

                end = datetime.fromisoformat(time_range["end"])
                if end.tzinfo is None:
                    end = end.replace(tzinfo=timezone.utc)

                time_ranges.append(TimeRange(start, end))

            config["time_ranges"] = time_ranges
        else:
            canonical_map_period = CanonicalMapPeriod(**config["canonical_map_period"])
            config["canonical_map_period"] = canonical_map_period

        if config.get("output_directory") is not None:
            config["output_directory"] = Path(config["output_directory"])
        if config.get("kernel_path") is not None:
            config["kernel_path"] = Path(config["kernel_path"])
        return cls(raw_yaml, **config)

    @classmethod
    def parse_instrument(cls, instrument_sensor: str):
        instrument_split = instrument_sensor.split(' ')
        instrument = instrument_split[0]
        if len(instrument_split) > 1:
            sensor = instrument_split[1]
        else:
            sensor = ""
        instrument = MappableInstrumentShortName[instrument.upper()]

        return instrument, sensor

    def get_map_descriptor(self) -> MappingToolDescriptor:
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
        duration = "0mo" if self.canonical_map_period is None else str(self.canonical_map_period.map_period) + "mo"

        instrument, sensor = self.parse_instrument(self.instrument)

        if self.kernel_path is None:
            try:
                spice_frame = MapDescriptor.get_map_coord_frame(self.spice_frame_name)
            except NotImplementedError:
                try:
                    spice_frame = SpiceFrame[self.spice_frame_name]
                except KeyError:
                    raise ValueError(f'Unknown Spice Frame {self.spice_frame_name} with no custom kernel path provided')
        else:
            spice_frame = CustomSpiceFrame(name=self.spice_frame_name)

        coordinate_system = re.sub(r"[^A-Za-z0-9]", "", self.spice_frame_name).lower()

        return MappingToolDescriptor(
            frame_descriptor=frame_descriptors[self.reference_frame_type],
            resolution_str=resolution,
            duration=duration,
            instrument=instrument,
            sensor=sensor,
            principal_data=principal_data[self.map_data_type],
            quantity_suffix=self.quantity_suffix,
            species=self.lo_species or 'h',
            survival_corrected="sp" if self.survival_corrected else "nsp",
            spin_phase=spin_phase[self.spin_phase.lower()],
            coordinate_system=coordinate_system,
            spice_frame=spice_frame,
            kernel_path=self.kernel_path
        )

    def get_map_date_ranges(self) -> list[tuple[datetime, datetime]]:
        if self.canonical_map_period is not None:
            return self.canonical_map_period.calculate_date_ranges()
        else:
            self.time_ranges.sort(key=lambda time_range: time_range.start)
            return [(time_range.start, time_range.end) for time_range in self.time_ranges]



