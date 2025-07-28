import logging
from typing import Optional

logger = logging.getLogger(__name__)

import tempfile
from pathlib import Path

import imap_data_access
from imap_processing.cli import ProcessInstrument

from mapping_tool.configuration import Configuration


class MapPrinter:
    def __init__(self, configuration: Configuration):
        self.output_directory = configuration.output_directory
        self.output_file_names = iter(configuration.output_files)

    def print(self, processor: ProcessInstrument):
        pass


def process(processor: ProcessInstrument, output_directory: Path, output_file_name: Optional[str] = None) -> \
        list[Path]:
    downloaded_deps = processor.pre_processing()
    try:
        results = processor.do_processing(downloaded_deps)
    except Exception as e:
        logger.warning(
            f" Processor failed when trying to generate map: {processor.descriptor}! Skipping\nexception: {e}")
        processor.cleanup()
        return []

    files_written = []

    with tempfile.TemporaryDirectory() as temp_dir:
        old_data_dir = imap_data_access.config["DATA_DIR"]
        try:
            imap_data_access.config["DATA_DIR"] = Path(temp_dir)
            processor.post_processing(results, downloaded_deps)
            match list(Path(temp_dir).rglob("*.cdf")):
                case [file]:
                    filename = output_file_name or file.name
                    output_file_path = output_directory / filename
                    if output_file_path.exists():
                        overwrite = input(f"File {filename} already exists. Would you like to overwrite it? (Y/n) ")
                        if overwrite not in ["Y", "y", ""]:
                            return []
                    logger.info(f"Writing to: {output_file_path}")
                    output_file_path.parent.mkdir(parents=True, exist_ok=True)
                    file.replace(output_file_path)
                    files_written.append(output_file_path)
                case [_, _, *_]:
                    raise ValueError("Expected to write up to one map CDF")
        except Exception as e:
            raise e
        finally:
            imap_data_access.config["DATA_DIR"] = old_data_dir
    processor.cleanup()
    return files_written
