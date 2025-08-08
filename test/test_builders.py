from pathlib import Path
from typing import Dict, Optional, Literal

from imap_processing.ena_maps.utils.naming import MappableInstrumentShortName, MapDescriptor
from imap_processing.spice.geometry import SpiceFrame

from mapping_tool.configuration import Configuration, CanonicalMapPeriod
from mapping_tool.mapping_tool_descriptor import MappingToolDescriptor


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
        quantity_suffix: str = "CUSTOM",
        spice_frame: SpiceFrame = SpiceFrame.ECLIPJ2000
):
    return MappingToolDescriptor(
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
        quantity_suffix=quantity_suffix,
        spice_frame=spice_frame,
    )


def create_l2_map_descriptor(
        frame_descriptor: Literal["sf", "hf", "hk"] = "sf",
        resolution_str: str = "2deg",
        duration: str = "6mo",
        instrument: MappableInstrumentShortName = MappableInstrumentShortName["HI"],
        sensor: str = "90",
        species: str = "h",
        spin_phase: str = "ram",
        coordinate_system: str = "hae"
):
    return create_map_descriptor(
        frame_descriptor=frame_descriptor,
        resolution_str=resolution_str,
        duration=duration,
        instrument=instrument,
        sensor=sensor,
        species=species,
        spin_phase=spin_phase,
        coordinate_system=coordinate_system,
        survival_corrected="nsp"
    )


def create_canonical_map_period(year=2025, quarter=1, map_period=6, number_of_maps=1):
    return CanonicalMapPeriod(year=year, quarter=quarter, map_period=map_period, number_of_maps=number_of_maps)


def create_configuration(
        canonical_map_period: CanonicalMapPeriod = None,
        instrument: Optional[str] = None,
        spin_phase: str = "Ram",
        reference_frame: str = "spacecraft",
        survival_corrected: bool = False,
        spice_frame_name: str = "ECLIPJ2000",
        pixelation_scheme: str = "square",
        pixel_parameter: int = 4,
        map_data_type: str = "ENA Intensity",
        lo_species: str = "h",
        output_directory: Path = Path(".")
):
    canonical_period = canonical_map_period if canonical_map_period is not None else create_canonical_map_period()
    instrument = instrument or "Hi 90"
    return Configuration(
        canonical_map_period=canonical_period,
        instrument=instrument,
        spin_phase=spin_phase,
        reference_frame=reference_frame,
        survival_corrected=survival_corrected,
        spice_frame_name=spice_frame_name,
        pixelation_scheme=pixelation_scheme,
        pixel_parameter=pixel_parameter,
        map_data_type=map_data_type,
        lo_species=lo_species,
        output_directory=output_directory
    )


def create_config_dict(args: Dict):
    config = {
        "canonical_map_period": {
            "year": 2025,
            "quarter": 1,
            "map_period": 6,
            "number_of_maps": 1
        },
        "instrument": "Hi 90",
        "spin_phase": "Ram",
        "reference_frame": "spacecraft",
        "survival_corrected": True,
        "spice_frame_name": "ECLIPJ2000",
        "pixelation_scheme": "square",
        "pixel_parameter": 2,
        "map_data_type": "ENA Intensity",
        "lo_species": "h"
    }
    config.update(args)
    return config
