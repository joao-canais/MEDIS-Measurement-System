from src.paths import get_timestamp, get_timestamp_sec, img_dir, data_dir, fits_dir
from src.styles import apply_page_config, github_link
from src.utils import create_folder, save_fits, save_png
from src.compute_calibration import compute_calibration
from src.camera import capture_image

from datetime import datetime
from astropy.io import fits
import streamlit as st
import pandas as pd
import numpy as np
import tempfile
import json
import os


# Style and page configuration
apply_page_config()
github_link("https://github.com/joao-canais/MEDIS-Measurement-System.git")

def single_acquisition(cam_idx=0, session_folders=None, json_file=None, folder_name=None):
    """
    Executes a single image acquisition and processing
    Returns: img, x, y, full_results
    """
    # Uses the session folders if provided
    if session_folders is None:
        fit_session_dir = create_folder(fits_dir)
        png_session_dir = create_folder(img_dir)
    else:
        fit_session_dir, png_session_dir = session_folders
    
    timestamp_seg = get_timestamp_sec()

    # Capture the frame
    img, img_original, header_params = capture_image(cam_idx)
        
    header_params.update({
        'COEF_F': (folder_name, 'Coefficients folder name'),
    })
    
    # The compute_calibration function may return a figure, let's capture it
    if json_file is not None:
        try:
            full_results = compute_calibration(img.astype(float), calib=True, json_file=json_file)
        except Exception as e:
            st.warning(f"Error using the compute_calibration function: {e}")
            st.warning("Check if the captured image is valid.")
    else:
        st.warning("No calibration coefficient file provided.")
    
    # Extract main values
    x = full_results["center_real_points"][0]
    y = full_results["center_real_points"][1]
    coord = (x, y)
    
    fit_dest = save_fits(img, fit_session_dir, coord=coord, header_params=header_params)
    save_png(img, png_session_dir, type="adapted", coord=coord)
    
            
    return img, coord, full_results, timestamp_seg, fit_dest


# Initialize session state
if 'acquisition_active' not in st.session_state:
    st.session_state.acquisition_active = False
if 'results_history' not in st.session_state:
    st.session_state.results_history = []
if 'session_folders' not in st.session_state:
    st.session_state.session_folders = None
if 'acquisition_count' not in st.session_state:
    st.session_state.acquisition_count = 0
if 'x_list' not in st.session_state:
    st.session_state.x_list = []
if 'y_list' not in st.session_state:
    st.session_state.y_list = []

st.title("Main Page - 3D Coordinate Acquisition")

with st.expander("Full Instructions:", type="step"):
    st.markdown("""
                
    ### **Objective**
    This system captures cross images using USB cameras and automatically computes the (X, Y) coordinates (with the given calibration coefficients) in millimeters with high precision.

    ### **How to Use**

    - Select the calibration coefficients (JSON file).
    - Click on **"Start Acquisition"** (ensure the camera is properly connected and configured).
    - Displays real-time coordinates for each capture, along with image quality information (saturation, maximum intensity)
    - To capture again, click **"Next Capture"** after each acquisition
    - Use **"Stop Acquisition"** to interrupt when necessary
    - Click **"Clear History"** to reset the results history and start fresh

    ### **Results Obtained**

    1. **Main Coordinates:**
    - **X (mm)** - Horizontal position of the cross in millimeters
    - **Y (mm)** - Vertical position of the cross in millimeters

    2. **Quality Information:**
    - **Saturation Status** - Detects if the image is saturated
    - **Saturated Pixels** - Counts how many pixels reached saturation (≥254)

    #### **History and Statistics**
    - **Results Table** - Shows captures with coordinates and status

    ### **Generated Files**

    The system automatically saves:
    - **FITS files** organized by session with timestamp
    - **PNG images** for verification
    - **TXT File** with results history (coordinates and status of each capture)
    """)
    
col1, col2 = st.columns([1, 1])

json_file = None

with col1:
    if st.header("Choose Calibration Coefficients", help= "You can choose a certain CC or leave it blank to use the most recent one."):
        json_file = st.file_uploader(
            "Choose Calibration Coefficients",
            type=["json"],
            label_visibility="collapsed"
            )
        
        if json_file is not None:
            # Create a temporary file to store the uploaded JSON content
            with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
                tmp.write(json_file.getvalue())
                tmp_path = tmp.name # Load the JSON content from the temporary file
                
            try:
                with open(tmp_path, 'r') as f:
                    calib = json.load(f)
                    if calib.get("folder_name"):
                        folder_name = calib["folder_name"]
                    else:
                        folder_name = "unknown"
                        st.warning("Warning: Invalid JSON file. Does not contain the folder name for the coefficients (to be saved in the fits header of each file).")
            except Exception as e:
                st.warning(f"Warning: Could not read the JSON file: {e}")
        
        st.session_state.calibration_coefficients = json_file

