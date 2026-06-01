# Impact assessment

The impact assessment scripts are found in the post_processing folder.
They were developed to compare results between different versions of HEM.

### collect_impact_assessment_results.py <br>
This script provides a stand-alone tool for processing impact assessment result files by coordinating various scripts.<br>
### reformat_data_historic_results.py<br>
This scripts standardises outputs and combines all the result files into single results file with additional columns for each archetype and commit ID. <br>
"archetype" describes the building archetype used for the model, i.e. the filename given to the JSON files that are ran through HEM. "commit ID" refers to the commit ID of the HEM version the archetypes were ran through. <br>
- _results.csv files will be aggregated into an output CSV file called "all_results.csv" saved in the results folder.<br>
- _results_heat_balance_air_node.csv files will be aggregated into an output CSV file called "all_heat_balance_air_node_results.csv"<br>
- _results_heat_balance_external_boundary.csv files will be aggregated into an output CSV file called "all_heat_balance_external_results.csv"<br>
### impact_assessment_figures.py<br>
This script processes standardised outputs into annual reports (CSV format) and plots (PNG format). See "Outputs" section below for the detailed list of outputs.<br>

## How to run

The virtual environment must be activated as set out in the README.md file at the top of the working directory under section “Installing dependencies”. <br>

The script to be called is collect_impact_assessment_results.py <br>
The script takes the following required arguments:
- path to the input folder containing sub-folders of results to process. See section "Input folder structure" below.
- path to a CSV file containing a summary of which HEM versions are associated with the results from the input folder. See section "CSV file with descriptions of commit IDs and engine versions".<br>

The example command below will process results for JSON files called DE.json, DA.json, or VF.json found in the folder: test/impact_testing/core/ <br>
and will classify the results following the commit id description file: test/impact_testing/core/base_archetypes_commit_id_descriptions.csv 

### RHEL 7 / CentOS 7:
```
python3 test/batch_running_tool/post_processing/collect_impact_assessment_results.py test/impact_testing/core/ test/impact_testing/core/base_archetypes_commit_id_descriptions.csv DE DA VF
```

### Windows 10:
```
python test\batch_running_tool\post_processing\collect_impact_assessment_results.py test\impact_testing\core\ test\impact_testing\core\base_archetypes_commit_id_descriptions.csv DE DA VF
```

## Input folder structure

Required folder structure for input files:
```
folder-path/
    {commit_id_1}/
        {archetype_1.json}
        {archetype_2.json}
        {archetype_1}__results/
            {archetype_1}__core__results_heat_balance_air_node.csv
            {archetype_1}__core__results_heat_balance_external_boundary.csv
            {archetype_1}__core__results_heat_balance_internal_boundary.csv
        {archetype_2}__results/
            {archetype_2}__core__results_heat_balance_air_node.csv
            {archetype_2}__core__results_heat_balance_external_boundary.csv
            {archetype_2}__core__results_heat_balance_internal_boundary.csv
```

## CSV file with descriptions of commit IDs and engine versions
The file must have the following columns:
***commit_id, test_suite_id, chronology, date, description***

Where:
- Values in the ***commit_id*** column must match a sub-folder name at the input folder location (for example commit_id_1 in the example below).
- Values in the ***test_suite_id*** column can collect a unique code chosen by the user to describe the commit ID in a user-friendly way. 
- Values in the ***chronology*** column must be integers, and will represent the order in which results will be displayed on output figures.
- Values in the ***date*** column should record the commit ID date (HEM version date) in the format YYYY-MM-DD
- The ***description*** column can hold a brief text description of the specificites of the engine version.

For example, if you wish to run and compare a file through HEM v0.24 (commit ID: 7b619b5e) and HEM v0.28 (commit ID: b01f46ac), you may wish to set your commit ID description CSV as follows:<br>
*7b619b5e, HEM v0.24, 1, 2023-12-13, HEM version at the start of HEM consultation*<br>
*b01f46ac, HEM v0.24, 2, 2024-03-01, HEM version at the end of HEM consultation (includes WWHRS fix and PV solar fix)*<br>


## Outputs
The script will create a results folder at the same location as the input commit ID descriptions CSV, named after the input CSV file but ending with __results.

The results folder will collect:
- the master dataframes created from all result CSVs, all air node heat balance CSVs and all external boundary heat balance CSVs respectively:
  - all_results_df.csv
  - all_heat_balance_air_node_results_df.csv
  - all_heat_balance_external_results_df.csv
- CSV files for annual summaries:
  - annual_energy.csv
  - annual_energy_net_change.csv
  - annual_heat_balance_air_node.csv
  - annual_heat_balance_external_boundary.csv
- stacked bar charts for:
  - annual energy use by end-use, per archetype: annual_energy_use_{archetype}.png
  - annual heat balance at air node, per archetype: annual_heat_balance_air_node_{archetype}.png
  - annual heat balance at external boundary, per archetype: annual_heat_balance_external_boundary_{archetype}.png
  - monthly heat balance at air node, per archetype: monthly_heat_balance_air_node_{archetype}.png
  - monthly heat balance at external boundary, per archetype: monthly_heat_balance_external_boundary_{archetype}.png
- simple bar charts for annual space heating and hot water demand, per archetype: annual_SH_DHW_demand_{archetype}.png