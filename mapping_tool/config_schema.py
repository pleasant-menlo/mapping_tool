import json
from pathlib import Path

schema = json.load(open(Path(__file__).parent / 'config_schema.json'))
