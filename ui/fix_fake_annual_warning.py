from pathlib import Path

path = Path("ui/pages/10_Run_HEM_Results.py")
text = path.read_text(encoding="utf-8")

old = '''        if simulation_summary["is_annual"]:
            st.success(simulation_summary["message"])
        else:
            st.warning(
                simulation_summary["message"]
                + " Annual-looking KPIs should not be interpreted as annual results."
            )
'''

new = '''        if simulation_summary["is_annual"]:
            st.success(simulation_summary["message"])
        else:
            st.error(
                simulation_summary["message"]
                + " This is a short test-period run, not an annual calculation. "
                "Do not use these values as annual KPIs."
            )

            st.info(
                "To run annual HEM results, the generated JSON must have "
                "SimulationTime.end = 8760 and annual weather arrays with 8760 values."
            )
'''

if old not in text:
    print("Expected block not found. The page may already have been partly patched.")
else:
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
    print("Added hard warning for non-annual simulations.")