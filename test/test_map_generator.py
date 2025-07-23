import unittest
from unittest.mock import Mock

from mapping_tool.configuration import Configuration
from mapping_tool.map_generator import process
from test.test_helpers import get_example_config_path


class TestMapGenerator(unittest.TestCase):
    def test_process(self):
        mock_processor = Mock()
        example_config_path = get_example_config_path() / "example_config.json"
        config: Configuration = Configuration.from_json(example_config_path)
        process(mock_processor, config)

        pre_processing = mock_processor.pre_processing
        do_processing = mock_processor.do_processing
        post_processing = mock_processor.post_processing

        pre_processing.assert_called_once()
        do_processing.assert_called_once_with(pre_processing.return_value)
        post_processing.assert_called_once_with(do_processing.return_value, pre_processing.return_value)
        mock_processor.cleanup.assert_called_once()
