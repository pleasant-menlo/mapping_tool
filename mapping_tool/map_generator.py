import tempfile
from pathlib import Path

import imap_data_access
from imap_processing.cli import ProcessInstrument

from mapping_tool.configuration import Configuration


def process(processor: ProcessInstrument, config: Configuration) -> list[Path]:
    downloaded_deps = processor.pre_processing()
    results = processor.do_processing(downloaded_deps)
    with tempfile.TemporaryDirectory() as temp_dir:
        old_data_dir = imap_data_access.config["DATA_DIR"]
        try:
            imap_data_access.config["DATA_DIR"] = Path(temp_dir)
            processor.post_processing(results, downloaded_deps)
            files = Path(temp_dir).rglob("*.cdf")
            for file in files:
                if (config.output_directory / file.name).exists():
                    overwrite = input(f"File {file.name} already exists. Would you like to overwrite it? (Y/n) ")
                    if overwrite not in ["Y", "y", ""]:
                        continue

                print("Writing to: ", config.output_directory / file.name)
                file.replace(config.output_directory / file.name)
        except Exception as e:
            raise e
        finally:
            imap_data_access.config["DATA_DIR"] = old_data_dir
    processor.cleanup()
    return files
