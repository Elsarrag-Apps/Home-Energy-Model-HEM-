from pathlib import Path

path = Path("ui/pages/7_Hot_Water.py")
text = path.read_text(encoding="utf-8")

text = text.replace(
    'st.header("2. Hot water form")',
    'st.header("2. Hot water system")',
)

text = text.replace(
    'st.subheader("Cylinder / storage tank")',
    'st.subheader("System type, storage and heat source")',
)

text = text.replace(
    '''    c1, c2, c3 = st.columns(3)

    with c1:
        cylinder_volume_litres = st.number_input(
''',
    '''    system_col1, system_col2, system_col3 = st.columns(3)

    with system_col1:
        hot_water_system_type = st.selectbox(
            "Hot water system type",
            [
                "Storage cylinder with immersion heater",
            ],
            index=0,
            help="Current form-generated HEM mapping uses HotWaterSource -> StorageTank with ImmersionHeater.",
        )

        hot_water_source_name = st.text_input(
            "Hot water source name",
            value=saved_form.get("cylinder_name", "hw cylinder"),
        )

        heat_source_type = st.selectbox(
            "Heat source type",
            [
                "Immersion heater",
            ],
            index=0,
            help="Additional HEM hot-water heat source types can be added after schema inspection.",
        )

        cylinder_volume_litres = st.number_input(
''',
)

text = text.replace("with c2:", "with system_col2:", 1)
text = text.replace("with c3:", "with system_col3:", 1)

text = text.replace(
    '''        "cylinder_name": "hw cylinder",
        "immersion_name": "immersion",
''',
    '''        "hot_water_system_type": hot_water_system_type,
        "heat_source_type": heat_source_type,
        "cylinder_name": hot_water_source_name,
        "immersion_name": "immersion",
''',
)

text = text.replace(
    'st.header("3. Hot water input insight")',
    'st.header("3. Hot water system insight")',
)

text = text.replace(
    'st.header("4. Uploaded HEM hot water summary")',
    'st.header("4. Uploaded HEM hot water system summary")',
)

path.write_text(text, encoding="utf-8")
print("Updated Hot Water page labels to show Hot Water System clearly.")