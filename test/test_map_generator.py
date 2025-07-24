import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, call

import imap_data_access

from mapping_tool.configuration import Configuration
from mapping_tool.map_generator import process
from test.test_helpers import get_example_config_path


class TestMapGenerator(unittest.TestCase):
    def test_process(self):
        mock_processor = Mock()
        example_config_path = get_example_config_path() / "test_config.json"
        config: Configuration = Configuration.from_json(example_config_path)
        process(mock_processor, config)

        pre_processing = mock_processor.pre_processing
        do_processing = mock_processor.do_processing
        post_processing = mock_processor.post_processing

        pre_processing.assert_called_once()
        do_processing.assert_called_once_with(pre_processing.return_value)
        post_processing.assert_called_once_with(do_processing.return_value, pre_processing.return_value)
        mock_processor.cleanup.assert_called_once()

    @patch('mapping_tool.map_generator.input')
    def test_process_prompts_user_to_overwrite_already_existing_file(self, mock_input):
        mock_processor = Mock()

        config: Configuration = Mock(spec=Configuration)

        hi_map_that_gets_overwritten = "hi_map.cdf"
        ultra_map_that_is_not_overwritten = "ultra_map.cdf"
        some_new_map = "some_new_map.cdf"

        original_data_dir = imap_data_access.config['DATA_DIR']

        def write_cdf_files_to_data_dir(results, downloaded_deps):
            self.assertNotEqual(imap_data_access.config["DATA_DIR"], original_data_dir)
            (imap_data_access.config["DATA_DIR"] / hi_map_that_gets_overwritten).write_text("new hi map data")
            (imap_data_access.config["DATA_DIR"] / ultra_map_that_is_not_overwritten).write_text("should be ignored")
            (imap_data_access.config["DATA_DIR"] / some_new_map).write_text("brand new map")

        mock_processor.post_processing.side_effect = write_cdf_files_to_data_dir

        mock_input.side_effect = ["y", "n"]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_directory = Path(temp_dir)
            (output_directory / hi_map_that_gets_overwritten).write_text("old hi map data")
            (output_directory / ultra_map_that_is_not_overwritten).write_text("ultra data")

            config.output_directory = output_directory

            output_cdfs = process(mock_processor, config)

            mock_input.assert_has_calls([
                call(f"File {hi_map_that_gets_overwritten} already exists. Would you like to overwrite it? (Y/n) "),
                call(f"File {ultra_map_that_is_not_overwritten} already exists. Would you like to overwrite it? (Y/n) ")
            ])

            self.assertEqual("new hi map data", (output_directory / hi_map_that_gets_overwritten).read_text())
            self.assertEqual("ultra data", (output_directory / ultra_map_that_is_not_overwritten).read_text())
            self.assertEqual("brand new map", (output_directory / some_new_map).read_text())

            self.assertEqual(original_data_dir, imap_data_access.config["DATA_DIR"])

            expected_output_files = [output_directory / hi_map_that_gets_overwritten,
                                     output_directory / some_new_map]
            self.assertEqual(expected_output_files, output_cdfs)
