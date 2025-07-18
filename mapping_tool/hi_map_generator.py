import json

from imap_data_access import ProcessingInputCollection
from imap_processing.cli import Hi


class HiMapGenerator:
    def __init__(self, config):
        self.config = config

    def make_map(self, descriptor: str, dependencies: ProcessingInputCollection):
        hi_processor = Hi("l2", descriptor, dependencies.serialize(),
        "20000101",
        None,
        "0",
        False,)
        hi_processor.process()

