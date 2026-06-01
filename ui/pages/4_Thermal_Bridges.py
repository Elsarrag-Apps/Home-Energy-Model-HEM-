import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="Thermal Bridges",
    layout="wide"
)

st.title("Thermal Bridges")

st.write(
    "Add linear and point thermal bridges. This page calculates thermal bridge "
    "heat-loss coefficients for input checking and visual review. Final model "
    "results will come from the HEM engine."
)

SAP_JUNCTION_DEFAULTS = {
    "Custom / user-defined": None,
    "E1 Steel lintel with perforated steel base plate": 0.50,
    "E2 Other lintel": 0.30,
    "E3 Sill": 0.04,
    "E4 Jamb": 0.05,
    "E5 Ground floor": 0.16,
    "E6 Intermediate floor within dwelling": 0.07,
    "E7 Party floor between dwellings": 0.07,
    "E8 Balcony within wall insulation": 0.02,
    "E9 Balcony outside wall insulation": 0.32,
    "E10 Eaves insulated at ceiling level": 0.06,
    "E11 Eaves insulated at rafter level": 0.04,
    "E12 Gable insulated at ceiling level": 0.24,
    "E13 Gable insulated at rafter level": 0.04,
    "E14 Corner normal": 0.09,
    "E15 Corner inverted": -0.09,
    "E16 Party wall between dwellings": 0.06,
    "E17 Ground floor edge steel/timber frame": 0.32,
}

if "thermal_bridges" not in st.session_state:
    st.session_state["thermal_bridges"] = []

if "thermal_bridges_saved" not in st.session_state:
    st.session_state["thermal_bridges_saved"] = False


st.subheader("Add thermal bridge")

bridge_type = st.selectbox(
    "Bridge type",
    [
        "Linear bridge",
        "Point bridge",
    ],
)

