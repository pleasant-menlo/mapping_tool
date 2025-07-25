# mapping_tool

## Installation

1. Clone/Download the repo

 ```shell
    git clone https://github.com/pleasant-menlo/mapping_tool
    cd mapping_tool
 ```

2. Setup a virtual environment

```shell
    python3.13 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
```

## Usage

From within the virtual environment

 ```shell
    python main.py {path to config file}
 ```

### Config File Parameters

```json
{
  "canonical_map_period": {
    "year": 2025,
    "quarter": 1,
    "map_period": 6,
    "number_of_maps": 1
  },
  "instrument": [
    "Hi 90",
    "Hi 45"
  ],
  "spin_phase": "Ram",
  "reference_frame": "spacecraft",
  "survival_corrected": true,
  "coordinate_system": "hae",
  "pixelation_scheme": "square",
  "pixel_parameter": 2,
  "map_data_type": "ENA Intensity",
  "lo_species": "h",
  "output_directory": "."
}
```



