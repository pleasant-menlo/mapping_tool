import tempfile
import unittest
from pathlib import Path
from unittest import skip
from unittest.mock import Mock, patch, call

import imap_data_access

from mapping_tool import map_generator
from mapping_tool.map_generator import process
from test.test_builders import create_configuration


class TestMapGenerator(unittest.TestCase):
    def test_process(self):
        self.assertTrue(hasattr(map_generator, "logger"))

        mock_processor = Mock()
        process(mock_processor, Path("output/dir"))

        pre_processing = mock_processor.pre_processing
        do_processing = mock_processor.do_processing
        post_processing = mock_processor.post_processing

        pre_processing.assert_called_once()
        do_processing.assert_called_once_with(pre_processing.return_value)
        post_processing.assert_called_once_with(do_processing.return_value, pre_processing.return_value)
        mock_processor.cleanup.assert_called_once()

    @patch('mapping_tool.map_generator.input')
    def test_process_overwrites_existing(self, mock_input):
        mock_processor = Mock()
        map_generator.logger = Mock()

        map_file_name = "hi_map.cdf"
        original_data_dir = imap_data_access.config['DATA_DIR']

        def write_cdf_files_to_data_dir(results, downloaded_deps):
            self.assertNotEqual(imap_data_access.config["DATA_DIR"], original_data_dir)
            (imap_data_access.config["DATA_DIR"] / map_file_name).write_text("new hi map data")

        mock_processor.post_processing.side_effect = write_cdf_files_to_data_dir

        mock_input.return_value = "y"

        with tempfile.TemporaryDirectory() as temp_dir:
            output_directory = Path(temp_dir)

            expected_output_path = output_directory / map_file_name
            expected_output_path.write_text("old hi map data")

            output_cdfs = process(mock_processor, output_directory)

            mock_input.assert_called_once_with(
                f"File {map_file_name} already exists. Would you like to overwrite it? (Y/n) ")
            map_generator.logger.info.assert_called_once_with(f"Writing to: {expected_output_path}")

            self.assertEqual("new hi map data", expected_output_path.read_text())
            self.assertEqual([expected_output_path], output_cdfs)
            self.assertEqual(original_data_dir, imap_data_access.config["DATA_DIR"])

    @patch('mapping_tool.map_generator.input')
    def test_process_overwrite_is_refused(self, mock_input):
        mock_processor = Mock()
        map_generator.logger = Mock()

        mock_input.return_value = 'n'

        def write_cdf_files_to_data_dir(results, downloaded_deps):
            (imap_data_access.config["DATA_DIR"] / "ultra_map.cdf").write_text("should be ignored")

        mock_processor.post_processing.side_effect = write_cdf_files_to_data_dir

        with tempfile.TemporaryDirectory() as temp_dir:
            output_directory = Path(temp_dir)
            ultra_output_path = output_directory / 'ultra_map_filename'

            ultra_output_path.write_text("ultra data")

            output_cdfs = process(mock_processor, output_directory, 'ultra_map_filename')

            mock_input.assert_called_once_with(
                f"File ultra_map_filename already exists. Would you like to overwrite it? (Y/n) ")

            self.assertEqual("ultra data", ultra_output_path.read_text())
            self.assertEqual([], output_cdfs)

    def test_process_gracefully_handles_processing_exceptions(self):
        map_generator.logger = Mock()

        mock_processor = Mock()
        mock_processor.descriptor = "some_map_descriptor"

        mock_processor.do_processing.side_effect = Exception("test")
        files_written = process(mock_processor, create_configuration())
        self.assertEqual([], files_written)
        mock_processor.cleanup.assert_called_once()
        map_generator.logger.warning.assert_called_once_with(
            f" Processor failed when trying to generate map: some_map_descriptor! Skipping\nexception: test")

    def test_specifying_output_files_generates_files_with_those_names(self):
        mock_processor = Mock()
        output_file_name = 'hi_map.cdf'

        def write_cdf_files_to_data_dir(results, downloaded_deps):
            (imap_data_access.config["DATA_DIR"] / "long_hi_cdf_name.cdf").write_text("hi map data")

        mock_processor.post_processing.side_effect = write_cdf_files_to_data_dir

        with tempfile.TemporaryDirectory() as temp_dir:
            output_directory = Path(temp_dir)

            output_cdfs = process(mock_processor, output_directory, output_file_name)

            expected_output_path = output_directory / output_file_name
            self.assertEqual("hi map data", expected_output_path.read_text())

            self.assertEqual([expected_output_path], output_cdfs)