with st.form("add_thermal_bridge_form"):
    col1, col2, col3 = st.columns(3)

    with col1:
        bridge_name = st.text_input(
            "Bridge name / description",
            "Wall-floor junction",
        )

        junction_category = st.selectbox(
            "Junction category",
            list(SAP_JUNCTION_DEFAULTS.keys()),
        )

    with col2:
        default_psi = SAP_JUNCTION_DEFAULTS.get(junction_category)

        if bridge_type == "Linear bridge":
            psi_value = st.number_input(
                "ψ-value (W/mK)",
                value=float(default_psi) if default_psi is not None else 0.16,
                step=0.001,
                format="%.3f",
            )

            length_m = st.number_input(
                "Length (m)",
                min_value=0.0,
                value=10.0,
                step=0.5,
            )

            chi_value = None
            quantity = None

        else:
            chi_value = st.number_input(
                "χ-value (W/K)",
                min_value=0.0,
                value=0.02,
                step=0.001,
                format="%.3f",
            )

            quantity = st.number_input(
                "Quantity",
                min_value=1,
                value=1,
                step=1,
            )

            psi_value = None
            length_m = None

    with col3:
        connected_element = st.selectbox(
            "Connected element / location",
            [
                "External wall",
                "Roof",
                "Ground floor",
                "Window / door opening",
                "Balcony",
                "Party wall",
                "Internal junction",
                "Other",
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
        )

        source = st.selectbox(
            "Value source",
            [
                "Default value",
                "Manufacturer / accredited detail",
                "Project calculation",
                "User-defined",
                "Unknown",
            ],
        )

    notes = st.text_input(
        "Notes / detail reference",
        value="",
        help="Optional reference to detail drawing, calculation note, or assumption.",
    )

    add_bridge = st.form_submit_button("Add thermal bridge")


if add_bridge:
    if bridge_type == "Linear bridge":
        hlc_w_k = psi_value * length_m
        display_value = f"ψ={psi_value:.3f} W/mK × {length_m:.2f} m"
    else:
        hlc_w_k = chi_value * quantity
        display_value = f"χ={chi_value:.3f} W/K × {quantity}"

    st.session_state["thermal_bridges"].append(
        {
            "name": bridge_name,
            "bridge_type": bridge_type,
            "junction_category": junction_category,
            "connected_element": connected_element,
            "boundary_condition": boundary_condition,
            "source": source,
            "psi_value_w_mk": psi_value,
            "length_m": length_m,
            "chi_value_w_k": chi_value,
            "quantity": quantity,
            "calculation": display_value,
            "thermal_bridge_hlc_w_k": hlc_w_k,
            "notes": notes,
        }
    )

    st.session_state["thermal_bridges_saved"] = False
    st.success(f"Added thermal bridge: {bridge_name}")


st.subheader("Thermal bridge list")

if not st.session_state["thermal_bridges"]:
    st.warning("No thermal bridges have been added yet.")
else:
    df = pd.DataFrame(st.session_state["thermal_bridges"])

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )

    total_bridge_hlc = df["thermal_bridge_hlc_w_k"].sum()
    largest_bridge = df.sort_values(
        "thermal_bridge_hlc_w_k",
        ascending=False,
    ).iloc[0]

    fabric_hlc = None
    bridge_share_percent = None

    if "fabric_summary" in st.session_state:
        fabric_hlc = st.session_state["fabric_summary"].get("fabric_hlc_w_k")

        if fabric_hlc and fabric_hlc > 0:
            bridge_share_percent = total_bridge_hlc / (
                total_bridge_hlc + fabric_hlc
            ) * 100

    st.subheader("Thermal bridge summary")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total bridge HLC", f"{total_bridge_hlc:.2f} W/K")

    with col2:
        st.metric(
            "Largest bridge",
            f"{largest_bridge['thermal_bridge_hlc_w_k']:.2f} W/K",
            largest_bridge["name"],
        )

    with col3:
        st.metric(
            "Heat loss at ΔT=21K",
            f"{total_bridge_hlc * 21:.1f} W",
        )

    with col4:
        if bridge_share_percent is not None:
            st.metric(
                "Bridge share of fabric + bridges",
                f"{bridge_share_percent:.1f}%",
            )
        else:
            st.metric(
                "Bridge share of fabric + bridges",
                "N/A",
                "Save fabric inputs first",
            )

    st.subheader("Bridge HLC contribution by junction")

    chart_df = df[["name", "thermal_bridge_hlc_w_k"]].set_index("name")
    st.bar_chart(chart_df)

    st.subheader("Bridge HLC by connected element")

    by_element = (
        df.groupby("connected_element", as_index=False)["thermal_bridge_hlc_w_k"]
        .sum()
        .sort_values("thermal_bridge_hlc_w_k", ascending=False)
    )

    st.bar_chart(by_element.set_index("connected_element"))

    st.subheader("Thermal bridge contribution table")

    df_display = df.copy()
    df_display["share_of_bridge_hlc_percent"] = (
        df_display["thermal_bridge_hlc_w_k"] / total_bridge_hlc * 100
        if total_bridge_hlc > 0
        else 0
    )

    st.dataframe(
        df_display[
            [
                "name",
                "bridge_type",
                "junction_category",
                "connected_element",
                "calculation",
                "thermal_bridge_hlc_w_k",
                "share_of_bridge_hlc_percent",
                "source",
                "notes",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Input checks")

    warnings = []

    if total_bridge_hlc < 0:
        warnings.append("Total bridge HLC is negative. Check inverted junctions.")

    high_bridge_rows = df[df["thermal_bridge_hlc_w_k"] > 5.0]
    if not high_bridge_rows.empty:
        warnings.append(
            "One or more individual thermal bridges exceed 5 W/K. "
            "Check ψ-values and lengths."
        )

    unknown_rows = df[df["source"] == "Unknown"]
    if not unknown_rows.empty:
        warnings.append(
            "Some thermal bridge values are marked as unknown. "
            "Consider replacing these with project-specific or default values."
        )

    if warnings:
        for warning in warnings:
            st.warning(warning)
    else:
        st.success("No obvious thermal bridge input warnings detected.")

    st.subheader("Save thermal bridge inputs")

    col_save, col_clear = st.columns(2)

    with col_save:
        if st.button("Save thermal bridge inputs"):
            st.session_state["thermal_bridges_saved"] = True
            st.session_state["thermal_bridge_summary"] = {
                "total_thermal_bridge_hlc_w_k": total_bridge_hlc,
                "heat_loss_at_21k_w": total_bridge_hlc * 21,
                "largest_bridge_name": largest_bridge["name"],
                "largest_bridge_hlc_w_k": largest_bridge[
                    "thermal_bridge_hlc_w_k"
                ],
                "bridge_share_of_fabric_plus_bridges_percent": bridge_share_percent,
            }
            st.success("Thermal bridge inputs saved.")

    with col_clear:
        if st.button("Clear all thermal bridges"):
            st.session_state["thermal_bridges"] = []
            st.session_state["thermal_bridges_saved"] = False
            st.rerun()

    if st.session_state["thermal_bridges_saved"]:
        st.success("Thermal bridge inputs are currently saved.")
        st.json(st.session_state["thermal_bridge_summary"])