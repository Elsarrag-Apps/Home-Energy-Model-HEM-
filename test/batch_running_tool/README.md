# Introduction

The purpose of the batch tool is to allow to run multiple variations on a base JSON file in one go, and to process the results for producing summary CSV files, charts and tables. 

The reader is advised to view this README file in a markdown file viewer such as DevOps Preview.

# Contents of the batch_running_tool folder

Batch_tool.py      – This is the core script which allows to run test variations and to coordinate the output analysis.<br>
Post_processing    – this folder contains scripts relevant for the analysis of result files.<br>
Example            – this folder contains example configuration files and folder packages, i.e. inputs to the batch_tool.py script.


# Running

To run the batch tool, you must have activated the python environment as set out in the overall README.md file under section “Installing dependencies”.<br>
The batch_tool.py script takes the following arguments:<br>
- path to a configuration JSON file<br>
- path to packages folder<br>
- flag to specify the weather file type (CIBSE or EPW, as for hem.py)<br>
- path to weather file<br>
- optional flag to determine the type of analysis required.<br><br>

For example, you may test the script by running the following command (assuming the working directory is the batch_tunning_tool folder):

## RHEL 7 / CentOS 7:
```
python3 batch_tool.py example/example_config.json example/example_packages --–CIBSE-weather-file path/to/CIBSE/weather.csv
```

## Windows 10:
```
python batch_tool.py example\example_config.json example\example_packages --CIBSE-weather-file path\to\CIBSE_weather.csv
```


# Configuration files and packages

The configuration file is set up as nested {key: value} pairs as follows:<br>
At the highest level, the key is a given name for a set of tests, the value to this key is a nested set of {key: values} pairs that describe the different variations for this set of tests. See table 1.<br><br>


The general structure is as follows: <br>
- the user provides a list of base cases on which to perform test variations,<br>
- and lists of variations for specific components of the JSON files. <br><br>
The general structure of a nested {key: value} pair would look like:<br>
```
{
    "Example test named by user":{
        Base cases: [archetype1, archetype2],
        Package example: [variation1, variation2]
        }
}
```
The script will create input JSON files for each specified configuration and run them through hem. In the example above, the tool would create the following cases:<br>
- Archetype1 with variation1,<br>
- Archetype1 with variation2,<br>
- Archetype2 with variation1,<br>
- Archetype2 with variation2<br><br>

Table 1 Description of {key:value} pairs available to describe the different variations for a given set of tests.
|key       | value |
|----------|-------|
|base_json | Takes a list of JSON filenames to be found at location path_to_packages/base_json/ <br><br> For example, a filename may be “base_filename” in which case a file base_filename.json must be found at path_to_packages/base_json/base_filename.json <br><br>This is the only mandatory input, as it provides the base json files on which all variations will be performed.<br><br> The given files must be set up in a way that they could be ran as stand-alone JSON input files to the HEM engine. <br><br>For example if you wish to perform tests on 2 existing base input files called base1.json and base2.json, you should place these files in your base_json package folder, named base1.json and base2.json and the value to this key will be:<br>[“base1”, “base2”] |
|wrapper_flag | Takes a list of wrapper flags HEM can accept (you may see the list of flags HEM can accept if you call the hem.py script with the flag -h).<br><br>For example, if you wish to run the base file with the following set of wrappers: FHS and FEE, then the value will be:<br>[“future-homes-standards”, “future-homes-standards-FEE”] |
|wrapper_preproc| Takes {key: value} pairs.<br><br>This input applies variations on inputs used within before the wrapper equations are applied. For example inputs such as the number of wet rooms or number of floors (see note 2 below for list of wrapper inputs).<br><br>{key: value} pairs where:<br>- The Key is a package folder name defined under path_to_packages/wrapper_preproc/[package_name]<br>- The value is a list of relevant JSON snippet filenames found within the package folder. <br><br>For example, if you wish to test different numbers of wet rooms on a base case, you can create a folder called wet_rooms_count at the location path_to_packages/wrapper_preproc/<br>And create json snippets to test different number of wet rooms counts for example:<br>- 1_wet_room.json<br>- 2_wet_rooms.json<br>See note 1 below for how to create JSON snippets.<br>In the config file you would then call upon them as<br>{“wrapper_preproc”: {<br>     “wet_rooms_count”: [“1_wet_room”, “2_wet_rooms”]}<br>} |
|wrapper_postproc| Takes {key: value} pairs.<br><br>This input applies variations to the inputs after the wrappers have been applied – i.e. you can use it to on wrapper assumptions and overwrite pre-existing wrapper assumptions.<br><br>{key: value} pairs where:<br>- The Key is a package folder name defined under path_to_packages/wrapper_postproc/[package_name]<br>- The value is a list of relevant JSON snippet filenames found within the package folder. <br><br>For example, if you wish to test different sets of heating control schedules a base case, you can create a folder called heating_schedules at the location path_to_packages/wrapper_preproc/<br>And create json snippets to test different schedules, for example:<br>- continuous.json<br>- intermittent.json<br>See note 1 below for how to create JSON snippets.<br>In the config file you would then call upon them as<br>{“wrapper_postproc”: {<br>     “heating_schedules”: [“continuous”, “intermittent”]}<br>} |
|tariff_file| Takes a list of JSON filenames found at location path_to_packages/tariff_file/<br><br>This input allows to create variations where one or more tariff files are provided. Tariff files are necessary for running certain systems such as a heat battery for example. 
|simplified_fabric|Takes a list of JSON filenames to be found at location path_to_packages/ simplified_fabric/<br><br>This {key: value} pair is designed to edit fabric heat loss specifications easily.<br> The ‘simplified’ aspect means it will apply heat loss parameters for a given component type to all components of the same type. For example, a same u-value will be applied to all external walls.<br><br>For example, if you wish to have a quick look at how a poor vs good fabric may affect a base case, you can create 2 simplified fabric packages named poor_fabric.json and good_fabric.json and call upon them in the configuration file as follows:<br>{“simplified_fabric”: [“poor_fabric”, “good_fabric”]}<br>Note the JSON files for the simplified  fabric package must follow a specific structure which is described in Note 3. <br><br>The example folder also records an example simplified fabric package at the following location example/example_packages/simplified_fabric/simple_fabric.json. |
|User defined package name | Takes a list of JSON filenames found at location path_to_packages/[user defined package name]/<br><br>With this input, the user may edit any component of the JSON file that is not a wrapper-related input.<br><br>For example, if the user wishes to test different sizes of hot water cylinders, the user may create a package named “cylinder_sizes” and create JSON snipets for the different sizes to test for example 150L.json and 300L.json which will overwrite the relevant component of the base input JSON file. And call upon these packages in the configuration file as follows:<br>{“cylinder_sizes”: [“150L”,”300L”]}<br>Note 1 below applies. |


