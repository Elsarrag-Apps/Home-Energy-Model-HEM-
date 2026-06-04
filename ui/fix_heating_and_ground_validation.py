from pathlib import Path

# ------------------------------------------------------------
# 1. Patch hvac_mapper.py
# ------------------------------------------------------------
path = Path("ui/utils/hvac_mapper.py")
text = path.read_text(encoding="utf-8")

# Remove invalid Zone field from generated InstantElecHeater
text = text.replace(
    '''            "EnergySupply": heating_data.get("direct_electric_energy_supply", "mains elec"),
            "Zone": zone_name,
''',
    '''            "EnergySupply": heating_data.get("direct_electric_energy_supply", "mains elec"),
''',
)

path.write_text(text, encoding="utf-8")
print("Patched hvac_mapper.py: removed invalid Zone field from InstantElecHeater.")


# ------------------------------------------------------------
# 2. Patch Heating & Cooling page defaults
# ------------------------------------------------------------
path = Path("ui/pages/6_Heating_Cooling_Systems.py")
text = path.read_text(encoding="utf-8")

# Heat pump COP: guard saved value so 0.0 does not crash the widget
text = text.replace(
    '''            heat_pump_nominal_cop = st.number_input(
                "Nominal COP",
                min_value=0.1,
                value=float(saved_heating_form.get("heat_pump_nominal_cop", 3.2)),
                step=0.1,
            )
''',
    '''            saved_hp_cop = float(saved_heating_form.get("heat_pump_nominal_cop", 3.2) or 3.2)
            if saved_hp_cop < 0.1:
                saved_hp_cop = 3.2

            heat_pump_nominal_cop = st.number_input(
                "Nominal COP",
                min_value=0.1,
                value=saved_hp_cop,
                step=0.1,
            )
''',
)

# Cooling COP: same guard in case previous saved value is zero
text = text.replace(
    '''        cooling_cop = st.number_input(
            "Cooling COP / EER",
            min_value=0.0,
            value=float(saved_cooling.get("cooling_cop", 3.0)),
            step=0.1,
        )
''',
    '''        saved_cooling_cop = float(saved_cooling.get("cooling_cop", 3.0) or 3.0)

        cooling_cop = st.number_input(
            "Cooling COP / EER",
            min_value=0.0,
            value=saved_cooling_cop,
            step=0.1,
        )
''',
)

path.write_text(text, encoding="utf-8")
print("Patched Heating & Cooling page: guarded COP defaults.")


# ------------------------------------------------------------
# 3. Patch full_case_builder.py with final ground-floor sanitizer
# ------------------------------------------------------------
path = Path("ui/utils/full_case_builder.py")
text = path.read_text(encoding="utf-8")

if "def clean_ground_elements_in_case" not in text:
    insert_after = '''def clean_transparent_elements_in_case(hem_input: dict) -> dict:
    """Remove fields rejected by HEM for BuildingElementTransparent."""
    zones = hem_input.get("Zone", {})

    if not isinstance(zones, dict):
        return hem_input

    for zone in zones.values():
        if not isinstance(zone, dict):
            continue

        elements = zone.get("BuildingElement", {})

        if not isinstance(elements, dict):
            continue

        for element in elements.values():
            if not isinstance(element, dict):
                continue

            if element.get("type") == "BuildingElementTransparent":
                element.pop("area", None)
                element.pop("areal_heat_capacity", None)
                element.pop("mass_distribution_class", None)
                element.pop("solar_absorption_coeff", None)

    return hem_input
'''

    block = insert_after + '''


def clean_ground_elements_in_case(hem_input: dict) -> dict:
    """Protect HEM validation from invalid generated ground-floor resistance values.

    HEM rejects ground floors where the derived r_vi becomes <= 0. This can happen
    when the simplified fabric UI writes an inconsistent u_value and
    thermal_resistance_floor_construction combination. For now, if a ground element
    has both values and they are clearly inconsistent, remove the explicit u_value
    and let HEM use the construction inputs.
    """
    zones = hem_input.get("Zone", {})

    if not isinstance(zones, dict):
        return hem_input

    for zone in zones.values():
        if not isinstance(zone, dict):
            continue

        elements = zone.get("BuildingElement", {})

        if not isinstance(elements, dict):
            continue

        for element_name, element in elements.items():
            if not isinstance(element, dict):
                continue

            if element.get("type") != "BuildingElementGround":
                continue

            u_value = element.get("u_value")
            r_floor = element.get("thermal_resistance_floor_construction")

            try:
                u_value_f = float(u_value)
                r_floor_f = float(r_floor)
            except (TypeError, ValueError):
                continue

            if u_value_f <= 0:
                element.pop("u_value", None)
                continue

            # If 1/U is less than or equal to the supplied construction resistance,
            # HEM's derived internal resistance can become zero or negative.
            if (1.0 / u_value_f) <= r_floor_f:
                element.pop("u_value", None)

    return hem_input
'''

    if insert_after not in text:
        raise RuntimeError("Could not find clean_transparent_elements_in_case block.")

    text = text.replace(insert_after, block, 1)

if "hem_input = clean_ground_elements_in_case(hem_input)" not in text:
    text = text.replace(
        '''    hem_input = clean_transparent_elements_in_case(hem_input)

    save_json(output_json_path, hem_input)
''',
        '''    hem_input = clean_transparent_elements_in_case(hem_input)
    hem_input = clean_ground_elements_in_case(hem_input)

    save_json(output_json_path, hem_input)
''',
        1,
    )

path.write_text(text, encoding="utf-8")
print("Patched full_case_builder.py: added final ground-floor sanitizer.")

print("Fix complete.")