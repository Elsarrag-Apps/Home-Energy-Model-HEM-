from pathlib import Path


# Patch results_parser.py
parser_path = Path("ui/utils/results_parser.py")
text = parser_path.read_text(encoding="utf-8")

if "def extract_delivered_energy_end_use" not in text:
    text += '''


def extract_delivered_energy_end_use(summary_csv_path, end_use_names):
    """Extract delivered energy by end-use from HEM summary CSV."""
    if isinstance(end_use_names, str):
        end_use_names = [end_use_names]

    wanted = {str(name).strip().lower() for name in end_use_names}
    total = 0.0

    try:
        lines = summary_csv_path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return 0.0

    in_delivered_section = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("Delivered energy by end-use"):
            in_delivered_section = True
            continue

        if in_delivered_section and (
            stripped.startswith("Hot water system")
            or stripped.startswith("Space heating system")
            or stripped.startswith("Energy Demand Summary")
            or stripped.startswith("Energy Supply Summary")
        ):
            break

        if not in_delivered_section:
            continue

        parts = [part.strip() for part in line.split(",")]

        if len(parts) < 2:
            continue

        row_name = parts[0].strip().lower()

        if row_name in wanted:
            try:
                total += float(parts[1])
            except ValueError:
                pass

    return total


def extract_hot_water_energy(summary_csv_path):
    """Return approximate DHW-related delivered energy in kWh/m2."""
    return extract_delivered_energy_end_use(
        summary_csv_path,
        [
            "immersion",
            "IES",
            "instant electric shower",
            "hot_water",
            "hot water",
            "dhw",
        ],
    )
'''

parser_path.write_text(text, encoding="utf-8")
print("Patched ui/utils/results_parser.py")


# Patch Run HEM Results page
run_path = Path("ui/pages/10_Run_HEM_Results.py")
text = run_path.read_text(encoding="utf-8")

text = text.replace(
    "from results_parser import compare_summary_metrics, format_number",
    "from results_parser import compare_summary_metrics, extract_hot_water_energy, format_number",
)

text = text.replace(
    "col1, col2, col3, col4, col5 = st.columns(5)",
    "col1, col2, col3, col4, col5, col6 = st.columns(6)",
)

text = text.replace(
    '''                    mech_vent = next(
                        item
                        for item in comparison
                        if item["metric"] == "Mechanical ventilation energy"
                    )
''',
    '''                    mech_vent = next(
                        item
                        for item in comparison
                        if item["metric"] == "Mechanical ventilation energy"
                    )

                    hot_water_generated = extract_hot_water_energy(GENERATED_SUMMARY_PATH)
                    hot_water_baseline = (
                        extract_hot_water_energy(BASE_SUMMARY_PATH)
                        if BASE_SUMMARY_PATH.exists()
                        else 0.0
                    )
                    hot_water_difference = hot_water_generated - hot_water_baseline
''',
)

text = text.replace(
    '''                    with col3:
                        st.metric(
                            "Peak electricity",
                            f"{format_number(peak_elec['generated_value'])} {peak_elec['unit']}",
                            f"{format_number(peak_elec['difference'])} {peak_elec['unit']}",
                        )

                    with col4:
                        st.metric(
                            "Delivered energy",
                            f"{format_number(delivered['generated_value'])} {delivered['unit']}",
                            f"{format_number(delivered['difference'])} {delivered['unit']}",
                        )

                    with col5:
                        st.metric(
                            "Mechanical ventilation",
                            f"{format_number(mech_vent['generated_value'])} {mech_vent['unit']}",
                            f"{format_number(mech_vent['difference'])} {mech_vent['unit']}",
                        )
''',
    '''                    with col3:
                        st.metric(
                            "Hot water energy",
                            f"{format_number(hot_water_generated)} kWh/m2",
                            f"{format_number(hot_water_difference)} kWh/m2",
                        )

                    with col4:
                        st.metric(
                            "Peak electricity",
                            f"{format_number(peak_elec['generated_value'])} {peak_elec['unit']}",
                            f"{format_number(peak_elec['difference'])} {peak_elec['unit']}",
                        )

                    with col5:
                        st.metric(
                            "Delivered energy",
                            f"{format_number(delivered['generated_value'])} {delivered['unit']}",
                            f"{format_number(delivered['difference'])} {delivered['unit']}",
                        )

                    with col6:
                        st.metric(
                            "Mechanical ventilation",
                            f"{format_number(mech_vent['generated_value'])} {mech_vent['unit']}",
                            f"{format_number(mech_vent['difference'])} {mech_vent['unit']}",
                        )
''',
)

run_path.write_text(text, encoding="utf-8")
print("Patched ui/pages/10_Run_HEM_Results.py")
print("Batch X complete.")