from datetime import datetime, timezone
from pathlib import Path

import imap_data_access
import requests
from imap_processing.ena_maps.utils.naming import MapDescriptor, MappableInstrumentShortName
from spiceypy import spiceypy


class DependencyCollector:
    IMAP_API = "https://api.dev.imap-mission.com/"

    @staticmethod
    def get_pointing_sets(descriptor: MapDescriptor, start_date: datetime, end_date: datetime):
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

        if descriptor.survival_corrected == "sp":
            files.extend(filter_files_by_highest_version(imap_data_access.query(instrument="glows",
                                                                                start_date=start_date,
                                                                                end_date=end_date,
                                                                                data_level="l3e",
                                                                                descriptor=f"survival-probability-{instrument_for_query[:2]}")))

        return [pset['file_path'] for pset in files]

    @classmethod
    def furnish_spice(cls, start_date: datetime, end_date: datetime):
        for kernel_type in ["leapseconds", "spacecraft_clock", "pointing_attitude", "imap_frames", "science_frames"]:
            file_json = requests.get(cls.IMAP_API + f"spice-query?type={kernel_type}&start_time=0").json()
            file_names = []
            for spice_file in file_json:
                spice_start_date = datetime.strptime(spice_file["min_date_datetime"], "%Y-%m-%d, %H:%M:%S")
                spice_start_date = spice_start_date.replace(tzinfo=timezone.utc)
                spice_end_date = datetime.strptime(spice_file["max_date_datetime"], "%Y-%m-%d, %H:%M:%S")
                spice_end_date = spice_end_date.replace(tzinfo=timezone.utc)
                if spice_start_date <= end_date and start_date < spice_end_date:
                    file_names.append(Path(spice_file["file_name"]).name)

            spice_files = [imap_data_access.download(file_name) for file_name in file_names]
            for kernel in spice_files:
                spiceypy.furnsh(str(kernel))
