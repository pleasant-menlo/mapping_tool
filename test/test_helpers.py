import dataclasses
import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from unittest import SkipTest

from imap_data_access.processing_input import ProcessingInput

import pytz


def get_example_config_path():
    return Path(__file__).parent / "example_configuration_files"


def get_test_cdf_file_path():
    return Path(__file__).parent / "cdf_files"


def utcdatetime():
    return datetime(2025, 8, 20, tzinfo=pytz.utc)

def assert_imap_processing_inputs_match(expected: list[ProcessingInput], actual: list[ProcessingInput], any_order = False):
    assert len(expected) == len(actual)

    expected_to_compare = deepcopy(expected)
    actual_to_compare = deepcopy(actual)

    if any_order:
        expected_to_compare = sorted(expected_to_compare, key=lambda i: ("").join(i.filename_list))
        actual_to_compare = sorted(actual_to_compare, key=lambda i: ("").join(i.filename_list))

    for expected, actual in zip(expected_to_compare, actual_to_compare):
        for field in dataclasses.fields(expected):
            if field.name == "imap_file_paths":
                continue
            assert getattr(actual, field.name) == getattr(expected, field.name), f"{getattr(actual, field.name)} != {getattr(expected, field.name)}"

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
