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
```

3. Download dependencies

For SciPy, the OpenBLAS linear algebra C package needs to be installed
first: https://docs.scipy.org/doc/scipy-1.16.0/building/index.html

```shell
    brew install gfortran openblas pkg-config
    brew info openblas | grep PKG_CONFIG_PATH
    export PKG_CONFIG_PATH=<path from above command>
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



