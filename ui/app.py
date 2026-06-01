import json
import sys
from pathlib import Path

import streamlit as st

# Allow imports from ui/utils
CURRENT_DIR = Path(__file__).resolve().parent
UTILS_DIR = CURRENT_DIR / "utils"
sys.path.append(str(UTILS_DIR))

from model_runner import run_hem_model
from results_parser import format_number, read_summary_metrics


st.set_page_config(
    page_title="Home Energy Model Desktop App",
    layout="wide"
)

st.title("Home Energy Model Desktop App")

st.write(
    "Upload a HEM input JSON file, run the HEM engine locally, "
    "and review the result summary."
)

TEMP_DIR = Path("ui/temp")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

input_path = TEMP_DIR / "hem_input.json"
results_dir = TEMP_DIR / "hem_input__results"
summary_path = results_dir / "hem_input__core__results_summary.csv"

weather_file = Path("test/e2e/demo_files/London_weather_CIBSE_format.csv")


st.sidebar.title("HEM Controls")
st.sidebar.info("Upload a HEM input JSON file, then run the model locally.")

uploaded_file = st.file_uploader(
    "Upload HEM input JSON",
    type=["json"]
)

if uploaded_file is None:
    st.warning("Please upload a HEM input JSON file to begin.")
else:
    try:
        input_data = json.load(uploaded_file)

        st.success("Input JSON loaded successfully.")

        with open(input_path, "w", encoding="utf-8") as f:
            json.dump(input_data, f, indent=2)

        st.info(f"Temporary input saved to: {input_path}")

        with st.expander("Preview uploaded JSON", expanded=False):
            st.json(input_data)

        st.subheader("Run HEM model")

        if st.button("Run HEM model"):
            with st.spinner("Running HEM model..."):
                result = run_hem_model(input_path, weather_file)

            if result.returncode == 0:
                st.success("HEM model completed successfully.")

                if summary_path.exists():
                    st.subheader("HEM Results Dashboard")

                    metrics = read_summary_metrics(summary_path)

                    col1, col2, col3 = st.columns(3)

                    with col1:
                        metric = metrics.get("Space heat demand")
                        if metric:
                            st.metric(
                                "Space heat demand",
                                f"{format_number(metric['value'])} {metric['unit']}",
                            )

                    with col2:
                        metric = metrics.get("Space cool demand")
                        if metric:
                            st.metric(
                                "Space cool demand",
                                f"{format_number(metric['value'])} {metric['unit']}",
                            )

                    with col3:
                        metric = metrics.get("Peak electricity consumption")
                        if metric:
                            st.metric(
                                "Peak electricity consumption",
                                f"{format_number(metric['value'])} {metric['unit']}",
                            )

                    summary_text = summary_path.read_text(encoding="utf-8")

                    with st.expander("View full summary CSV", expanded=True):
                        st.text(summary_text)

                    st.download_button(
                        label="Download summary CSV",
                        data=summary_text,
                        file_name="hem_input__core__results_summary.csv",
                        mime="text/csv",
                    )

                else:
                    st.warning(
                        "The model ran, but the expected summary CSV was not found."
                    )

            else:
                st.error("HEM model failed.")
                st.subheader("Error output")
                st.code(result.stderr)

                if result.stdout:
                    st.subheader("Model output")
                    st.code(result.stdout)

    except json.JSONDecodeError:
        st.error("The uploaded file is not valid JSON.")