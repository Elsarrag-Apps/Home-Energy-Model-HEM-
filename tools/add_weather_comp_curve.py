#!/usr/bin/env python3

"""
This script adds weather compensation curve inputs.
The input values added are equivalent to the previous hard-coded assumptions.
"""

import sys
import json

for f in sys.argv[1:]:
    with open(f) as json_file:
        inp_dict = json.load(json_file)

    for sh_system in inp_dict["SpaceHeatSystem"].values():
        if sh_system["type"] == "WetDistribution":
            ecodesign_dict = {
                "ecodesign_control_class": sh_system["ecodesign_control_class"],
                "min_outdoor_temp": -4,
                "max_outdoor_temp": 20,
                "min_flow_temp": 30,
            }

            sh_system["ecodesign_controller"] = ecodesign_dict
            ecodesign_dict_1 = sh_system["ecodesign_controller"]
            del sh_system["ecodesign_control_class"]

    with open(f + "_converted.json", "w") as json_file:
        json.dump(inp_dict, json_file, indent=4)
