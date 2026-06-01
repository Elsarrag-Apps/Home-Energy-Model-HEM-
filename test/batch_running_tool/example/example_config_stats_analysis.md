This example config file provides an exmaple for how to set up a config file compatible with the statistical analysis post processing script.

The post processing script, called with the flat --statistical-analysis, relies on a specific format for the config file.
The script will compare two runs of same variation code. For example, if the config is set up as:
        run1 : {package: [var1, var2]},
        run2 : {package: [var1, var2]}
The script will pair run1_0 with run2_0 and run1_1 with run2_1 for comparing.
The statistical analysis post-processing script is reliant on having test runs specified
with a same number of variations and with variations specified in an order that is coherent for all runs.

The config file provides an example where the user may want to compare 2 different heating schedules on the same base case.
With this example, if the user runs the config file through the batch_tool with the flag --statistical-analysis,
the config file will generate 2 test runs:
DE_SH_bi_z1_21_z2_off_01 (with heating schedule package bi_z1_21_z2_off) and DE_SH_bi_z1_21_z2_16_01 (with heating schedule package bi_z1_21_z2_16)
the post processing script will perform statistical tests for comparing these 2 test runs.
