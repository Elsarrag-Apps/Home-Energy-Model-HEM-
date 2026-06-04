from pathlib import Path


# Patch results_parser.py
path = Path("ui/utils/results_parser.py")
text = path.read_text(encoding="utf-8")

if "def format_small_number" not in text:
    text += '''


def format_small_number(value, decimals=6):
    """Format small energy values without hiding them as 0.000."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "0.000000"

    if abs(value) < 0.001 and value != 0:
        return f"{value:.{decimals}f}"

    return f"{value:.3f}"


def get_simulation_summary_from_case(case_json_path):
    """Return simulation period summary from generated HEM input."""
    import json

    path = Path(case_json_path)

    if not path.exists():
        return {
            "start": None,
            "end": None,
            "step": None,
            "timesteps": 0,
            "is_annual": False,
            "message": "Generated HEM input not found.",
        }

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "start": None,
            "end": None,
            "step": None,
            "timesteps": 0,
            "is_annual": False,
            "message": "Could not read generated HEM input.",
        }

    sim = data.get("SimulationTime", {}) or {}
    external = data.get("ExternalConditions", {}) or {}

    start = sim.get("start")
    end = sim.get("end")
    step = sim.get("step", 1)

    try:
        timesteps = int((float(end) - float(start)) / float(step))
    except Exception:
        timesteps = 0

    weather_lengths = {}

    for key in [
        "air_temperatures",
        "wind_speeds",
        "diffuse_horizontal_radiation",
        "direct_beam_radiation",
    ]:
        value = external.get(key)

        if isinstance(value, list):
            weather_lengths[key] = len(value)

    is_annual = timesteps >= 8760

    if is_annual:
        message = "Annual or near-annual simulation period."
    else:
        message = (
            f"Short test-period simulation: {timesteps} timestep(s). "
            "This is not an annual result."
        )

    return {
        "start": start,
        "end": end,
        "step": step,
        "timesteps": timesteps,
        "is_annual": is_annual,
        "weather_lengths": weather_lengths,
        "message": message,
    }
'''

path.write_text(text, encoding="utf-8")
print("Patched ui/utils/results_parser.py")


# Patch Run HEM Results page
path = Path("ui/pages/10_Run_HEM_Results.py")
text = path.read_text(encoding="utf-8")

text = text.replace(
    "from results_parser import compare_summary_metrics, extract_delivered_energy_rows, extract_hot_water_energy, extract_hot_water_energy_by_names, find_columns_containing, format_number, get_delivered_energy_chart_rows, read_core_results_dataframe",
    "from results_parser import compare_summary_metrics, extract_delivered_energy_rows, extract_hot_water_energy, extract_hot_water_energy_by_names, find_columns_containing, format_number, format_small_number, get_delivered_energy_chart_rows, get_simulation_summary_from_case, read_core_results_dataframe",
)

# Rename results header if present
text = text.replace(
    'st.subheader("Results comparison")',
    'st.subheader("Results comparison for current simulation period")',
)

# Add simulation summary after generated input ready message
old = '''        st.success("Generated HEM input is ready to run.")
'''

new = '''        st.success("Generated HEM input is ready to run.")

        simulation_summary = get_simulation_summary_from_case(GENERATED_FULL_CASE_PATH)

        sim_col1, sim_col2, sim_col3, sim_col4 = st.columns(4)

        with sim_col1:
            st.metric("Simulation timesteps", simulation_summary["timesteps"])

        with sim_col2:
            st.metric("Start", simulation_summary["start"])

        with sim_col3:
            st.metric("End", simulation_summary["end"])

        with sim_col4:
            st.metric("Step", simulation_summary["step"])

        if simulation_summary["is_annual"]:
            st.success(simulation_summary["message"])
        else:
            st.warning(
                simulation_summary["message"]
                + " Annual-looking KPIs should not be interpreted as annual results."
            )

        with st.expander("Weather array lengths", expanded=False):
            st.json(simulation_summary.get("weather_lengths", {}))
'''

if old in text and "Simulation timesteps" not in text:
    text = text.replace(old, new, 1)

# Improve MVHR small-value formatting
text = text.replace(
    '''                            f"{format_number(mech_vent['generated_value'])} {mech_vent['unit']}",
                            f"{format_number(mech_vent['difference'])} {mech_vent['unit']}",
''',
    '''                            f"{format_small_number(mech_vent['generated_value'])} {mech_vent['unit']}",
                            f"{format_small_number(mech_vent['difference'])} {mech_vent['unit']}",
''',
)

path.write_text(text, encoding="utf-8")
print("Patched ui/pages/10_Run_HEM_Results.py")

print("Batch Y2 complete.")