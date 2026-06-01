#!/usr/bin/env python3

"""
This script adds heater and thermostat position inputs (now required) to
files that do not have them. The input values added are equivalent to
the previous hard-coded assumptions.
"""

import sys
import json

for f in sys.argv[1:]:
    with open(f) as json_file:
        inp_dict = json.load(json_file)

    for wh_data in inp_dict["HotWaterSource"].values():
        for heat_source_data in wh_data["HeatSource"].values():
            heat_source_data["heater_position"] = 0.0
            heat_source_data["thermostat_position"] = 1.0 / 3.0

    with open(f + "_converted.json", "w") as json_file:
        json.dump(inp_dict, json_file, indent=4)
