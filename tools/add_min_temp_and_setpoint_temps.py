#!/usr/bin/env python3

"""
This script adds minimum and setpoint temperatures inputs (now required) to
files that do not have them. The input values added are equivalent to
the previous hard-coded assumptions.
"""

import sys
import json

for f in sys.argv[1:]:
    with open(f) as json_file:
        inp_dict = json.load(json_file)

    for wh_data in inp_dict["HotWaterSource"].values():
        if wh_data["type"] == "StorageTank":
            wh_data["min_temp"] = 52.0
            wh_data["setpoint_temp"] = 55.0

    with open(f + "_converted.json", "w") as json_file:
        json.dump(inp_dict, json_file, indent=4)
