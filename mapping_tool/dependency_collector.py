import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from spacepy.pycdf import CDF

import imap_data_access
import requests
from imap_processing.ena_maps.utils.naming import MappableInstrumentShortName, MapDescriptor
from imap_data_access.processing_input import AncillaryInput, ScienceInput
from imap_data_access.file_validation import AncillaryFilePath

from mapping_tool.mapping_tool_descriptor import MappingToolDescriptor


class DependencyCollector:
    def __init__(self, descriptor: MappingToolDescriptor, start_date: datetime, end_date: datetime,
                 ultra_energy_ranges: Optional[str] = None):
        self.descriptor = descriptor
        self.start_date = start_date
        self.end_date = end_date
        self.ultra_energy_ranges = ultra_energy_ranges

    def get_pointing_sets(self) -> list[str]:
        map_instrument_pset_descriptors = []

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

        assert len(map_instrument_pset_descriptors) > 0
        instrument_for_query = self.descriptor.instrument.name.lower()
        start_date = self.start_date.strftime("%Y%m%d")
        end_date = self.end_date.strftime("%Y%m%d")

        def filter_files_by_highest_version(files: list):
            dates_to_files = {}
            for file in files:
                if file["start_date"] not in dates_to_files or file["version"] > dates_to_files[file["start_date"]][
                    "version"]:
                    dates_to_files[file["start_date"]] = file
            return dates_to_files.values()

        files = []
        for pset_descriptor in map_instrument_pset_descriptors:
            files.extend(filter_files_by_highest_version(imap_data_access.query(instrument=instrument_for_query,
                                                                                start_date=start_date,
                                                                                end_date=end_date,
                                                                                data_level="l1c",
                                                                                descriptor=pset_descriptor)))

        return [Path(pset['file_path']).name for pset in files]

    def get_survival_probability_dependencies(self, input_maps: list[Path]) -> list[ScienceInput]:
        if self.descriptor.survival_corrected == "nsp":
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

    def collect_spice_kernels(self) -> list[str]:
        file_names = []
        auth_headers = {"Authorization": f"Bearer {imap_data_access.config['ACCESS_TOKEN']}"}
        for kernel_type in ["leapseconds", "spacecraft_clock", "pointing_attitude", "imap_frames", "science_frames",
                            "planetary_ephemeris", "ephemeris_reconstructed", "planetary_constants"]:
            response = requests.get(
                imap_data_access.config["DATA_ACCESS_URL"] + f"/spice-query?type={kernel_type}&start_time=0",
                headers=auth_headers
            )
            response.raise_for_status()
            file_json = response.json()
            for spice_file in file_json:
                spice_start_date = datetime.strptime(spice_file["min_date_datetime"], "%Y-%m-%d, %H:%M:%S")
                spice_start_date = spice_start_date.replace(tzinfo=timezone.utc)
                spice_end_date = datetime.strptime(spice_file["max_date_datetime"], "%Y-%m-%d, %H:%M:%S")
                spice_end_date = spice_end_date.replace(tzinfo=timezone.utc)
                if spice_start_date <= self.end_date and self.start_date < spice_end_date:
                    file_names.append(Path(spice_file["file_name"]).name)
        return file_names

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