## Note 1
JSON packages must be set up to match the structure of the base_json file. <br>
For example, given the fictional base_json file structure below:<br>
```
{
“Variable 1”: { 
	“Variable a”: 1,
	“Variable b”: 2
	},
“Variable 2”: 3
}
```
If the user wished to create JSON packages to edit “variable a”, the JSON package should be structure as:<br>
```
{
“Variable 1”: { 
	“Variable a”: 7
	}
}
```
This is to allow packages to get merged smoothly with the base JSON.<br><br>
Important to note that packages must be designed to work with the base JSON. There are numerous cross-references in input JSON files, and these must be coherent between all packages. For example zone name references must remain the same across all packages. The concept applies to heating and cooling system names, heat source names etc. 

## Note 2
List of wrapper inputs:<br>
-	NumberOfBedRooms<br>
-	NumberOfWetRooms<br>
-	HeatingControlType<br>
-	storeys_in_building<br>
-	build_type<br>


## Note 3
Table 2 below describes the structure of a simplified fabric JSON.<br>
For definition of each variables, please refer to the HEM module building_elements.py.<br>

Table 2 Structure of a simplified fabric JSON.
|key|Value|
|---|-----|
|window |{<br>“g_value”: xx,<br>“thermal_resistance_construction”: xx<br>} |
|wall|{<br>"solar_absorption_coeff": xx,<br>"thermal_resistance_construction": xx,<br>"areal_heat_capacity": xx,<br>"mass_distribution_class": xx<br>}|
|party_wall|{<br>"thermal_resistance_construction": xx,<br>"areal_heat_capacity": xx,<br>"mass_distribution_class": xx<br>}|
|door|{<br>"solar_absorption_coeff": xx,<br>"thermal_resistance_construction": xx,<br>"areal_heat_capacity": xx,<br>"mass_distribution_class": xx<br>}|
|ground|{<br>"floor_type": "xx",<br>"thickness_walls": xx,<br>"psi_wall_floor_junc": xx,<br>"u_value": xx,<br>"r_f": xx,<br>"areal_heat_capacity": xx,<br>"mass_distribution_class": xx<br>}|
|roof|{<br>"solar_absorption_coeff": xx,<br>"thermal_resistance_construction": xx,<br>"areal_heat_capacity": xx,<br>"mass_distribution_class": xx,<br>"is_unheated_pitched_roof": xx<br>}|
|ThermalBridging|"TB_linear": {<br>                        "type": "ThermalBridgeLinear",<br>                        "linear_thermal_transmittance": xx<br>                    },<br>"TB_point": {<br>                        "type": "ThermalBridgePoint",<br>                        "heat_transfer_coeff": xx<br>                }|


For example if the user wishes to test windows, the user should create JSON packages which look like:
```
{
        "window":{
            "g_value":xx,
            "thermal_resistance_construction": xx
            }
}
```
Note internal walls and walls adjacent to unheated zones not editable via the simplified_fabric package currently.


# Documentation requirements

Each configuration JSON file must be accompanied by a .md file to describe the purpose of the set of tests. See example provided at example/example_config.json and example/example_config.md <br>
Each JSON file package must be accompanied by a .md file of the same name structured as follows: <br>
Filename, short description of its purpose, include the source is relevant. See example at example/example_packages/base_json/ESPr_DE.json and example/example_packages/base_json/ESPr_DE.md


# Outputs

A results folder will be created in the same location as the configuration file. The folder has the same name as the configuration file with the suffix __results. This folder collects all outputs for a given configuration file.<br>
The script will create input JSON files for every possible configurations. The JSON files will be named with the high-level name for a set of tests (provided at highest level of the configuration file) and each configuration will be identified with a unique id, which counts the configurations starting from 0.<br>
Each JSON files will be run through hem and their accompanying results will be saved found in the same location.<br>
A summary CSV file also gets created to allow to easily identify each configuration. The summary file is named [configuration_filename]_summary.csv. It is structure as:

|Package name|[test_name]_0|[test_name]_1|etc. for all test names and their variations specified in input config file|
|------------|-------------|-------------|---------------------------------------------------------------------------|
|Base_json   |Text snippet from the relevant base JSON file’s accompanying .md file.|||
|Other package |Text snippet from the relevant package JSON file’s accompanying .md file.|||


# post-processing scripts

If the batch_tool is run with the flag –QA-post-processing, the outputs get formatted into a CSV file ready for copy-pasting into the phase 1 sensitivity analysis spreadsheet created by the HEM QA team.


