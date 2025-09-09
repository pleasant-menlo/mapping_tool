import json
from dataclasses import dataclass
from datetime import datetime, timedelta, tzinfo
from pathlib import Path
from typing import Optional
from unittest import skip, skipIf, SkipTest

import pytz


def get_example_config_path():
    return Path(__name__).parent / "example_configuration_files"


def get_test_cdf_file_path():
    return Path(__name__).parent / "cdf_files"


def utcdatetime():
    return datetime(2025, 8, 20, tzinfo=pytz.utc)


@dataclass
class PeriodicallyRunTest:
    test_name: str
    frequency: str
    last_run: Optional[str]


def run_periodically(frequency: timedelta):
    def run_periodically_decorator(test_item):
        periodically_run_tests_path = Path(__file__).parent / "periodically_run_tests.json"
        periodically_run_tests = json.loads(periodically_run_tests_path.read_text())

        last_run = periodically_run_tests.get(test_item.__name__)

        def test_thing(*args):
            if last_run is not None:
                last_run_time = datetime.fromisoformat(last_run) + frequency
                if datetime.now() < last_run_time:
                    raise SkipTest(f'Skipping expensive test, {test_item.__name__}, because it passed recently')

            try:
                test_item(*args)
                periodically_run_tests[test_item.__name__] = datetime.now().isoformat()
                periodically_run_tests_path.write_text(json.dumps(periodically_run_tests))
            except Exception as e:
                periodically_run_tests[test_item.__name__] = None
                periodically_run_tests_path.write_text(json.dumps(periodically_run_tests))
                raise e

        return test_thing

    return run_periodically_decorator
