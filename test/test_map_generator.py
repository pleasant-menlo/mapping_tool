import unittest
from datetime import datetime
from unittest.mock import patch

from imap_data_access import ProcessingInputCollection

from mapping_tool.map_generator import make_hi_map, make_lo_map, make_ultra_map


class TestMapGenerator(unittest.TestCase):
    @patch('mapping_tool.map_generator.Hi')
    def test_make_hi_map(self, mock_imap_cli_hi):
        start_date = datetime(2025, 1, 1)
        descriptor = "h90-ena-h-sf-sp-ram-hae-2deg-6mo"
        dependencies = ProcessingInputCollection()
        make_hi_map(descriptor, start_date, dependencies)

        mock_imap_cli_hi.assert_called_with(
            data_level="l2",
            data_descriptor=descriptor,
            dependency_str="[]",
            start_date="20250101",
            repointing=None,
            version="0",
            upload_to_sdc=False
        )

        mock_imap_cli_hi.return_value.process.assert_called()

    @patch('mapping_tool.map_generator.Lo')
    def test_make_lo_map(self, mock_imap_cli_lo):
        start_date = datetime(2025, 1, 1)
        descriptor = "l090-ena-h-sf-sp-ram-hae-2deg-6mo"
        dependencies = ProcessingInputCollection()
        make_lo_map(descriptor, start_date, dependencies)

        mock_imap_cli_lo.assert_called_with(
            data_level="l2",
            data_descriptor=descriptor,
            dependency_str="[]",
            start_date="20250101",
            repointing=None,
            version="0",
            upload_to_sdc=False
        )

        mock_imap_cli_lo.return_value.process.assert_called()

    @patch('mapping_tool.map_generator.Ultra')
    def test_make_ultra_map(self, mock_imap_cli_ultra):
        start_date = datetime(2025, 1, 1)
        descriptor = "u90-ena-h-sf-sp-ram-hae-2deg-6mo"
        dependencies = ProcessingInputCollection()
        make_ultra_map(descriptor, start_date, dependencies)

        mock_imap_cli_ultra.assert_called_with(
            data_level="l2",
            data_descriptor=descriptor,
            dependency_str="[]",
            start_date="20250101",
            repointing=None,
            version="0",
            upload_to_sdc=False
        )

        mock_imap_cli_ultra.return_value.process.assert_called()