with col2:
    st.header("Start Acquisition")

    if st.button("Start Acquisition", disabled=st.session_state.acquisition_active, width='stretch', key ="start_acquisition"):
        
        if json_file is None:
            st.info("Select the calibration coefficients before starting the acquisition.")
            st.stop()
            
        # Create session folders and initialize session state variables
        timestamp = get_timestamp()
        st.session_state.session_folders = (
            create_folder(fits_dir),
            create_folder(img_dir)
        )
        st.session_state.acquisition_active = True
        st.session_state.acquisition_count = 0
        st.session_state.ready_for_next_capture = True
        # Clear previous results and coordinate lists
        st.session_state.x_list = []
        st.session_state.y_list = []
        st.rerun()

# Exhibition of acquisition results and controls
if st.session_state.acquisition_active:
        
    st.header("Acquisition in Progress")
    
    # Placeholders for dynamic content
    status_placeholder = st.empty()
    image_placeholder = st.empty()
    coords_placeholder = st.empty()
    countdown_placeholder = st.empty()
    
    # Only captures if the flag is set, otherwise just shows the last result and waits for user to click "Next Capture" 
    if st.session_state.get('ready_for_next_capture', True):

        try:
            with st.spinner(f"Capture #{st.session_state.acquisition_count + 1} in progress..."):
            
                # Executes the acquisition and processing function
                img, coord, full_results, timestamp_seg, fit_dir = single_acquisition(
                    session_folders=st.session_state.session_folders, json_file=tmp_path, folder_name=folder_name
                )
                
                # Adds the coordinates to the lists for variation calculation
                st.session_state.x_list.append(coord[0])
                st.session_state.y_list.append(coord[1])
            
                # Update acquisition count
                st.session_state.acquisition_count += 1
            
                # Store the result in the session state history
                result = {
                    'img': img,
                    'x': coord[0],
                    'y': coord[1],
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'timestamp_seg': timestamp_seg,
                    'resultados': full_results,
                    'capture_num': st.session_state.acquisition_count,
                }
                
                st.session_state.results_history.append(result)
                st.session_state.last_result = result
                st.session_state.current_fit_path = str(fit_dir)
                
                # Deactivate the flag to wait for user input before next capture
                st.session_state.ready_for_next_capture = False
            
        except Exception as e:
            st.error(f"Error in acquisition: {str(e)}")
            st.session_state.acquisition_active = False
    
    # Always shows the last result during acquisition
    if 'last_result' in st.session_state and st.session_state.last_result:
        result = st.session_state.last_result
        img = result['img']
        x = result['x']
        y = result['y']
        
        # If not ready for next capture, shows the current result with controls
        if not st.session_state.get('ready_for_next_capture', False):
            with status_placeholder.container():
                saturados = np.sum(img >= 254)
                max_val = np.max(img)
            
            with image_placeholder.container():
                col_img, col_coords = st.columns([2, 1])
                
                with col_img:
                    st.image(img, caption=f'Capture #{result["capture_num"]} - {result["timestamp"]}', 
                            width='stretch')
                
                with col_coords:
                    st.subheader("Coordinates:")
                    st.metric("X Coordinate (mm)", f"{x:.3f}")
                    st.metric("Y Coordinate (mm)", f"{y:.3f}")
                    
                    if saturados > 0:
                        st.error(f"Saturated Image! {saturados} pixels saturated.")
                    else:
                        st.success(f"No saturation detected!")
            
                col1, col2 = st.columns(2)
                with col1:

                    st.subheader("Next Capture")
                    if st.button("Next Capture", type="secondary", width='stretch'):
                        st.session_state.ready_for_next_capture = True
                        st.rerun()

                with col2:
                    st.subheader("Stop Acquisition")
                    if st.button("Stop Acquisition", disabled=not st.session_state.acquisition_active, width='stretch'):
                        
                        # Generates TXT file with the history of results
                        if st.session_state.results_history:
                            timestamp_export = get_timestamp()
                            txt_file = os.path.join(data_dir, f"results_history_{timestamp_export}.txt")
                            os.makedirs(data_dir, exist_ok=True)
                            
                            with open(txt_file, 'w', encoding='utf-8') as f:
                                f.write("="*60 + "\n")
                                f.write(" MEDIS - RESULTS HISTORY\n")
                                f.write("="*60 + "\n\n")
                                f.write(f"Date/Time: {timestamp_export}\n")
                                if 'folder_name' in locals() and folder_name:
                                    f.write(f"JSON Folder: {folder_name}\n")
                                f.write(f"Number of points: {len(st.session_state.results_history)}\n")
                                f.write("\n" + "="*60 + "\n\n")
                                f.write("RESULTS:\n")
                                f.write("-"*60 + "\n")
                                f.write("  Capture  |    X (mm)    |    Y (mm)    |   Image\n")
                                f.write("-"*60 + "\n")
                                
                                for idx, result in enumerate(st.session_state.results_history, start=1):
                                    status = 'Saturated' if np.sum(result['img'] >= 254) > 0 else 'Not Saturated'
                                    f.write(f"   {idx:3d}     |  {result['x']:8.3f}    |  {result['y']:8.3f}    |  {status}\n")
                                
                                f.write("-"*60 + "\n")
                        
                        st.session_state.acquisition_active = False
                        st.session_state.session_folders = None
                        st.rerun()
                st.markdown("---")
            
            # Computes the variation from the last capture if there are at least 2 captures
            if len(st.session_state.x_list) > 1:
                diff_x = st.session_state.x_list[-1] - st.session_state.x_list[-2]
                diff_y = st.session_state.y_list[-1] - st.session_state.y_list[-2]
                dist = np.sqrt(diff_x**2 + diff_y**2)
                
                with coords_placeholder.container():
                    st.subheader("Variation since the last capture:")
                    col_dx, col_dy, col_dist = st.columns(3)
                    with col_dx:
                        st.metric("ΔX (mm)", f"{diff_x:.3f}")
                    with col_dy:
                        st.metric("ΔY (mm)", f"{diff_y:.3f}")
                    with col_dist:
                        st.metric("Distance (mm)", f"{dist:.3f}")
        
        with st.expander("Debug (Optional)"):
            st.write("To save the real positions (in the fits header) and compare with the ones obtained on the Debug page.")
            
            # Inputs for the real coordinates
            col1, col2 = st.columns(2)
            with col1:
                x_coord = st.number_input(
                    "X Coordinate (mm):",
                    value=0.0,
                    format="%.3f",
            )
            with col2:
                y_coord = st.number_input(
                    "Y Coordinate (mm):",
                    value=0.0,
                    format="%.3f",
                )
            
            if st.button("Save", type="secondary", width='stretch'):
                
                # Saves the real coordinates in the FITS header of the current capture
                fit_path = st.session_state.get('current_fit_path') or st.session_state.last_result.get('fit_path')
                
                if fit_path and os.path.exists(fit_path):
                    with fits.open(fit_path, mode='update') as hdul:
                        hdul[0].header['COORD_X'] = (f"{x_coord:.3f}", 'X coordinate in mm')
                        hdul[0].header['COORD_Y'] = (f"{y_coord:.3f}", 'Y coordinate in mm')
                        hdul.flush()
                    st.info(f"Real coordinates saved in {os.path.basename(fit_path)}")
                else:
                    st.error("FITS file not found. Please make a capture first.")
    

