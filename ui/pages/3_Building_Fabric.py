import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="Building Fabric",
    layout="wide"
)

st.title("Building Fabric")

st.write(
    "Add building fabric elements such as walls, roofs, floors, windows and doors. "
    "Opaque external elements include solar absorption and surface properties. "
    "Transparent elements include glazing solar and daylight properties. "
    "The graphics on this page are for input checking; final energy calculations "
    "will come from the HEM engine."
)


OPAQUE_ELEMENTS = [
    "External wall",
    "Roof",
    "Ground floor",
    "Exposed floor",
    "External door",
    "Party wall",
    "Adjacent unconditioned space",
]

TRANSPARENT_ELEMENTS = [
    "Window",
    "Rooflight",
]


def is_opaque_external(element_type: str, boundary_condition: str) -> bool:
    return (
        element_type in OPAQUE_ELEMENTS
        and boundary_condition == "External"
        and element_type not in ["Party wall", "Adjacent unconditioned space"]
    )


def default_solar_absorption(surface_finish: str) -> float:
    values = {
        "Light / reflective finish": 0.35,
        "Medium colour finish": 0.55,
        "Dark brick / dark render": 0.75,
        "Very dark / black roof": 0.90,
        "User-defined": 0.60,
    }
    return values.get(surface_finish, 0.60)


if "fabric_elements" not in st.session_state:
    st.session_state["fabric_elements"] = []

if "fabric_inputs_saved" not in st.session_state:
    st.session_state["fabric_inputs_saved"] = False


st.subheader("Add fabric element")

element_type = st.selectbox(
    "Element type",
    [
        "External wall",
        "Roof",
        "Ground floor",
        "Exposed floor",
        "Window",
        "Rooflight",
        "External door",
        "Party wall",
        "Adjacent unconditioned space",
    ],
)

boundary_condition = st.selectbox(
    "Boundary condition",
    [
        "External",
        "Ground",
        "Adjacent unconditioned space",
        "Party / internal",
    ],
    index=0 if element_type not in ["Ground floor", "Party wall"] else 1,
)

