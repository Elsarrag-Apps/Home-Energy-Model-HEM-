# -*- coding: utf-8 -*-
from pathlib import Path

RUN_PAGE = Path("ui/pages/10_Run_HEM_Results.py")

if not RUN_PAGE.exists():
    raise FileNotFoundError(RUN_PAGE)

text = RUN_PAGE.read_text(encoding="utf-8")


# ---------------------------------------------------------------------
# 1. Add helper functions for existing result detection and hot-water cols
# ---------------------------------------------------------------------
helper_code = r'''

def get_existing_result_files(results_dir: Path) -> dict:
    """Return known HEM result files if they exist."""
    if not results_dir.exists():
        return {}

    summary_files = list(results_dir.glob("*__results_summary.csv"))
    timestep_files = list(results_dir.glob("*__results.csv"))
    static_files = list(results_dir.glob("*__results_static.csv"))

    return {
        "summary": summary_files[0] if summary_files else None,
        "timestep": timestep_files[0] if timestep_files else None,
        "static": static_files[0] if static_files else None,
    }


def has_existing_results(results_dir: Path) -> bool:
    files = get_existing_result_files(results_dir)
    return bool(files.get("summary") and files.get("timestep"))


def select_hot_water_profile_columns(columns) -> list[str]:
    """Select useful hot-water plotting columns only.

    This avoids plotting event-count/duration columns together with kWh/volume columns,
    which makes annual hot-water charts look flat or meaningless.
    """
    selected = []

    include_terms = [
        "hot water energy demand",
        "hot water volume required",
        "storage losses",
        "distribution pipework losses",
        "primary pipework losses",
    ]

    exclude_terms = [
        "number of events",
        "total event duration",
        "_electric_showers",
    ]

    for col in columns:
        lower = col.lower()

        if any(term in lower for term in exclude_terms):
            continue

        if any(term in lower for term in include_terms):
            selected.append(col)

    return selected


def numeric_timestep_dataframe(csv_path: Path):
    import pandas as pd

    df = pd.read_csv(csv_path)
    if "Timestep" not in df.columns:
        return df

    mask = pd.to_numeric(df["Timestep"], errors="coerce").notna()
    df = df.loc[mask].copy()
    df["Timestep"] = pd.to_numeric(df["Timestep"], errors="coerce").astype(int)

    for col in df.columns:
        if col != "Timestep":
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df
'''

if "def get_existing_result_files" not in text:
    # Insert after imports. We place after the final import-like line near the top.
    marker = "st.set_page_config"
    idx = text.find(marker)
    if idx == -1:
        text = helper_code + "\n\n" + text
    else:
        text = text[:idx] + helper_code + "\n\n" + text[idx:]


# ---------------------------------------------------------------------
# 2. Add existing-results notification near Run section if possible
# ---------------------------------------------------------------------
# We add a small block after GENERATED_FULL_CASE_PATH is likely defined.
status_block = r'''
# Existing result detection for persistence across page navigation.
GENERATED_RESULTS_DIR = Path("ui/temp/generated_full_project_case__results")
existing_result_files = get_existing_result_files(GENERATED_RESULTS_DIR)
existing_results_available = has_existing_results(GENERATED_RESULTS_DIR)
'''

if "existing_results_available = has_existing_results" not in text:
    marker = "GENERATED_FULL_CASE_PATH"
    pos = text.find(marker)
    if pos != -1:
        line_end = text.find("\n", pos)
        text = text[:line_end + 1] + status_block + "\n" + text[line_end + 1:]
    else:
        text = status_block + "\n" + text


# ---------------------------------------------------------------------
# 3. Add a visible load-existing-results message before run button area
# ---------------------------------------------------------------------
load_block = r'''
if existing_results_available:
    st.info(
        "Previous HEM results are available and will remain visible until a new run overwrites them."
    )
'''

