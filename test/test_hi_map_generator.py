import unittest
from pathlib import Path
from unittest.mock import patch

from imap_data_access import ProcessingInputCollection

from mapping_tool.configuration import Configuration
from mapping_tool.hi_map_generator import HiMapGenerator


class TestHiMapGenerator(unittest.TestCase):
    @patch('mapping_tool.hi_map_generator.Hi')
    def test_constructor(self, mock_imap_cli_hi):
        config = Configuration.from_json(Path("./example_configuration_files/example_config.json"))
        hi_map_generator = HiMapGenerator(config)

        descriptor = "h90-ena-h-sf-sp-ram-hae-2deg-6mo"
        dependencies = ProcessingInputCollection()
        hi_map_generator.make_map(descriptor, dependencies)

        mock_imap_cli_hi.assert_called_with(
        "l2",
        descriptor,
        "[]",
        "20000101",
        None,
        "0",
        False,
        )

        mock_imap_cli_hi.return_value.process.assert_called()