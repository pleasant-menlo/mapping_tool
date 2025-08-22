import json
from pathlib import Path

with open(Path(__file__).parent / 'config_schema.json') as f:
    schema = json.load(f)
