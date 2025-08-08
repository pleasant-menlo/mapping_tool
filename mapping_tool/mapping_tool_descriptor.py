from dataclasses import dataclass

from imap_processing.ena_maps.utils.naming import MapDescriptor
from imap_processing.spice.geometry import SpiceFrame


@dataclass
class MappingToolDescriptor(MapDescriptor):
    quantity_suffix: str = "CUSTOM"
    spice_frame: SpiceFrame = SpiceFrame.ECLIPJ2000

    def __post_init__(self) -> None:
        self.duration = MapDescriptor.parse_map_duration(self.duration)
        self.instrument_descriptor = MapDescriptor.get_instrument_descriptor(
            self.instrument, self.sensor
        )

    def to_mapping_tool_string(self):
        return "-".join(
            [
                self.instrument_descriptor,
                self.principal_data + self.quantity_suffix,
                self.species,
                self.frame_descriptor,
                self.survival_corrected,
                self.spin_phase,
                self.coordinate_system,
                self.resolution_str,
                str(self.duration),
            ]
        )
