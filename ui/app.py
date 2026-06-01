import json
import subprocess
from pathlib import Path

import pandas as pd
import streamlit as st


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
            command = [
                "uv",
                "run",
                "hem-core",
                str(input_path),
                "--CIBSE-weather-file",
                str(weather_file),
            ]

            with st.spinner("Running HEM model..."):
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    shell=False,
                )

            if result.returncode == 0:
                st.success("HEM model completed successfully.")

                if summary_path.exists():
                    st.subheader("HEM Results Summary")

                    summary_text = summary_path.read_text(encoding="utf-8")
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