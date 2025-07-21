import json
from datetime import datetime

from imap_data_access import ProcessingInputCollection
from imap_processing.cli import Hi


class HiMapGenerator:
    def __init__(self, config):
        self.config = config

    def make_map(self, descriptor: str, start_date: datetime, dependencies: ProcessingInputCollection):
        hi_processor = Hi("l2", descriptor, dependencies.serialize(),
                          start_date.strftime("%Y%m%d"),
                          None,
                          "0",
                          False, )
        hi_processor.process()
