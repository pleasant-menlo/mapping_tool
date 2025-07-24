import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


def get_example_config_path():
    return Path(__name__).parent / "example_configuration_files"


@dataclass
class PeriodicallyRunTest:
    test_name: str
    frequency: str
    last_run: Optional[str]


def run_periodically(test_to_decorate):
    periodically_run_tests_path = Path(__file__).parent / "periodically_run_tests.json"
    periodically_run_tests = json.loads(periodically_run_tests_path.read_text())

    current_test = periodically_run_tests.get(test_to_decorate.__name__)
    if current_test is None:
        raise ValueError("Could not find test name in periodically run tests")

    def test_thing(*args):
        if current_test["last_run"] is not None:
            next_run_time = datetime.fromisoformat(current_test["last_run"]) + timedelta(
                days=int(current_test["frequency"]))
            if current_test["last_run"] and datetime.now() < next_run_time:
                return
        test_to_decorate(*args)
        current_test["last_run"] = datetime.now().isoformat()
        periodically_run_tests_path.write_text(json.dumps(periodically_run_tests))

    return test_thing
