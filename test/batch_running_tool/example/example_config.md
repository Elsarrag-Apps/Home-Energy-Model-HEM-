The purpose of this example configuration file is to provide examples for create a configuration json file compatible with the batch_tool.py

The following examples are provided:

base_case
	This case provides a simple example for how to specify running one base json file (ESPr_DE)
	with the future homes standard (FHS) wrapper.

heat_schedule_tests
	This case provides an example for creating 2 variations of heating schedules
	on a base json file where all other assumptions are provided by the FHS wrapper.
	The heating schedules must overwrite the FHS wrapper assumptions, 
	therefore the package is nested under "wrapper_postproc".
	
	To edit other post FHS processing components, you can create a new package folder
	appropriately named under packages_folder/wrapper_postproc/[new_package_folder]/
	and reference any package JSON located in this folder as a nested dictionary under
	"wrapper_postproc" in the config file.

wet_room_count_test
	This case provides an example for creating 2 variations of wet room counts
	on a base json file where all other assumptions are provided by the FHS wrapper.
	The number of wet rooms is an input to the FHS wrapper,
	some FHS assumptions are calibrated with respect to the number of wetrooms,
	Therefore, this input must be provided prior to applying the FHS wrapper, 
	therefore the package is nested under "wrapper_preproc".

	To edit other FHS pre-processing components, you can create a new package folder
	appropriately named under packages_folder/wrapper_preproc/[new_package_folder]/
	and reference any package JSON located in this folder as a nested dictionary under
	"wrapper_preproc" in the config file.

PV_test
	This case provides an example for creating 3 variations of PV arrays
	on a base json file with FHS wrapper assumptions.
	
base_fabric
	This case provides an example for creating an alternative base case
	where the fabric heat loss specifications have been overwritten 
	with a simplified fabric package. 
	The simplified fabric approach applies a single heat loss paramter
	for a given fabric component type to all components of the type
	for example all walls will get the same u-value.

base_heatpump
	This case provides an example for creating an altrrnative base case
	where hot water and space heating is provided by a heat pump.

hot_water_test
	This case provides an example for editing hot water related inputs.

direct_elec_test
	This case provides an example for replacing the space ehating system
	with a different direct electric system.

combined_wet_rooms_&_heat_schedule_test
	This case provides an example where 2 wet room count packages and 2 heat schedule packages 
	are varied simultaneously, creating 4 variations on the base case.
