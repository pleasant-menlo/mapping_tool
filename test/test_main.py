import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

import main
from test.test_helpers import run_periodically, get_example_config_path


class TestMain(unittest.TestCase):

    @run_periodically(timedelta(days=1))
    def test_main_integration(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            tmp_dir = Path(temporary_directory)

            shutil.copy(get_example_config_path() / "integration_test_config.json", tmp_dir / "config.json")
            shutil.copy(get_example_config_path() / "imap_science_100.tf", tmp_dir / "spice_kernel.tf")

            process_result = subprocess.run([sys.executable, main.__file__, "config.json"], cwd=temporary_directory,
                                            text=True)

            if process_result.returncode != 0:
                self.fail("Process failed:\n" + process_result.stderr)

            self.assertTrue(
                (tmp_dir / "imap_hi_l3_h90-enatest-h-sf-sp-ram-imaphae-4deg-3mo-mapper_20250702_v000.cdf").exists())
