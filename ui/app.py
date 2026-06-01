import json
from pathlib import Path

import streamlit as st


st.set_page_config(
    page_title="Home Energy Model Desktop App",
    layout="wide"
)

st.title("Home Energy Model Desktop App")

st.write(
    "Upload a HEM input JSON file, preview it, and prepare it for running through the HEM engine."
)

TEMP_DIR = Path("ui/temp")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

input_path = TEMP_DIR / "hem_input.json"


st.sidebar.title("HEM Controls")
st.sidebar.info("First version: upload and preview a HEM input JSON file.")


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

        with st.expander("Preview uploaded JSON", expanded=True):
            st.json(input_data)

        st.subheader("Next action")
        if st.button("Run HEM model"):
            st.warning(
                "The run button is ready, but the HEM command has not been connected yet. "
                "Next step: connect this button to the HEM engine."
            )

    except json.JSONDecodeError:
        st.error("The uploaded file is not valid JSON.")