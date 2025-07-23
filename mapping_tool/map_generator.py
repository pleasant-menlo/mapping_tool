import json
from datetime import datetime

from imap_data_access import ProcessingInputCollection
from imap_processing.cli import Hi, Lo, Ultra


def make_hi_map(descriptor: str, start_date: datetime, dependencies: ProcessingInputCollection):
    hi_processor = Hi(data_level="l2", data_descriptor=descriptor, dependency_str=dependencies.serialize(),
                      start_date=start_date.strftime("%Y%m%d"),
                      repointing=None,
                      version="0",
                      upload_to_sdc=False)
    hi_processor.process()


def make_lo_map(descriptor: str, start_date: datetime, dependencies: ProcessingInputCollection):
    lo_processor = Lo(data_level="l2", data_descriptor=descriptor, dependency_str=dependencies.serialize(),
                      start_date=start_date.strftime("%Y%m%d"),
                      repointing=None,
                      version="0",
                      upload_to_sdc=False)
    lo_processor.process()


def make_ultra_map(descriptor: str, start_date: datetime, dependencies: ProcessingInputCollection):
    ultra_processor = Ultra(data_level="l2", data_descriptor=descriptor, dependency_str=dependencies.serialize(),
                            start_date=start_date.strftime("%Y%m%d"),
                            repointing=None,
                            version="0",
                            upload_to_sdc=False)
    ultra_processor.process()
