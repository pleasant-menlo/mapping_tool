from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from imap_processing.ena_maps.utils.naming import MapDescriptor, MappableInstrumentShortName
from imap_processing.spice.geometry import SpiceFrame


@dataclass
class CustomSpiceFrame:
    name: str


@dataclass
class MappingToolDescriptor(MapDescriptor):
    quantity_suffix: str = ""
    spectral_index_energy_step_range: str = ""
    spice_frame: SpiceFrame | CustomSpiceFrame = SpiceFrame.ECLIPJ2000
    kernel_path: Optional[Path] = None

    def __post_init__(self) -> None:
        self.duration = MapDescriptor.parse_map_duration(self.duration)
        self.instrument_descriptor = MapDescriptor.get_instrument_descriptor(
            self.instrument, self.sensor
        )

    def to_mapping_tool_string(self):
        return "-".join(
            [
                self.instrument_descriptor,
                self.principal_data + self.spectral_index_energy_step_range + self.quantity_suffix,
                self.species,
                self.frame_descriptor,
                self.survival_corrected,
                self.spin_phase,
                self.coordinate_system,
                self.resolution_str,
                "custom" if self.duration == "0mo" else str(self.duration),
                "mapper"
            ]
        )

    def to_l3_input_string(self):
        return "-".join(
            [
                self.instrument_descriptor,
                self.principal_data + self.spectral_index_energy_step_range + self.quantity_suffix,
                self.species,
                self.frame_descriptor,
                self.survival_corrected,
                self.spin_phase,
                self.coordinate_system,
                self.resolution_str,
                str(self.duration)
            ]
        )

    def get_glows_input_descriptors(self) -> list[str]:
        map_details = (self.instrument, self.sensor, self.frame_descriptor)
        match map_details:
            case (MappableInstrumentShortName.HI, "45" | "90" as sensor, _):
                return [f"survival-probability-hi-{sensor}"]
            case (MappableInstrumentShortName.HI, "combined", _):
                return ["survival-probability-hi-45", "survival-probability-hi-90"]
            case (MappableInstrumentShortName.ULTRA, _, "hf" | "sf" as frame):
                return [f"survival-probability-ul-{frame}"]
            case (MappableInstrumentShortName.LO, _, _):
                return [f"survival-probability-{self.instrument.name.lower()[:2]}"]
            case _:
                raise ValueError(f"Unsupported instrument, sensor, or frame descriptor for finding GLOWS SP dependencies: {map_details}")
