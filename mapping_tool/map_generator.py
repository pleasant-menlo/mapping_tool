import tempfile
from pathlib import Path

import imap_data_access
from imap_processing.cli import ProcessInstrument

from mapping_tool.configuration import Configuration


def process(processor: ProcessInstrument, config: Configuration) -> list[Path]:
    downloaded_deps = processor.pre_processing()
    results = processor.do_processing(downloaded_deps)

    files_written = []

    with tempfile.TemporaryDirectory() as temp_dir:
        old_data_dir = imap_data_access.config["DATA_DIR"]
        try:
            imap_data_access.config["DATA_DIR"] = Path(temp_dir)
            processor.post_processing(results, downloaded_deps)
            files = list(Path(temp_dir).rglob("*.cdf"))
            for file in files:
                output_file_path = config.output_directory / file.name
                if output_file_path.exists():
                    overwrite = input(f"File {file.name} already exists. Would you like to overwrite it? (Y/n) ")
                    if overwrite not in ["Y", "y", ""]:
                        continue

                print("Writing to: ", output_file_path)
                file.replace(output_file_path)
                files_written.append(output_file_path)
        except Exception as e:
            raise e
        finally:
            imap_data_access.config["DATA_DIR"] = old_data_dir
    processor.cleanup()
    return files_written