with st.form("add_fabric_element_form"):
    col1, col2, col3 = st.columns(3)

    with col1:
        element_name = st.text_input("Element name", element_type)
        area_m2 = st.number_input(
            "Area (m²)",
            min_value=0.0,
            value=20.0,
            step=0.5,
        )

    with col2:
        u_value = st.number_input(
            "U-value (W/m²K)",
            min_value=0.0,
            value=1.20 if element_type in TRANSPARENT_ELEMENTS else 0.21,
            step=0.01,
            format="%.3f",
        )

        orientation = st.selectbox(
            "Orientation",
            [
                "North",
                "North East",
                "East",
                "South East",
                "South",
                "South West",
                "West",
                "North West",
                "Horizontal",
                "Not applicable",
            ],
            index=4 if element_type in TRANSPARENT_ELEMENTS else 9,
        )

    with col3:
        pitch_degrees = st.number_input(
            "Pitch / tilt (degrees)",
            min_value=0.0,
            max_value=180.0,
            value=30.0 if element_type in ["Roof", "Rooflight"] else 90.0,
            step=1.0,
        )

        element_notes = st.text_input(
            "Notes / construction reference",
            value="",
            help="Optional note, for example construction type, source of U-value, or drawing reference.",
        )

    opaque_data = {}
    glazing_data = {}

    if is_opaque_external(element_type, boundary_condition):
        st.subheader("Opaque external surface properties")

        s1, s2, s3, s4 = st.columns(4)

        with s1:
            surface_finish = st.selectbox(
                "External surface finish",
                [
                    "Light / reflective finish",
                    "Medium colour finish",
                    "Dark brick / dark render",
                    "Very dark / black roof",
                    "User-defined",
                ],
            )

        with s2:
            solar_absorption_coeff = st.number_input(
                "Solar absorption coefficient",
                min_value=0.0,
                max_value=1.0,
                value=default_solar_absorption(surface_finish),
                step=0.01,
                format="%.2f",
                help=(
                    "Absorptance of the external opaque surface. "
                    "Light finishes are lower; dark finishes are higher."
                ),
            )

        with s3:
            areal_heat_capacity = st.number_input(
                "Areal heat capacity (kJ/m²K)",
                min_value=0.0,
                value=75.0,
                step=5.0,
                help="Approximate thermal mass per unit area for input checking.",
            )

        with s4:
            mass_class = st.selectbox(
                "Mass class",
                [
                    "Lightweight",
                    "Medium",
                    "Heavy",
                    "Very heavy",
                    "Unknown",
                ],
                index=1,
            )

        opaque_data = {
            "surface_finish": surface_finish,
            "solar_absorption_coeff": solar_absorption_coeff,
            "areal_heat_capacity_kj_m2k": areal_heat_capacity,
            "mass_class": mass_class,
            "absorbed_solar_index_m2": area_m2 * solar_absorption_coeff,
        }

    else:
        opaque_data = {
            "surface_finish": None,
            "solar_absorption_coeff": None,
            "areal_heat_capacity_kj_m2k": None,
            "mass_class": None,
            "absorbed_solar_index_m2": 0.0,
        }

    if element_type in TRANSPARENT_ELEMENTS:
        st.subheader("Glazing solar and daylight properties")

        g1, g2, g3, g4 = st.columns(4)

        with g1:
            g_value = st.number_input(
                "g-value / solar transmittance",
                min_value=0.0,
                max_value=1.0,
                value=0.63,
                step=0.01,
                format="%.2f",
                help="Solar energy transmittance of the glazing.",
            )

        with g2:
            light_transmittance = st.number_input(
                "Visible light transmittance",
                min_value=0.0,
                max_value=1.0,
                value=0.70,
                step=0.01,
                format="%.2f",
                help="Approximate daylight transmittance of the glazing.",
            )

        with g3:
            frame_factor = st.number_input(
                "Frame factor",
                min_value=0.0,
                max_value=1.0,
                value=0.70,
                step=0.01,
                format="%.2f",
                help="Fraction of window area that is glazed rather than frame.",
            )

        with g4:
            shading_factor = st.number_input(
                "Shading factor",
                min_value=0.0,
                max_value=1.0,
                value=0.90,
                step=0.01,
                format="%.2f",
                help="Reduction factor for shading, blinds, overhangs or obstructions.",
            )

        g5, g6 = st.columns(2)

        with g5:
            openable_fraction = st.number_input(
                "Openable fraction",
                min_value=0.0,
                max_value=1.0,
                value=0.50,
                step=0.05,
                format="%.2f",
                help="Approximate openable portion of the window area.",
            )

        with g6:
            shading_device = st.selectbox(
                "Shading / blind type",
                [
                    "None",
                    "Internal blind",
                    "External shading",
                    "Overhang",
                    "Curtains",
                    "User-defined",
                ],
            )

        glazing_data = {
            "g_value": g_value,
            "visible_light_transmittance": light_transmittance,
            "frame_factor": frame_factor,
            "shading_factor": shading_factor,
            "openable_fraction": openable_fraction,
            "shading_device": shading_device,
            "effective_solar_area_m2": area_m2 * frame_factor * g_value * shading_factor,
            "effective_daylight_area_m2": area_m2
            * frame_factor
            * light_transmittance
            * shading_factor,
        }

    else:
        glazing_data = {
            "g_value": None,
            "visible_light_transmittance": None,
            "frame_factor": None,
            "shading_factor": None,
            "openable_fraction": None,
            "shading_device": None,
            "effective_solar_area_m2": 0.0,
            "effective_daylight_area_m2": 0.0,
        }

    add_element = st.form_submit_button("Add element")


if add_element:
    st.session_state["fabric_elements"].append(
        {
            "name": element_name,
            "type": element_type,
            "boundary_condition": boundary_condition,
            "area_m2": area_m2,
            "u_value_w_m2k": u_value,
            "orientation": orientation,
            "pitch_degrees": pitch_degrees,
            "heat_loss_coefficient_w_k": area_m2 * u_value,
            "notes": element_notes,
            **opaque_data,
            **glazing_data,
        }
    )

    st.session_state["fabric_inputs_saved"] = False
    st.success(f"Added fabric element: {element_name}")


st.subheader("Fabric element list")

if not st.session_state["fabric_elements"]:
    st.warning("No fabric elements have been added yet.")
