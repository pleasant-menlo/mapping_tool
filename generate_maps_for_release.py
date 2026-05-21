import logging
from datetime import datetime, timezone
from pathlib import Path

from mapping_tool.dependency_collector import DependencyCollector
from imap_processing.ena_maps.utils.naming import MapDescriptor
from imap_data_access.processing_input import ScienceFilePath

from mapping_tool.generate_map import generate_map
import imap_data_access

L3_MAPS_TO_GENERATE = [
    "ulc-ena-h-hf-nsp-full-hae-4deg-6mo",
    "ulc-ena-h-hf-nsp-full-hae-6deg-6mo",
    "u90-ena-h-sf-sp-full-hae-4deg-6mo",
    "u90-ena-h-sf-sp-full-hae-6deg-6mo",
    "u45-ena-h-sf-sp-full-hae-4deg-6mo",
    "u45-ena-h-sf-sp-full-hae-6deg-6mo",
    "ulc-spx-h-hf-sp-full-hae-4deg-6mo",
    "u90-spx-h-hf-sp-full-hae-4deg-6mo",
    "u45-spx-h-hf-sp-full-hae-4deg-6mo",
    "ulc-spx-h-hf-sp-full-hae-6deg-6mo",
    "u90-spx-h-hf-sp-full-hae-6deg-6mo",
    "u45-spx-h-hf-sp-full-hae-6deg-6mo",
]
time_range = [(datetime(2025, 11, 15, tzinfo=timezone.utc), datetime(2026, 5, 15, tzinfo=timezone.utc))]

if __name__ == "__main__":
    # logging.basicConfig(force=True, level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    data_dir = Path(__file__).parent / "data_release_data_dir"
    imap_data_access.config["DATA_DIR"] = data_dir

    generated_maps = {}

    for file_path in data_dir.rglob("*_v000.cdf"):
        dependency_collector = DependencyCollector(
            descriptor=MapDescriptor.from_string(ScienceFilePath(file_path.name).descriptor),
            time_ranges=time_range,
            include_predicted_ephemeris=True,
        )
        generated_maps[dependency_collector] = file_path

    for map_descriptor in L3_MAPS_TO_GENERATE:
        dependencies = DependencyCollector(
            descriptor=MapDescriptor.from_string(map_descriptor),
            time_ranges=time_range,
            include_predicted_ephemeris=True,
        )

        generate_map(dependencies, generated_maps)
