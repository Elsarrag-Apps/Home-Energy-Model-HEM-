#!/bin/python3

"""
This script converts input files that define setpoints per zone to define
equivalent setpoint schedules, which is now required.
"""

import sys
import json


def convert_onoff_to_setpoint_timecontrol(ctrl_dict, setpoint_on, setpoint_off):
    # Create new control object for each system/zone, with same on/off pattern but in terms of setpoints
    schedule = {}
    for subschedule_name, subschedule in ctrl_dict["schedule"].items():
        new_subschedule = []
        for sched_entry in subschedule:
            if isinstance(sched_entry, bool):
                if sched_entry:
                    new_subschedule.append(setpoint_on)
                else:
                    new_subschedule.append(setpoint_off)
            elif isinstance(sched_entry, dict):
                if isinstance(sched_entry["value"], bool):
                    if sched_entry["value"]:
                        value = setpoint_on
                    else:
                        value = setpoint_off
                else:
                    value = sched_entry["value"]
                new_subschedule.append({"value": value, "repeat": sched_entry["repeat"]})
            elif isinstance(sched_entry, str):
                new_subschedule.append(sched_entry)

        schedule[subschedule_name] = new_subschedule

    new_ctrl_dict = {
        "type": "SetpointTimeControl",
        "start_day": ctrl_dict["start_day"],
        "time_series_step": ctrl_dict["time_series_step"],
        "schedule": schedule,
    }
    return new_ctrl_dict


for f in sys.argv[1:]:
    with open(f) as json_file:
        inp_dict = json.load(json_file)

    for z_name, z_data in inp_dict["Zone"].items():
        # Get setpoint from each zone
        if "temp_setpnt_heat" in z_data.keys():
            setpoint_heat_on = z_data["temp_setpnt_heat"]
            del z_data["temp_setpnt_heat"]
        if "temp_setpnt_cool" in z_data.keys():
            setpoint_cool_on = z_data["temp_setpnt_cool"]
            del z_data["temp_setpnt_cool"]

        # Get names of heating systems serving each zone
        # Get names of controls used by each heating/cooling system
        # Create new control object for each system/zone, with same on/off pattern but in terms of setpoints
        # Set name of control object in each system
        if "SpaceHeatSystem" in z_data.keys():
            h_name = z_data["SpaceHeatSystem"]
            if "Control" in inp_dict["SpaceHeatSystem"][h_name]:
                h_ctrl_name = inp_dict["SpaceHeatSystem"][h_name]["Control"]
                new_h_ctrl_name = h_name + "__" + h_ctrl_name + "__converted_from_OnOffTimeControl"
                inp_dict["SpaceHeatSystem"][h_name]["Control"] = new_h_ctrl_name
                inp_dict["Control"][new_h_ctrl_name] = convert_onoff_to_setpoint_timecontrol(
                    inp_dict["Control"][h_ctrl_name],
                    setpoint_heat_on,
                    -273.15,
                )
            else:
                new_h_ctrl_name = h_name + "__new_SetpointControl"
                inp_dict["SpaceHeatSystem"][h_name]["Control"] = new_h_ctrl_name
                inp_dict["Control"][new_h_ctrl_name] = {
                    "type": "SetpointTimeControl",
                    "start_day": 0,
                    "time_series_step": 1,
                    "schedule": {
                        "main": [{"repeat": 8760, "value": setpoint_heat_on}],
                    },
                }
        if "SpaceCoolSystem" in z_data.keys():
            c_name = z_data["SpaceCoolSystem"]
            if "Control" in inp_dict["SpaceCoolSystem"][c_name]:
                c_ctrl_name = inp_dict["SpaceCoolSystem"][c_name]["Control"]
                c_ctrl_name = inp_dict["SpaceCoolSystem"][c_name]["Control"]
                new_c_ctrl_name = c_name + "__" + c_ctrl_name + "__converted_from_OnOffTimeControl"
                inp_dict["SpaceCoolSystem"][c_name]["Control"] = new_c_ctrl_name
                inp_dict["Control"][new_c_ctrl_name] = convert_onoff_to_setpoint_timecontrol(
                    inp_dict["Control"][c_ctrl_name],
                    setpoint_cool_on,
                    1.4e32,
                )
            else:
                new_c_ctrl_name = c_name + "__new_SetpointControl"
                inp_dict["SpaceCoolSystem"][c_name]["Control"] = new_c_ctrl_name
                inp_dict["Control"][new_c_ctrl_name] = {
                    "type": "SetpointTimeControl",
                    "start_day": 0,
                    "time_series_step": 1,
                    "schedule": {
                        "main": [{"repeat": 8760, "value": setpoint_cool_on}],
                    },
                }

    with open(f + "_converted.json", "w") as json_file:
        json.dump(inp_dict, json_file, indent=4)
