from imap_processing.ena_maps.utils.naming import MapDescriptor


class MappingToolDescriptor(MapDescriptor):
    def __post_init__(self) -> None:
        self.duration = MapDescriptor.parse_map_duration(self.duration)
        self.instrument_descriptor = MapDescriptor.get_instrument_descriptor(
            self.instrument, self.sensor
        )
