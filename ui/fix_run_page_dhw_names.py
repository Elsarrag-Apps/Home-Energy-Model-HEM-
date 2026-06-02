from pathlib import Path

path = Path("ui/pages/10_Run_HEM_Results.py")
text = path.read_text(encoding="utf-8")

text = text.replace(
    "from results_parser import compare_summary_metrics, extract_hot_water_energy, format_number",
    "from results_parser import compare_summary_metrics, extract_delivered_energy_rows, extract_hot_water_energy, extract_hot_water_energy_by_names, format_number",
)

marker = '''project_data = active_project.get("project_data", {})
project_setup = project_data.get("project_setup", {})
'''

helper = '''project_data = active_project.get("project_data", {})
project_setup = project_data.get("project_setup", {})


def get_dhw_end_use_names_from_generated_case(generated_case_path: Path) -> list[str]:
    """Identify likely DHW end-use rows from generated HEM HotWaterSource."""
    names = ["immersion", "IES", "instant electric shower"]

    if not generated_case_path.exists():
        return names

    try:
        generated = json.loads(generated_case_path.read_text(encoding="utf-8"))
    except Exception:
        return names

    hot_water_sources = generated.get("HotWaterSource", {})

    if not isinstance(hot_water_sources, dict):
        return names

    for source_name, source in hot_water_sources.items():
        if isinstance(source, dict):
            names.append(source_name)

            heat_sources = source.get("HeatSource", {})
            if isinstance(heat_sources, dict):
                for heat_source_name in heat_sources.keys():
                    names.append(heat_source_name)

    seen = set()
    clean_names = []

    for name in names:
        key = str(name).strip().lower()
        if key and key not in seen:
            seen.add(key)
            clean_names.append(str(name).strip())

    return clean_names

'''

if "def get_dhw_end_use_names_from_generated_case" not in text:
    text = text.replace(marker, helper, 1)

old = '''                    hot_water_generated = extract_hot_water_energy(GENERATED_SUMMARY_PATH)
                    hot_water_baseline = (
                        extract_hot_water_energy(BASE_SUMMARY_PATH)
                        if BASE_SUMMARY_PATH.exists()
                        else 0.0
                    )
                    hot_water_difference = hot_water_generated - hot_water_baseline
'''

new = '''                    dhw_end_use_names = get_dhw_end_use_names_from_generated_case(
                        GENERATED_FULL_CASE_PATH
                    )

                    hot_water_generated = extract_hot_water_energy_by_names(
                        GENERATED_SUMMARY_PATH,
                        dhw_end_use_names,
                    )

                    hot_water_baseline = (
                        extract_hot_water_energy_by_names(
                            BASE_SUMMARY_PATH,
                            dhw_end_use_names,
                        )
                        if BASE_SUMMARY_PATH.exists()
                        else 0.0
                    )

                    hot_water_difference = hot_water_generated - hot_water_baseline
'''

if old in text:
    text = text.replace(old, new, 1)

old2 = '''                with st.expander("View full HEM summary output", expanded=False):
                    st.text(summary_text)
'''

new2 = '''                with st.expander("Delivered energy by end-use", expanded=False):
                    delivered_rows = extract_delivered_energy_rows(GENERATED_SUMMARY_PATH)

                    if delivered_rows:
                        st.dataframe(
                            delivered_rows,
                            use_container_width=True,
                            hide_index=True,
                        )
                    else:
                        st.write("No delivered-energy end-use rows found.")

                    st.caption(
                        "Hot water energy is estimated from the generated HotWaterSource "
                        "heat-source names plus common DHW rows such as IES and immersion."
                    )

                with st.expander("View full HEM summary output", expanded=False):
                    st.text(summary_text)
'''

if old2 in text:
    text = text.replace(old2, new2, 1)

path.write_text(text, encoding="utf-8")
print("Patched Run HEM page for DHW end-use names and delivered-energy table.")