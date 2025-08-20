# IMAP Mapping Tool

Quick links:
* [Installation](#installation)
* [Config File Parameters](#config-file-parameters)
* [Troubleshooting](#installation-issues)

## Installation

1. Clone/Download the repository
     ```shell
    git clone https://github.com/pleasant-menlo/mapping_tool
    cd mapping_tool
     ```

2. [Download](https://www.python.org/downloads/) and install Python version 3.13
   * Alternatively, a package manager like Homebrew or Chocolatey can be used 
     * macOS: `brew install python@3.13`
     * Windows: `choco install python313`


3. Setup a virtual environment
    ```shell
    python3.13 -m venv venv 
    ```
4. Activate virtual environment
    * #### Windows: 
        ```shell
        venv\Scripts\activate
        ```
    * #### macOS/Linux 
        ```shell 
        source venv/bin/activate
        ```
      
5. Install dependencies
     ```shell
    pip install -r requirements.txt --prefer-binary
    ```

## Usage
From within the virtual environment, run the following:
```shell
    python main.py {path to config file}
```

Adding `-v` or `--verbose` to the command will include lots of diagnostic information.

## Configuration File Parameters
The map to be created is defined by the configuration file passed to `main.py`. The configuration can be specified in YAML or JSON. An annotated example file can be found [here](./example_config_file.yaml). Additional examples can be found in the [example_configuration_files](./example_configuration_files) directory. Available options and their corresponding values are:
* `canonical_map_period` - Specification of the time periods to be used for map creation. Either a canonical map period or a list of custom time ranges can be specified, but not both.
  * `year` - The year corresponding to the first map
  * `quarter` - The quarter corresponding to the first map
  * `map_period` - The map period for each map in months (e.g. 3, 6, 12)
  * `number_of_maps` - The number of maps to be calculated for the output CDF file


* `time_ranges` -  A list of custom date ranges to be used for map creation. Either a canonical map period or a list of custom time ranges can be specified, but not both.
  * `start` - The start date of the time range
  * `end` - The end date of the time range
  ##### Example of time ranges to create a file with to maps:
    ```yaml
    time_ranges:
      - start: 2025-06-15 
        end: 2025-08-01
      - start: 2025-04-15 
        end: 2025-05-01
    ```

* `instrument` - The instrument to be used to generate the map. Valid options are: "Hi 45", "Hi 90", "Hi combined", "Ultra 45", "Ultra 90", "Ultra combined", "Lo".


* `spin_phase` - The spin phase to be used to generate the map. Valid options are: "ram", "anti-ram", "full spin".


* `reference_frame_type` - The reference frame type to be used for the map projection. Valid options are: "spacecraft", "heliospheric".


* `survival_corrected` - Boolean value indicating whether the map should be survival-probability corrected.


* `spice_frame_name` - The SPICE frame to be used for the map projection. Some frames (e.g. "hae") are defined by the mission and can be used without supplying a custom spice kernel.


* `pixelation_scheme` - The pixelation scheme to be used for map generation. Valid options are "square" or "healpix".


* `pixelation_scheme` - The pixel parameter to be used for map generation. This defines the degree resolution for square maps, and the nside for HEALPix maps. Valid options are 2, 4, and 6 for square maps, and 16, 32, 64, 128, 256, and 512 for HEALPix maps.


* `map_data_type` - The primary map data type. Valid parameters are `ENA Intensity` or `Spectral Index`.


* `lo_species` - The species used to create the map. Optional property, which only applies to IMAP-Lo maps. Valid parameters are `h` or `o`.


* `quantity_suffix` - Optional text suffix to be added to the map data type in the descriptor of the output file.


* `kernel_path` - Optional path to a SPICE kernel file to be included in map generation. Used in conjunction with the "spice_frame_name" to allow for custom frame definitions.


### Troubleshooting
* If there is a problem installing dependencies for SciPy on macOS, follow the steps below. The OpenBLAS linear algebra C package needs to be installed
first: https://docs.scipy.org/doc/scipy-1.16.0/building/index.html

    ```shell
    brew install gfortran openblas pkg-config
    brew info openblas | grep PKG_CONFIG_PATH
    export PKG_CONFIG_PATH=<path from above command>
    pip install -r requirements.txt
    ```

* If there is an error installing netCDF on macOS (i.e. `ValueError: did not find netCDF version 4 headers`), you may have to install netCDF prior to pip install:
    ```shell
    brew install netcdf
    pip install -r requirements.txt
    ```

