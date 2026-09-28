import streamlit as st
from src.styles import apply_page_config, github_link

# Apply configurations and styles
apply_page_config()
github_link("https://github.com/joao-canais/MEDIS-Measurement-System.git")

st.title("MEDIS - High Resolution 3D Measurement System")

st.header("About the Program")

st.markdown("""
**MEDIS** is a Python-based image processing pipeline, currently under development, that detects the **intersection of laser curtains** projected onto fixed targets.
The resulting cross pattern, captured by a USB camera, is analyzed to obtain spatial coordinates (x, y) with **sub-50 µm resolution**.

The pipeline is designed to be integrated into a full **3D Measurement System**, where 4 cameras capturing different planes will enable complete 
**XYZ coordinate** reconstruction — 3 for the vertical axis and 1 for the horizontal axis.
""")

st.header("Sidebar Options")

st.write("""
- **MEDIS**: This introduction page with brief information about the project.
- **Main**: To obtain 3D coordinates from images captured by the camera, in real-time.
- **Calibration**: To obtain calibration coefficients (convert pixels to mm).
- **Debug**: Access to intermediate process functionalities, to check intermediate values (image capture, computation of pixel coordinates (i,j) and millimeter coordinates (x,y)).

Each page includes **instructions** and interactive elements for user input and result visualization.
""")

st.image("files/Tables_Figures/preview_fits.png", width='stretch')