if "Previous HEM results are available" not in text:
    marker = 'st.header("5. Run HEM and compare results")'
    pos = text.find(marker)
    if pos != -1:
        line_end = text.find("\n", pos)
        text = text[:line_end + 1] + "\n" + load_block + "\n" + text[line_end + 1:]


# ---------------------------------------------------------------------
# 4. Persist run success in session_state where result.returncode == 0 occurs
# ---------------------------------------------------------------------
if 'st.session_state["last_hem_results_dir"]' not in text:
    text = text.replace(
        'st.success("HEM run completed successfully.")',
        'st.success("HEM run completed successfully.")\n'
        '            st.session_state["last_hem_results_dir"] = str(GENERATED_RESULTS_DIR)\n'
        '            st.session_state["last_hem_run_success"] = True',
        1,
    )


# ---------------------------------------------------------------------
# 5. Patch chart hot-water column selection if page uses broad selector
# ---------------------------------------------------------------------
# This is intentionally conservative: if exact old code is not found, we add helper only.
text = text.replace(
    '[c for c in results_df.columns if "hot water" in c.lower() or "hw cylinder" in c.lower() or "shower" in c.lower() or "bath" in c.lower()]',
    'select_hot_water_profile_columns(results_df.columns)',
)

text = text.replace(
    '[c for c in df.columns if "hot water" in c.lower() or "hw cylinder" in c.lower() or "shower" in c.lower() or "bath" in c.lower()]',
    'select_hot_water_profile_columns(df.columns)',
)


# ---------------------------------------------------------------------
# 6. Add fallback display of previous summary if no new result block is active
# ---------------------------------------------------------------------
fallback_block = r'''

# Fallback: show previous HEM results after page navigation if files exist.
if existing_results_available and not st.session_state.get("last_hem_results_rendered_this_pass", False):
    with st.expander("View previous HEM summary output", expanded=False):
        summary_path = existing_result_files.get("summary")
        if summary_path and summary_path.exists():
            st.text(summary_path.read_text(encoding="utf-8", errors="ignore"))

    timestep_path = existing_result_files.get("timestep")
    if timestep_path and timestep_path.exists():
        try:
            prev_df = numeric_timestep_dataframe(timestep_path)
            st.subheader("Previous hourly / timestep results")

            tab_energy, tab_temp, tab_hw, tab_raw = st.tabs(
                ["Energy profiles", "Zone temperatures", "Hot water profiles", "Raw timestep data"]
            )

            with tab_energy:
                energy_cols = [
                    c for c in prev_df.columns
                    if c != "Timestep"
                    and (
                        "mains elec:" in c.lower()
                        or "space heat demand" in c.lower()
                        or "space cool demand" in c.lower()
                    )
                ]
                if energy_cols:
                    st.line_chart(prev_df.set_index("Timestep")[energy_cols])
                else:
                    st.info("No energy profile columns found in previous results.")

            with tab_temp:
                temp_cols = [c for c in prev_df.columns if "temp" in c.lower()]
                if temp_cols:
                    st.line_chart(prev_df.set_index("Timestep")[temp_cols])
                else:
                    st.info("No temperature columns found in previous results.")

            with tab_hw:
                hw_cols = select_hot_water_profile_columns(prev_df.columns)
                if hw_cols:
                    st.line_chart(prev_df.set_index("Timestep")[hw_cols])
                    with st.expander("Hot water column totals", expanded=False):
                        st.dataframe(prev_df[hw_cols].sum(numeric_only=True).sort_values(ascending=False))
                else:
                    st.info("No non-zero hot-water profile columns found in previous results.")

            with tab_raw:
                st.dataframe(prev_df, width="stretch")

        except Exception as exc:
            st.warning(f"Previous timestep results could not be loaded: {exc}")
'''

if "Fallback: show previous HEM results after page navigation" not in text:
    text = text + "\n" + fallback_block + "\n"


RUN_PAGE.write_text(text, encoding="utf-8")
print("Applied AD1/AD2: result persistence helpers and hot-water profile filtering.")