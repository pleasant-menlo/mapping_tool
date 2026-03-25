import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from spacepy.pycdf import CDF

import imap_data_access
from imap_l3_processing.utils import (
    furnish_spice_metakernel,
    get_spice_kernels_file_names,
    FurnishMetakernelOutput,
    SpiceKernelTypes,
)
from imap_processing.ena_maps.utils.naming import MappableInstrumentShortName, MapDescriptor
from imap_data_access.processing_input import AncillaryInput, ScienceInput
from imap_data_access.file_validation import AncillaryFilePath

from mapping_tool.mapping_tool_descriptor import MappingToolDescriptor

MAPPING_TOOL_KERNEL_TYPES = [
    SpiceKernelTypes.Leapseconds,
    SpiceKernelTypes.SpacecraftClock,
    SpiceKernelTypes.PointingAttitude,
    SpiceKernelTypes.IMAPFrames,
    SpiceKernelTypes.ScienceFrames,
    SpiceKernelTypes.PlanetaryEphemeris,
    SpiceKernelTypes.EphemerisReconstructed,
    SpiceKernelTypes.PlanetaryConstants,
]


class DependencyCollector:
    def __init__(self, descriptor: MappingToolDescriptor, time_ranges: list[tuple[datetime, datetime]],
                 ultra_energy_ranges: Optional[str] = None):
        self.descriptor = descriptor
        self.time_ranges = time_ranges
        self.start_date = min([start for start, _end in time_ranges])
        self.end_date = max([end for _start, end in time_ranges])
        self.ultra_energy_ranges = ultra_energy_ranges

    def get_pointing_sets(self) -> list[str]:
        pset_descriptors = self._map_instrument_pset_descriptors()
        assert len(pset_descriptors) > 0
        return self._find_psets_in_time_ranges( self._query_psets(pset_descriptors))

    def _map_instrument_pset_descriptors(self):
        map_instrument_pset_descriptors =[]
        if self.descriptor.instrument == MappableInstrumentShortName.HI:
            if self.descriptor.sensor in ["45", "combined"]:
                map_instrument_pset_descriptors.append(f"45sensor-pset")
            if self.descriptor.sensor in ["90", "combined"]:
                map_instrument_pset_descriptors.append(f"90sensor-pset")

        elif self.descriptor.instrument == MappableInstrumentShortName.LO:
            map_instrument_pset_descriptors.append("pset")

        elif self.descriptor.instrument == MappableInstrumentShortName.ULTRA:
            pset_string = "spacecraftpset" if self.descriptor.frame_descriptor == "sf" else "heliopset"
            if self.descriptor.sensor in ["45", "combined"]:
                map_instrument_pset_descriptors.append(f"45sensor-{pset_string}")
            if self.descriptor.sensor in ["90", "combined"]:
                map_instrument_pset_descriptors.append(f"90sensor-{pset_string}")
        return map_instrument_pset_descriptors

    def _query_psets(self, pset_descriptors: list[str]) -> list[dict]:
        query_results = []
        for pset_descriptor in pset_descriptors:
            query_results.extend(imap_data_access.query(instrument=self.descriptor.instrument.name.lower(),
                                                                                start_date=self.start_date.strftime("%Y%m%d"),
                                                                                end_date=self.end_date.strftime("%Y%m%d"),
                                                                                data_level="l1c",
                                                                                descriptor=pset_descriptor,
                                                                                version="latest"))
        return query_results

    def _find_psets_in_time_ranges(self, query_results: list[dict]) -> list[str]:
        psets = []
        for pset in query_results:
            pset_date = datetime.strptime(pset["start_date"], "%Y%m%d").replace(tzinfo=timezone.utc)
            if any(range_start <= pset_date <= range_end for range_start, range_end in self.time_ranges):
                psets.append(Path(pset['file_path']).name)
        return psets

    def get_survival_probability_dependencies(self, input_maps: list[Path]) -> list[ScienceInput]:
        hi_nsp_combined = (
                self.descriptor.instrument == MappableInstrumentShortName.HI
                and self.descriptor.sensor == 'combined'
                and self.descriptor.survival_corrected == 'nsp'
        )
        spectral_index = (
                'spx' in self.descriptor.principal_data
        )
        not_requiring_pointing_sets = hi_nsp_combined or spectral_index

        if not_requiring_pointing_sets:
            return []

        l1c_parent_names = set()
        for input_map in input_maps:
            l1c_parent_names.update(DependencyCollector._get_l1c_parents(input_map))

        return [*self.get_glows_dependencies(), *[ScienceInput(l1c) for l1c in l1c_parent_names]]

    def get_glows_dependencies(self) -> list[ScienceInput]:
        if self.descriptor.survival_corrected == "nsp":
            return []

        psets = imap_data_access.query(
            instrument='glows',
            descriptor=self.descriptor.get_descriptor_for_query("glows"),
            start_date=self.start_date.strftime("%Y%m%d"),
            end_date=self.end_date.strftime("%Y%m%d"),
            version="latest"
        )

        return [ScienceInput(Path(f["file_path"]).name) for f in psets]

    @staticmethod
    def _get_l1c_parents(input_map: Path) -> set[str]:
        with CDF(str(input_map)) as cdf:
            return set(parent for parent in cdf.attrs["Parents"] if "l1c" in parent)

    def furnish_spice_kernels(self) -> FurnishMetakernelOutput:
        return furnish_spice_metakernel(
            self.start_date.replace(tzinfo=None),
            self.end_date.replace(tzinfo=None),
            MAPPING_TOOL_KERNEL_TYPES,
        )

    def get_spice_kernel_names(self) -> list[str]:
        return [
            Path(name).name for name in get_spice_kernels_file_names(
                self.start_date.replace(tzinfo=None),
                self.end_date.replace(tzinfo=None),
                MAPPING_TOOL_KERNEL_TYPES,
            )
        ]

    def _filter_ancillary_dependencies(self, files: list[dict[str, str]]) -> list[
        dict[str, str]]:
        match self.descriptor:
            case MapDescriptor(instrument=MappableInstrumentShortName.HI, sensor="90", survival_corrected="nsp"):
                relevant_descriptors = ["90sensor-cal-prod", "90sensor-esa-energies", "90sensor-esa-eta-fit-factors"]
            case MapDescriptor(instrument=MappableInstrumentShortName.HI, sensor="45", survival_corrected="nsp"):
                relevant_descriptors = ["45sensor-cal-prod", "45sensor-esa-energies", "45sensor-esa-eta-fit-factors"]
            case MapDescriptor(instrument=MappableInstrumentShortName.LO, survival_corrected="nsp"):
                relevant_descriptors = ["esa-eta-fit-factors"]
            case MapDescriptor(instrument=MappableInstrumentShortName.ULTRA, principal_data="spx"):
                relevant_descriptors = ["ulc-spx-energy-ranges"]
            case MapDescriptor(instrument=MappableInstrumentShortName.ULTRA, principal_data="ena"):
                relevant_descriptors = ["l2-energy-bin-group-sizes"]
            case _:
                relevant_descriptors = []

        return [f for f in files if f['descriptor'] in relevant_descriptors]

    def get_ancillary_dependencies(self) -> list[AncillaryInput]:
        ancillaries = imap_data_access.query(table="ancillary", instrument=self.descriptor.instrument.name.lower())
        ancillaries = self._filter_ancillary_dependencies(ancillaries)

        def filter_files_by_highest_version(files: list):
            dates_to_files = {}
            valid_files = []
            for f in files:
                utc_start_time = datetime.strptime(f["start_date"], "%Y%m%d").replace(tzinfo=timezone.utc)
                if utc_start_time < self.end_date:
                    valid_files.append(f)

            for file in valid_files:
                file_descriptor = file["descriptor"]
                if file_descriptor not in dates_to_files:
                    dates_to_files[file_descriptor] = file
                else:
                    if dates_to_files[file_descriptor]["start_date"] == file["start_date"]:
                        if dates_to_files[file_descriptor]["version"] < file["version"]:
                            dates_to_files[file_descriptor] = file

                    if dates_to_files[file_descriptor]["start_date"] < file["start_date"]:
                        dates_to_files[file_descriptor] = file

            return dates_to_files.values()

        latest_ancillary_inputs = [AncillaryInput(Path(file['file_path']).name) for file in
                                   filter_files_by_highest_version(ancillaries)]

        if self.descriptor.instrument == MappableInstrumentShortName.ULTRA:
            if self.ultra_energy_ranges:
                ancillary_file_name = AncillaryFilePath("imap_ultra_l2-energy-bin-group-sizes_20250924_v000.csv")
                new_energy_ranges_path = ancillary_file_name.construct_path()
                os.makedirs(new_energy_ranges_path.parent, exist_ok=True)

                new_energy_ranges_path.write_text(self.ultra_energy_ranges.replace(" ", ""))

                latest_ancillary_inputs = [ancillary for ancillary in latest_ancillary_inputs if
                                           "l2-energy-bin-group-sizes" != ancillary.descriptor]
                latest_ancillary_inputs.append(AncillaryInput(new_energy_ranges_path.name))

        return latest_ancillary_inputs
