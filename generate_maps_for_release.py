import logging
from datetime import datetime, timezone
from pathlib import Path

from mapping_tool.dependency_collector import DependencyCollector
from imap_processing.ena_maps.utils.naming import MapDescriptor

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

if __name__ == "__main__":
    # logging.basicConfig(force=True, level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    imap_data_access.config["DATA_DIR"] = Path(__file__).parent / "data_release_data_dir"

    generated_maps = {}
    for map_descriptor in L3_MAPS_TO_GENERATE:
        dependencies = DependencyCollector(
            descriptor=MapDescriptor.from_string(map_descriptor),
            time_ranges=[(datetime(2025, 11, 15, tzinfo=timezone.utc), datetime(2026, 5, 15, tzinfo=timezone.utc))],
            include_predicted_ephemeris=True,
        )

        generate_map(dependencies, generated_maps)
