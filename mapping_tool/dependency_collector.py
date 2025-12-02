from datetime import datetime, timezone
from pathlib import Path

from spacepy.pycdf import CDF

import imap_data_access
import requests
from imap_processing.ena_maps.utils.naming import MapDescriptor, MappableInstrumentShortName
from imap_data_access.processing_input import AncillaryInput, ScienceInput
from mapping_tool.mapping_tool_descriptor import MappingToolDescriptor


class DependencyCollector:
    IMAP_API = "https://api.dev.imap-mission.com/"

    @staticmethod
    def get_pointing_sets(descriptor: MapDescriptor, start_date: datetime, end_date: datetime) -> list[str]:
        map_instrument_pset_descriptors = []

        if descriptor.instrument == MappableInstrumentShortName.HI:
            if descriptor.sensor in ["45", "combined"]:
                map_instrument_pset_descriptors.append(f"45sensor-pset")
            if descriptor.sensor in ["90", "combined"]:
                map_instrument_pset_descriptors.append(f"90sensor-pset")

        elif descriptor.instrument == MappableInstrumentShortName.LO:
            map_instrument_pset_descriptors.append("pset")

        elif descriptor.instrument == MappableInstrumentShortName.ULTRA:
            pset_string = "spacecraftpset" if descriptor.frame_descriptor == "sf" else "heliopset"
            if descriptor.sensor in ["45", "combined"]:
                map_instrument_pset_descriptors.append(f"45sensor-{pset_string}")
            if descriptor.sensor in ["90", "combined"]:
                map_instrument_pset_descriptors.append(f"90sensor-{pset_string}")

        assert len(map_instrument_pset_descriptors) > 0
        instrument_for_query = descriptor.instrument.name.lower()
        start_date = start_date.strftime("%Y%m%d")
        end_date = end_date.strftime("%Y%m%d")

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

    @classmethod
    def get_ancillary_dependencies(cls, descriptor: MapDescriptor) -> list[AncillaryInput]:
        ancillary_descriptors_to_fetch =  cls._get_ancillary_descriptor(descriptor)
        instrument = descriptor.instrument.name.lower()

        ancillary_files = []
        for descriptor in ancillary_descriptors_to_fetch:
            ancillary_files.extend(imap_data_access.query(
                instrument=instrument,
                descriptor=descriptor,
                table="ancillary",
                version='latest'
            ))
        return [AncillaryInput(Path(f["file_path"]).name) for f in ancillary_files]

    @staticmethod
    def get_survival_probability_dependencies(descriptor: MappingToolDescriptor, start_date: datetime, end_date: datetime, input_maps: list[Path]) -> list[ScienceInput]:
        if descriptor.survival_corrected == "nsp":
            return []

        l1c_parent_names = set()
        for input_map in input_maps:
            l1c_parent_names.update(DependencyCollector._get_l1c_parents(input_map))

        return [*DependencyCollector.get_glows_dependencies(descriptor, start_date, end_date), *[ScienceInput(l1c) for l1c in l1c_parent_names]]

    @staticmethod
    def get_glows_dependencies(descriptor: MappingToolDescriptor, start_date: datetime, end_date: datetime) -> list[ScienceInput]:
        if descriptor.survival_corrected == "nsp":
            return []

        psets = imap_data_access.query(
            instrument='glows',
            descriptor=descriptor.get_descriptor_for_query("glows"),
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
        )

        return [ScienceInput(Path(f["file_path"]).name) for f in psets]

    @classmethod
    def _get_ancillary_descriptor(cls, map_descriptor: MapDescriptor):
        match map_descriptor:
            case MapDescriptor(instrument=MappableInstrumentShortName.HI, sensor="90", survival_corrected="nsp"):
                return ["90sensor-cal-prod", "90sensor-esa-energies", "90sensor-esa-eta-fit-factors"]
            case MapDescriptor(instrument=MappableInstrumentShortName.HI, sensor="45", survival_corrected="nsp"):
                return ["45sensor-cal-prod", "45sensor-esa-energies", "45sensor-esa-eta-fit-factors"]
            case MapDescriptor(instrument=MappableInstrumentShortName.LO, survival_corrected="nsp"):
                return ["esa-eta-fit-factors"]
            case MapDescriptor(instrument=MappableInstrumentShortName.ULTRA, sensor="combined", principal_data="spx"):
                return ["ulc-spx-energy-ranges"]
            case MapDescriptor(instrument=MappableInstrumentShortName.ULTRA, sensor="combined"):
                return ["l2-energy-bin-group-sizes"]
            case MapDescriptor(instrument=MappableInstrumentShortName.ULTRA, survival_corrected="sp"):
                return ["l2-energy-bin-group-sizes"]
            case _:
                return []

    @staticmethod
    def _get_l1c_parents(input_map: Path) -> set[str]:
        with CDF(str(input_map)) as cdf:
            return set(parent for parent in cdf.attrs["Parents"] if "l1c" in parent)


    @classmethod
    def collect_spice_kernels(cls, start_date: datetime, end_date: datetime) -> list[str]:
        file_names = []
        for kernel_type in ["leapseconds", "spacecraft_clock", "pointing_attitude", "imap_frames", "science_frames", "planetary_ephemeris", "ephemeris_reconstructed"]:
            file_json = requests.get(cls.IMAP_API + f"spice-query?type={kernel_type}&start_time=0").json()
            for spice_file in file_json:
                spice_start_date = datetime.strptime(spice_file["min_date_datetime"], "%Y-%m-%d, %H:%M:%S")
                spice_start_date = spice_start_date.replace(tzinfo=timezone.utc)
                spice_end_date = datetime.strptime(spice_file["max_date_datetime"], "%Y-%m-%d, %H:%M:%S")
                spice_end_date = spice_end_date.replace(tzinfo=timezone.utc)
                if spice_start_date <= end_date and start_date < spice_end_date:
                    file_names.append(Path(spice_file["file_name"]).name)
        return file_names
