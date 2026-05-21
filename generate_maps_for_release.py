import shutil
from datetime import datetime, timezone
from pathlib import Path

from imap_data_access import ProcessingInputCollection
from imap_l3_processing.hi.hi_processor import HiProcessor
from imap_l3_processing.models import InputMetadata

from mapping_tool.dependency_collector import DependencyCollector
from imap_processing.ena_maps.utils.naming import MapDescriptor
from imap_data_access.processing_input import ScienceFilePath, ScienceInput

from mapping_tool.generate_map import generate_map
import imap_data_access

MAPS_TO_GENERATE = [
    {
        "start": datetime(2025, 11, 15, tzinfo=timezone.utc),
        "end": datetime(2026, 5, 15, tzinfo=timezone.utc),
        "descriptors": [
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
    },
    {
        "start": datetime(2025, 12, 3),
        "end": datetime(2026, 5, 17),
        "descriptors": [
            "h45-ena-h-hf-nsp-full-hae-6deg-6mo",
            "h45-ena-h-hf-nsp-full-hae-4deg-6mo",
            "h45-spx-h-hf-sp-full-hae-6deg-6mo",
            "h45-spx-h-hf-sp-full-hae-4deg-6mo",

            # not in release but needed for combined maps
            'h45-ena-h-hf-sp-ram-hae-6deg-6mo',
            'h45-ena-h-hf-sp-anti-hae-6deg-6mo',
            'h45-ena-h-hf-sp-ram-hae-4deg-6mo',
            'h45-ena-h-hf-sp-anti-hae-4deg-6mo',
        ]
    },
    {
        "start": datetime(2025, 11, 16),
        "end": datetime(2026, 5, 17),
        "descriptors": [
            "h90-ena-h-hf-nsp-full-hae-6deg-6mo",
            "h90-ena-h-hf-nsp-full-hae-4deg-6mo",
            "h90-spx-h-hf-sp-full-hae-6deg-6mo",
            "h90-spx-h-hf-sp-full-hae-4deg-6mo",

            # not in release but needed for combined maps
            'h90-ena-h-hf-sp-ram-hae-6deg-6mo',
            'h90-ena-h-hf-sp-anti-hae-6deg-6mo',
            'h90-ena-h-hf-sp-ram-hae-4deg-6mo',
            'h90-ena-h-hf-sp-anti-hae-4deg-6mo',
        ]
    }
]


COMBINED_MAPS_TO_GENERATE = [
    {
        'descriptor': 'hic-ena-h-hf-sp-full-hae-6deg-6mo',
        'deps': [
            'h45-ena-h-hf-sp-ram-hae-6deg-6mo',
            'h45-ena-h-hf-sp-anti-hae-6deg-6mo',
            'h90-ena-h-hf-sp-ram-hae-6deg-6mo',
            'h90-ena-h-hf-sp-anti-hae-6deg-6mo',
        ]
    },
    {
        'descriptor': 'hic-ena-h-hf-sp-full-hae-4deg-6mo',
        'deps': [
            'h45-ena-h-hf-sp-ram-hae-4deg-6mo',
            'h45-ena-h-hf-sp-anti-hae-4deg-6mo',
            'h90-ena-h-hf-sp-ram-hae-4deg-6mo',
            'h90-ena-h-hf-sp-anti-hae-4deg-6mo',
        ]
    }
]

if __name__ == "__main__":
    data_dir = Path(__file__).parent / "data_release_data_dir"
    imap_data_access.config["DATA_DIR"] = data_dir

    generated_maps = {}

    for file_path in data_dir.rglob("*_v000.cdf"):
        descriptor_str = ScienceFilePath(file_path.name).descriptor
        generated_maps[descriptor_str] = file_path

    for map_set_to_generate in MAPS_TO_GENERATE:
        time_range = (
            map_set_to_generate["start"].replace(tzinfo=timezone.utc),
            map_set_to_generate["end"].replace(tzinfo=timezone.utc)
        )

        for map_descriptor in map_set_to_generate["descriptors"]:
            dependencies = DependencyCollector(
                descriptor=MapDescriptor.from_string(map_descriptor),
                time_ranges=[time_range],
                include_predicted_ephemeris=True,
            )

            generate_map(dependencies, generated_maps)

    for combined_map in COMBINED_MAPS_TO_GENERATE:
        combined_descriptor = str(combined_map['descriptor'])

        if combined_descriptor not in generated_maps:
            dependencies = ProcessingInputCollection(*[ScienceInput(generated_maps[dep].name) for dep in combined_map['deps']])
            combined_metadata = InputMetadata(
                instrument='hi',
                data_level='l3',
                start_date=datetime(2025, 11, 16),
                end_date=datetime(2026, 5, 17),
                version='v000',
                descriptor=combined_map['descriptor'],
            )
            [combined_output_path] = HiProcessor(dependencies, combined_metadata).process()
            generated_maps[combined_descriptor] = combined_output_path

        spx_descriptor = combined_descriptor.replace("-ena-", "-spx-")
        if spx_descriptor not in generated_maps:
            spx_dependencies = ProcessingInputCollection(ScienceInput(combined_output_path.name))
            spx_metadata = InputMetadata(
                instrument='hi',
                data_level='l3',
                start_date=datetime(2025, 11, 16),
                end_date=datetime(2026, 5, 17),
                version='v000',
                descriptor=spx_descriptor,
            )
            [spx_output_path] = HiProcessor(spx_dependencies, spx_metadata).process()
            generated_maps[spx_descriptor] = spx_output_path

    # MAPS_TO_RELEASE = [
    #     "h45-ena-h-hf-nsp-full-hae-6deg-6mo",
    #     "h45-ena-h-hf-nsp-ram-hae-6deg-6mo",
    #     "h45-ena-h-hf-nsp-anti-hae-6deg-6mo",
    #     "h90-ena-h-hf-nsp-full-hae-6deg-6mo",
    #     "h90-ena-h-hf-nsp-ram-hae-6deg-6mo",
    #     "h90-ena-h-hf-nsp-anti-hae-6deg-6mo",
    #     "h45-ena-h-hf-nsp-full-hae-4deg-6mo",
    #     "h45-ena-h-hf-nsp-ram-hae-4deg-6mo",
    #     "h45-ena-h-hf-nsp-anti-hae-4deg-6mo",
    #     "h90-ena-h-hf-nsp-full-hae-4deg-6mo",
    #     "h90-ena-h-hf-nsp-ram-hae-4deg-6mo",
    #     "h90-ena-h-hf-nsp-anti-hae-4deg-6mo",
    #     "h90-ena-h-hf-sp-full-hae-6deg-6mo",
    #     "h45-ena-h-hf-sp-full-hae-6deg-6mo",
    #     "h90-ena-h-hf-sp-full-hae-4deg-6mo",
    #     "h45-ena-h-hf-sp-full-hae-4deg-6mo",
    #     "h45-spx-h-hf-sp-full-hae-6deg-6mo",
    #     "h90-spx-h-hf-sp-full-hae-6deg-6mo",
    #     "h45-spx-h-hf-sp-full-hae-4deg-6mo",
    #     "h90-spx-h-hf-sp-full-hae-4deg-6mo",
    #     "hic-ena-h-hf-sp-full-hae-6deg-6mo",
    #     "hic-ena-h-hf-sp-full-hae-4deg-6mo",
    #     "hic-spx-h-hf-sp-full-hae-6deg-6mo",
    #     "hic-spx-h-hf-sp-full-hae-4deg-6mo",
    #     "u90-ena-h-hf-nsp-full-hae-4deg-6mo",
    #     "u45-ena-h-hf-nsp-full-hae-4deg-6mo",
    #     "u90-ena-h-hf-nsp-full-hae-6deg-6mo",
    #     "u45-ena-h-hf-nsp-full-hae-6deg-6mo",
    #     "u90-ena-h-sf-nsp-full-hae-4deg-6mo",
    #     "u45-ena-h-sf-nsp-full-hae-4deg-6mo",
    #     "u90-ena-h-sf-nsp-full-hae-6deg-6mo",
    #     "u45-ena-h-sf-nsp-full-hae-6deg-6mo",
    #     "ulc-ena-h-hf-sp-full-hae-4deg-6mo",
    #     "ulc-ena-h-hf-sp-full-hae-6deg-6mo",
    #     "ulc-ena-h-hf-nsp-full-hae-4deg-6mo",
    #     "ulc-ena-h-hf-nsp-full-hae-6deg-6mo",
    #     "u90-ena-h-hf-sp-full-hae-4deg-6mo",
    #     "u90-ena-h-sf-sp-full-hae-4deg-6mo",
    #     "u90-ena-h-hf-sp-full-hae-6deg-6mo",
    #     "u90-ena-h-sf-sp-full-hae-6deg-6mo",
    #     "u45-ena-h-hf-sp-full-hae-4deg-6mo",
    #     "u45-ena-h-sf-sp-full-hae-4deg-6mo",
    #     "u45-ena-h-hf-sp-full-hae-6deg-6mo",
    #     "u45-ena-h-sf-sp-full-hae-6deg-6mo",
    #     "ulc-spx-h-hf-sp-full-hae-4deg-6mo",
    #     "u90-spx-h-hf-sp-full-hae-4deg-6mo",
    #     "u45-spx-h-hf-sp-full-hae-4deg-6mo",
    #     "ulc-spx-h-hf-sp-full-hae-6deg-6mo",
    #     "u90-spx-h-hf-sp-full-hae-6deg-6mo",
    #     "u45-spx-h-hf-sp-full-hae-6deg-6mo",
    # ]

    # release_path = Path(__file__).parent / "imap_maps_initial_release"
    # for release_descriptor in MAPS_TO_RELEASE:
    #     generated_path = generated_maps[release_descriptor]
    #     science_file_path = ScienceFilePath(generated_path.name)
    #
    #     output_dir = release_path / science_file_path.instrument / science_file_path.data_level
    #     output_dir.mkdir(parents=True, exist_ok=True)
    #     shutil.copy(generated_path, output_dir)