# Display last result when not in continuous acquisition
elif 'last_result' in st.session_state:
    st.header("Last Result")
    
    result = st.session_state.last_result
    img = result['img']
    x = result['x']
    y = result['y']
    
    # Saturation analysis
    saturados = np.sum(img >= 254)
    max_val = np.max(img)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        caption = f'Capture: {result["timestamp"]}'
        if 'capture_num' in result:
            caption = f'Capture #{result["capture_num"]}'
        st.image(img, caption=caption, width='stretch')
        
    with col2:
        st.header("Coordinates")
        st.metric("X (mm)", f"{x:.3f}")
        st.metric("Y (mm)", f"{y:.3f}")
        if saturados > 0:
            st.error(f"Saturated Image!")
        else:
            st.success(f"Maximum Intensity: {max_val}")


# History of results
if st.session_state.results_history:
    st.header("Results")
    
    # Show summary statistics
    col1, col2, col3, col4 = st.columns(4)
    
    x_coords = [r['x'] for r in st.session_state.results_history]
    y_coords = [r['y'] for r in st.session_state.results_history]
    
    with col1:
        st.metric("Total Captures", len(st.session_state.results_history))
    with col2:
        saturated_count = sum(1 for r in st.session_state.results_history if np.sum(r['img'] >= 254) > 0)
        st.metric("Saturated Images", saturated_count)
    
    # Table of data
    hist_data = []
    for idx, result in enumerate(st.session_state.results_history):
        hist_data.append({
            'Capture': f"{idx + 1}",
            'X (mm)': f"{result['x']:.3f}",
            'Y (mm)': f"{result['y']:.3f}",
            'Image': 'Saturated' if np.sum(result['img'] >= 254) > 0 else 'Not Saturated'
        })
        
        
    df = pd.DataFrame(hist_data)
    
    def red_color(imagem):
        if imagem == "Saturated":
            return 'background-color: rgba(255, 0, 0, 0.3)'  # Red background for saturated images
        else:
            return ''
    
    styled_df = (
        df.style
        .map(red_color, subset=['Image'])
        # .hide(axis='index')
        )
            
    st.dataframe(styled_df, width='stretch', hide_index=True)
    
    st.divider()
    
    # Button to clear history
    if st.button("Clear History", width='stretch'):
        st.session_state.results_history = []
        st.session_state.x_list = []
        st.session_state.y_list = []
        if 'last_result' in st.session_state:
            del st.session_state.last_result
        st.rerun()