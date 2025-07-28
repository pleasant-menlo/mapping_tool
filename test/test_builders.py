from typing import Dict, Optional, Literal

from imap_processing.ena_maps.utils.naming import MappableInstrumentShortName, MapDescriptor

from mapping_tool.configuration import Configuration, CanonicalMapPeriod


def create_map_descriptor(
        frame_descriptor: Literal["sf", "hf", "hk"] = "sf",
        resolution_str: str = "2deg",
        duration: str = "6mo",
        instrument: MappableInstrumentShortName = MappableInstrumentShortName["HI"],
        sensor: str = "90",
        principal_data: str = "ena",
        species: str = "h",
        survival_corrected: str = "sp",
        spin_phase: str = "ram",
        coordinate_system: str = "hae",
):
    return MapDescriptor(
        frame_descriptor=frame_descriptor,
        resolution_str=resolution_str,
        duration=duration,
        instrument=instrument,
        sensor=sensor,
        principal_data=principal_data,
        species=species,
        survival_corrected=survival_corrected,
        spin_phase=spin_phase,
        coordinate_system=coordinate_system,
    )


def create_canonical_map_period(year=2025, quarter=1, map_period=6, number_of_maps=1):
    return CanonicalMapPeriod(year=year, quarter=quarter, map_period=map_period, number_of_maps=number_of_maps)


def create_configuration(
        canonical_map_period: CanonicalMapPeriod = None,
        instruments: Optional[list[str]] = None,
        spin_phase: str = "Ram",
        reference_frame: str = "spacecraft",
        survival_corrected: bool = False,
        coordinate_system: str = "hae",
        pixelation_scheme: str = "square",
        pixel_parameter: int = 4,
        map_data_type: str = "ENA Intensity",
        lo_species: str = "h",
):
    canonical_period = canonical_map_period if canonical_map_period is not None else create_canonical_map_period()
    instruments = instruments or ["Hi 90"]
    return Configuration(
        canonical_map_period=canonical_period,
        instruments=instruments,
        spin_phase=spin_phase,
        reference_frame=reference_frame,
        survival_corrected=survival_corrected,
        coordinate_system=coordinate_system,
        pixelation_scheme=pixelation_scheme,
        pixel_parameter=pixel_parameter,
        map_data_type=map_data_type,
        lo_species=lo_species,
    )


def create_config_dict(args: Dict):
    config = {
        "canonical_map_period": {
            "year": 2025,
            "quarter": 1,
            "map_period": 6,
            "number_of_maps": 1
        },
        "instruments": ["Hi 90"],
        "spin_phase": "Ram",
        "reference_frame": "spacecraft",
        "survival_corrected": True,
        "coordinate_system": "hae",
        "pixelation_scheme": "square",
        "pixel_parameter": 2,
        "map_data_type": "ENA Intensity",
        "lo_species": "h"
    }
    config.update(args)
    return config
