"""
Module with all Streamlit application CSS styles.
Purely for aesthetics, not functionality (ignore).
"""

import streamlit as st
from pathlib import Path
import base64

def _load_stylesheet():
    """Loads the shared stylesheet used by the Streamlit page and iframes."""

    stylesheet_file = Path(__file__).with_name("styles.css")
    return stylesheet_file.read_text(encoding="utf-8")

def base_style():
    """Return base CSS styles."""
    
    style = """
    <style>
    .block-container {
        max-width: 1000px;
        padding-left: 2rem;
        padding-right: 2rem;
    }
    """
    st.markdown(style, unsafe_allow_html=True)
    
def tab_style():
    """Return CSS styles for tabs."""    
    style = """
    <style>
    .stTabs [role="tablist"] [role="tab"],
    .stTabs [data-baseweb="tab-list"] [data-baseweb="tab"] {
        margin-right: 0.5rem !important;
        padding: 0.5rem 1rem !important;
    }
    /* Hover - more specific */
    .stTabs [role="tablist"] [role="tab"]:hover,
    .stTabs [data-baseweb="tab-list"] [data-baseweb="tab"]:hover {
        color: #00FFC6 !important;
    }

    /* Selected tab - more specific */
    .stTabs [role="tablist"] [role="tab"][aria-selected="true"],
    .stTabs [data-baseweb="tab-list"] [data-baseweb="tab"][aria-selected="true"] {
        color: #ffffff !important;
    }

    /* Sliding bar (active tab indicator) */
    .stTabs [data-baseweb="tab-highlight"],
    .stTabs [data-testid="stTabHighlight"],
    .stTabs [data-testid="stTab"] > .react-aria-SelectionIndicator {
        background: #00FFC6 !important;
        background-color: #00FFC6 !important;
        border-color: #00FFC6 !important;
    }
    </style>
    """
    st.markdown(style, unsafe_allow_html=True)
    
def file_uploader_style():
    """Return CSS style for a custom file uploader."""
    style = """
    <style>
    /* Completely remove dropzone background */
    .stFileUploader section[data-testid="stFileUploaderDropzone"] {
        background: none !important;
        border: none !important;
        padding: 0 !important;
        min-height: auto !important;
    }

    /* Hide internal elements (text, icons, etc.) */
    .stFileUploader section[data-testid="stFileUploaderDropzone"] div {
        display: none !important;
    }

    /* Button style - similar to Streamlit default */
    .stFileUploader button {
        background: #171717 !important;
        color: #FAFAFA !important;
        border: 1px solid #454750 !important;
        border-radius: rem !important;
        padding: 0.5rem 1rem !important;
        font-size: 1rem !important;
        font-weight: 400 !important;
        cursor: pointer !important;
        width: 120px !important;
        height: 30px !important;
        transition: all 0.3s ease !important;
    }

    .stFileUploader section[data-testid="stFileUploaderDropzone"] button::after {
        content: "Browse files";
        font-size: 1rem;
    }

    /* Button hover */
    .stFileUploader button:hover {
        background: #454750 !important;
        border-color: #666 !important;
    }
    </style>
    """
    st.markdown(style, unsafe_allow_html=True)
    
def expander_style():
    """Return styles for expanders."""
    style = """
    <style>
    # /* Hover effect on expander */
    # .stExpander:hover {
    #     color: #00FFC6 !important;
    #     transition: all 0.3s ease !important;
    # }
    
    .stExpander > details > summary:hover {
        color: #00FFC6 !important;
    }
    
    /* Arrow color on hover - using the same base selector */
    .stExpander > details > summary:hover svg {
        fill: #00FFC6 !important;
        # color: #00FFC6 !important;
    }
    
    </style>
    """
    st.markdown(style, unsafe_allow_html=True)
      
def apply_page_config():
    """Applies basic page configuration, logo, and layout tweaks."""
    
    # Set page logo
    logo_file = Path(__file__).resolve().parent.parent / "files" / "Tables_Figures" / "logo.svg"
    
    if logo_file.is_file():
        svg_bytes = logo_file.read_bytes()
        svg_b64 = base64.b64encode(svg_bytes).decode("utf-8")
        icon = f"data:image/svg+xml;base64,{svg_b64}"
    else:
        icon = "❇️"
        
    st.set_page_config(
        page_title="MEDIS",
        page_icon=icon,
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Logo display in the sidebar
    if logo_file.is_file() and hasattr(st, "logo"):
        st.logo(f"data:image/svg+xml;base64,{svg_b64}", size="large")

    # Hide Streamlit's default menu and footer, and adjust padding
    st.markdown(
        f"<style>{_load_stylesheet()}</style>",
        unsafe_allow_html=True,
    )
    
    # Applies all styles
    # base_style()
    tab_style()
    # file_uploader_style()
    expander_style()

def github_link(
    repo_url="https://github.com/joao-canais/Propagation-of-Uncertainty-Calculator.git",
    label="GitHub Repository",
):
    """Renders GitHub badge with SVG icon in the sidebar."""
    st.sidebar.markdown(
        f"""
        <a href="{repo_url}" target="_blank" class="github-link">
            <svg height="18" width="18" viewBox="0 0 16 16">
                <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"></path>
            </svg>
            <span>{label}</span>
        </a>
        """,
        unsafe_allow_html=True,
    )