else:
    df = pd.DataFrame(st.session_state["fabric_elements"])

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )

    total_area = df["area_m2"].sum()
    total_hlc = df["heat_loss_coefficient_w_k"].sum()
    average_u_value = total_hlc / total_area if total_area > 0 else 0

    glazing_df = df[df["type"].isin(TRANSPARENT_ELEMENTS)].copy()
    opaque_external_df = df[
        (df["boundary_condition"] == "External")
        & (df["type"].isin(OPAQUE_ELEMENTS))
    ].copy()

    total_glazing_area = glazing_df["area_m2"].sum() if not glazing_df.empty else 0
    total_effective_solar_area = (
        glazing_df["effective_solar_area_m2"].sum() if not glazing_df.empty else 0
    )
    total_effective_daylight_area = (
        glazing_df["effective_daylight_area_m2"].sum() if not glazing_df.empty else 0
    )
    total_absorbed_solar_index = (
        opaque_external_df["absorbed_solar_index_m2"].sum()
        if not opaque_external_df.empty
        else 0
    )

    st.subheader("Fabric summary")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total fabric area", f"{total_area:.1f} m²")

    with col2:
        st.metric("Fabric HLC", f"{total_hlc:.1f} W/K")

    with col3:
        st.metric("Area-weighted U-value", f"{average_u_value:.3f} W/m²K")

    with col4:
        st.metric("Glazing area", f"{total_glazing_area:.1f} m²")

    st.subheader("Solar and daylight input summary")

    gcol1, gcol2, gcol3, gcol4 = st.columns(4)

    with gcol1:
        st.metric("Opaque absorption index", f"{total_absorbed_solar_index:.2f} m²")

    with gcol2:
        st.metric("Glazing effective solar area", f"{total_effective_solar_area:.2f} m²")

    with gcol3:
        st.metric(
            "Glazing effective daylight area",
            f"{total_effective_daylight_area:.2f} m²",
        )

    with gcol4:
        glazing_ratio = total_glazing_area / total_area * 100 if total_area > 0 else 0
        st.metric("Glazing-to-fabric ratio", f"{glazing_ratio:.1f}%")

    st.subheader("Element heat-loss contribution")

    chart_df = df[["name", "heat_loss_coefficient_w_k"]].set_index("name")
    st.bar_chart(chart_df)

    if not opaque_external_df.empty:
        st.subheader("Opaque surface absorption contribution")

        absorption_chart_df = opaque_external_df[
            ["name", "absorbed_solar_index_m2"]
        ].set_index("name")
        st.bar_chart(absorption_chart_df)

    if not glazing_df.empty:
        st.subheader("Glazing solar contribution")

        solar_chart_df = glazing_df[["name", "effective_solar_area_m2"]].set_index(
            "name"
        )
        st.bar_chart(solar_chart_df)

    st.subheader("Element contribution table")

    df_display = df.copy()
    df_display["share_of_fabric_hlc_percent"] = (
        df_display["heat_loss_coefficient_w_k"] / total_hlc * 100
        if total_hlc > 0
        else 0
    )

    columns_to_show = [
        "name",
        "type",
        "boundary_condition",
        "area_m2",
        "u_value_w_m2k",
        "orientation",
        "pitch_degrees",
        "solar_absorption_coeff",
        "surface_finish",
        "g_value",
        "visible_light_transmittance",
        "frame_factor",
        "shading_factor",
        "heat_loss_coefficient_w_k",
        "absorbed_solar_index_m2",
        "effective_solar_area_m2",
        "effective_daylight_area_m2",
        "share_of_fabric_hlc_percent",
    ]

    st.dataframe(
        df_display[columns_to_show],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Save fabric inputs")

    col_save, col_clear = st.columns(2)

    with col_save:
        if st.button("Save fabric inputs"):
            st.session_state["fabric_inputs_saved"] = True
            st.session_state["fabric_summary"] = {
                "total_fabric_area_m2": total_area,
                "fabric_hlc_w_k": total_hlc,
                "area_weighted_u_value_w_m2k": average_u_value,
                "total_glazing_area_m2": total_glazing_area,
                "opaque_absorption_index_m2": total_absorbed_solar_index,
                "effective_solar_area_m2": total_effective_solar_area,
                "effective_daylight_area_m2": total_effective_daylight_area,
                "glazing_ratio_percent": glazing_ratio,
            }
            st.success("Fabric inputs saved.")

    with col_clear:
        if st.button("Clear all fabric elements"):
            st.session_state["fabric_elements"] = []
            st.session_state["fabric_inputs_saved"] = False
            st.rerun()

    if st.session_state["fabric_inputs_saved"]:
        st.success("Fabric inputs are currently saved.")
        st.json(st.session_state["fabric_summary"])