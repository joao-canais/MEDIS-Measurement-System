from src.paths import data_calib_dir, fits_calib_dir, get_timestamp, get_timestamp_sec, img_calib_dir
from src.utils import create_folder, linear_calibration, save_fits, save_png
from src.styles import apply_page_config, github_link
from src.compute_calibration import compute_calibration
from src.camera import capture_image

from astropy.io import fits
from pathlib import Path
import streamlit as st
import numpy as np
import glob
import os


# Apply configurations and styles
apply_page_config()
github_link("https://github.com/joao-canais/MEDIS-Measurement-System.git")

def init_session_state():
    """Initializes the session state variables"""
    if 'total_images' not in st.session_state:
        st.session_state.total_images = 5
    if 'current_capture' not in st.session_state:
        st.session_state.current_capture = 0
    if 'captures_completed' not in st.session_state:
        st.session_state.captures_completed = []
    if 'session_timestamp' not in st.session_state:
        st.session_state.session_timestamp = get_timestamp()
    if "uploader_key" not in st.session_state:
        st.session_state.uploader_key = 0
    if 'calibration_completed' not in st.session_state:
        st.session_state.calibration_completed = False
    if 'calibration_coefficients' not in st.session_state:
        st.session_state.calibration_coefficients = None
    if 'session_folders' not in st.session_state:
        st.session_state.session_folders = None

def reset_session():
    """Calibration session reset"""
    st.session_state.current_capture = 0
    st.session_state.captures_completed = []
    st.session_state.session_timestamp = get_timestamp()
    st.session_state.calibration_completed = False
    st.session_state.calibration_coefficients = None
    st.session_state.session_folders = None
    # Clear pending captures
    keys_to_remove = [key for key in st.session_state.keys() if key.startswith('pending_capture_')]
    for key in keys_to_remove:
        del st.session_state[key]

def create_session_folders():
    """Creates the session folders once"""
    if st.session_state.session_folders is None:
        fit_session_dir = create_folder(fits_calib_dir, timestamp=st.session_state.session_timestamp)
        png_session_dir = create_folder(img_calib_dir, timestamp=st.session_state.session_timestamp)
        st.session_state.session_folders = (fit_session_dir, png_session_dir)
    return st.session_state.session_folders

def capturing_image(camera_index=0, session_folders=None, x_coord=None, y_coord=None):
    """Captures an image and saves it with the specified coordinates"""
    try:
        timestamp_seg = get_timestamp_sec()
        
        # Use the already created session folders
        fit_session_dir, png_session_dir = st.session_state.session_folders
        
        # Camera image capture
        image, img_original, fits_header_parameters = capture_image(camera_index)
        
        # Add coordinates to the FITS header
        if x_coord is not None and y_coord is not None:
            fits_header_parameters['COORD_X'] = (f"{round(x_coord, 3)}", 'Real X coordinate in mm')
            fits_header_parameters['COORD_Y'] = (f"{round(y_coord, 3)}", 'Real Y coordinate in mm')
        
        fit_path = save_fits(image, fit_session_dir, coord=(x_coord,y_coord), header_params=fits_header_parameters, timestamp=timestamp_seg)
        
        return image, fit_path
    
    except Exception as e:
        st.error(f"Capture error: {str(e)}")
        return None, None
    
def calibration(fits_files):
    """
    Automatic calibration function that processes captured FITS files
    """
    results = []
    
    # For each FITS image, computes the center and cross inclination
    for idx, fits_path in enumerate(fits_files, start=1):
        with fits.open(fits_path) as hdul:
            data = hdul[0].data.astype(float)
            result = compute_calibration(data, calib=False)
            results.append(result)
    
    # Array with pixel centers of each cross
    pixel_points = np.array([[r['center_pixel_points'][0], r['center_pixel_points'][1]] for r in results])

    # --- 2. Definition of Real distances and real points (in mm) ---
    real_points = []
    for fits_path in fits_files:
        with fits.open(fits_path) as hdul:
            header = hdul[0].header
            x = float(header['COORD_X'])
            y = float(header['COORD_Y'])
        real_points.append([x, y])
    real_points = np.array(real_points)

    # --- 3. Linear calibration (pixels → mm) ---
    calibration_data, estimated_points, json_name = linear_calibration(pixel_points, real_points, timestamp=st.session_state.session_timestamp)
    
    
    # --- 5. Rename FITS files and create PNG images ---
    fit_session_dir, png_session_dir = st.session_state.session_folders

    for idx, file in enumerate(fits_files):
        x_est, y_est = estimated_points[idx][0], estimated_points[idx][1]
        
        # Generate new name with estimated coordinates
        base_name = f"X{x_est:.3f}_Y{y_est:.3f}"
        
        # Rename FITS file
        old_fits_path = Path(file)
        new_fits_path = old_fits_path.parent / f"{base_name}.fits"
        old_fits_path.rename(new_fits_path)
        
        # Add JSON folder name to FITS header
        try:           
            with fits.open(new_fits_path, mode='update') as hdul:
                hdul[0].header['COEF_F'] = json_name
                hdul[0].header.comments['COEF_F'] = 'Coefficients folder name'
        except Exception as e:
            print(f"Warning: Could not save JSON folder name in FITS header: {e}")
        
        
        # Create PNG image from FITS
        try:
            with fits.open(new_fits_path) as hdul:
                data = hdul[0].data
            
            # Save PNG in the session images folder
            save_png(data, png_session_dir, type="adapted", coord=(x_est, y_est))
            
        except Exception as e:
            print(f"Warning: Error creating PNG for {base_name}: {e}")


    # --- 6. Save pixel and mm centers in a txt file ---
    txt_file = os.path.join(data_calib_dir, f"calibration_data_{st.session_state.session_timestamp}.txt")
    os.makedirs(data_calib_dir, exist_ok=True)
    
    with open(txt_file, 'w', encoding='utf-8') as f:
        # Header
        f.write("="*80 + "\n")
        f.write(" MEDIS - CALIBRATION DATA\n")
        f.write("="*80 + "\n\n")
        
        # Session information
        f.write(f"Date/Time: {st.session_state.session_timestamp}\n")
        f.write(f"FITS folder: capture_{st.session_state.session_timestamp}\n")
        f.write(f"JSON folder: {json_name}\n")
        f.write(f"Number of points: {len(real_points)}\n")
        f.write(f"Accuracy: {calibration_data['validation']['accuracy_percentage']:.2f}% (< 50 μm)\n")
        f.write(f"Mean X error: {calibration_data['validation']['mean_error_x_mm']:.3f} mm\n")
        f.write(f"Mean Y error: {calibration_data['validation']['mean_error_y_mm']:.3f} mm\n")
        f.write("\n" + "="*80 + "\n\n")
        
        # Coordinates table
        f.write("COMPARISON: REAL COORDINATES (MILLING MACHINE) vs COMPUTED (SYSTEM)\n")
        f.write("-"*80 + "\n")
        f.write("  i  | Milling Machine (mm) |  Computed (mm)   |  Error (mm)    \n")
        f.write("     |    X         Y     |    X         Y     |   ΔX      ΔY   \n")
        f.write("-"*80 + "\n")
        
        for idx, (est, real) in enumerate(zip(estimated_points, real_points), start=1):
            error_x = abs(est[0] - real[0])
            error_y = abs(est[1] - real[1])
            f.write(f"{idx:3d}  | {real[0]:7.3f}  {real[1]:7.3f}   | {est[0]:7.3f}  {est[1]:7.3f}   |   {error_x:5.3f}  {error_y:5.3f}\n")
        
        f.write("-"*80 + "\n")

    return calibration_data, txt_file

def run_automatic_calibration():
    """
    Executes automatic calibration with FITS files from the current session
    """
    try:
        fits_files = [os.path.join(fits_calib_dir, d) for d in os.listdir(fits_calib_dir) if os.path.isdir(os.path.join(fits_calib_dir, d))] 
        fits_files.sort(key=os.path.getmtime)                      # Sort subfolders by modification date (newest last)
        latest_dir = fits_files[-1]                                # Select the most recent subfolder
        fits_files = glob.glob(os.path.join(latest_dir, '*.fits')) # List all .fits files in the most recent subfolder
        fits_files.sort(key=os.path.getmtime)                      # Sort files by modification date (oldest to newest)

        
        if not fits_files:
            st.error("No FITS files were found to process.")
            return None, None
        
        # Convert to strings (absolute paths)
        fits_files_str = [str(f) for f in fits_files]
        
        try:
            # Run calibration
            calibration_data, txt_file = calibration(fits_files_str)
        except Exception as e:
            st.error(f"Error in calibration function: {str(e)}")
                    
        return calibration_data, txt_file
    
    except Exception as e:
        st.error(f"Error during automatic calibration: {str(e)}")
        return None, None


tab1, tab2 = st.tabs(["Full Calibration Process", "Get Calibration Coefficients"])


with tab1:
    st.header("Full Calibration Process")
    with st.expander("Instructions", type="step"):
        st.markdown("""
        ### **Objective**
        Runs the full calibration process, from image capture to calibration coefficient estimation.
        
        ### **How to use**
        
        **Part 1 - Image Capture:**
        1. **Set** the number of images to capture
        2. **Position** the target (cross center) at known real coordinates in mm (use a milling machine or a precise positioning system)
        3. **Enter** the X and Y coordinates for the target position (they are saved in the FITS header)
        4. **Capture** the image by pressing the capture button
        5. **Check** from the preview that the image is not saturated and the cross is valid (with all 4 ends visible)
        6. **Repeat** for all desired positions
        
        **Part 2 - Automatic Calibration:**
        
        7. After all captures, press **"Compute Coefficients"** to compute the calibration coefficients
        8. The system will display the computed calibration coefficients and allow you to repeat the process
        
        ### **What you get**
        - **FITS files** organized by session with timestamp
        - **PNG images** for verification
        - **TXT file** with calibration details and comparison between real and computed coordinates
        - **JSON file** with calibration coefficients (α_x and α_y) for pixel → mm conversion
        
        ### **Important tips**
        - Use points uniformly distributed over the area of interest
        - Avoid saturated images
        - Coordinates must be precise and in millimeters (ideally with 3 decimal places)
        """)
    
    st.divider()
    
    # Initialize session state
    init_session_state()
    
    col1, col2 = st.columns([5, 1])
    
    with col1:
        st.header("Part 1: Image Capture")
    with col2:
        # Reset session
        st.markdown("<br>", unsafe_allow_html=True)  # Add spacing
        if st.button("Restart Calibration", type="secondary", width='stretch'):
            reset_session()
            st.rerun()            
            
    # Sidebar settings
    with st.expander("Settings"):
        col1, col2 = st.columns(2)
        with col1:
            # Total number of images
            total_images = st.number_input(
                "Number of images to capture:",
                min_value=1,
                max_value=50,
                value=st.session_state.total_images
            )
            st.session_state.total_images = total_images
        with col2:
            # Camera index
            camera_index = st.number_input(
                "Camera index:",
                min_value=0,
                max_value=10,
                value=0
            )
        
    
    # Progress
    progress_col1, progress_col2 = st.columns([10, 1])
    with progress_col1:
        progress = st.progress(st.session_state.current_capture / st.session_state.total_images)
    with progress_col2:
        st.metric("Progress", f"{st.session_state.current_capture}/{st.session_state.total_images}")
    
    # If there are still images to capture
    if st.session_state.current_capture < st.session_state.total_images:
            
        st.subheader(f"Capture {st.session_state.current_capture + 1}/{st.session_state.total_images}")
        
        # Coordinate inputs
        col1, col2 = st.columns(2)
        with col1:
            x_coord = st.number_input(
                "X Coordinate (mm):",
                value=0.0,
                format="%.3f",
                key=f"x_{st.session_state.current_capture}"
            )
        with col2:
            y_coord = st.number_input(
                "Y Coordinate (mm):",
                value=0.0,
                format="%.3f",
                key=f"y_{st.session_state.current_capture}"
            )
        
        # Check if there is a pending capture for this position
        pending_capture_key = f"pending_capture_{st.session_state.current_capture}"
        
        # Capture button - only shown when there is no pending capture
        if pending_capture_key not in st.session_state:
            if st.button("Capture Image", width='stretch'):
                with st.spinner("Capturing image..."):
                        # create session folders (only on first capture)
                    if st.session_state.current_capture == 0:
                        create_session_folders()
                        
                    image, fit_path = capturing_image(camera_index, x_coord=x_coord, y_coord=y_coord)
                    
                    if fit_path is not None:
                        # Save pending capture in session_state
                        st.session_state[pending_capture_key] = {
                            'index': st.session_state.current_capture + 1,
                            'x': x_coord,
                            'y': y_coord,
                            'fit_path': str(fit_path),
                            'image': image  # Save image too
                        }
                        st.rerun()
                    else:
                        st.error("Image capture failed. Please try again.")
        
        # If there is a pending capture, show image and options
        if pending_capture_key in st.session_state:
            capture_data = st.session_state[pending_capture_key]
            image = capture_data['image']
            
            # --- Saturation check ---
            saturated_pixels = np.sum(image >= 254)
            max_val = np.max(image)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.image(image, caption='Adapted Image')  
            with col2:
                if saturated_pixels > 0:
                    st.error(f"Saturated image! Saturated pixels: {saturated_pixels}")
                else:
                    st.success(f"No saturation! Maximum value: {max_val}")
            
            # Buttons to continue or recapture
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Capture Again", type="secondary", width='stretch'):
                    # Remove pending capture
                    try:
                        if os.path.exists(capture_data['fit_path']):
                            os.remove(capture_data['fit_path'])
                    except Exception as e:
                        st.warning(f"Warning: Error removing temporary files: {e}")
                    
                    del st.session_state[pending_capture_key]
                    st.rerun()
            with col2:
                if st.button("Next Capture", type="secondary", width='stretch'):
                    
                    # Confirm capture - add to final list
                    capture_final = {
                        'index': capture_data['index'],
                        'x': capture_data['x'],
                        'y': capture_data['y'],
                        'fit_path': capture_data['fit_path'],
                    }
                    st.session_state.captures_completed.append(capture_final)
                    
                    # Remove pending capture
                    del st.session_state[pending_capture_key]
                    
                    # Move to next capture
                    st.session_state.current_capture += 1
                    st.rerun()
                        
    
    # If all captures are complete
    else:
        st.success("All captures have been saved!")
        
        # NEW SECTION: AUTOMATIC CALIBRATION
        st.markdown("---")
        st.header("Part 2: Automatic Calibration")
        
        # Ensure calibration variables are initialized
        if 'calibration_completed' not in st.session_state:
            st.session_state.calibration_completed = False
        if 'calibration_coefficients' not in st.session_state:
            st.session_state.calibration_coefficients = None
        
        if not st.session_state.calibration_completed:
            st.info("Ready to compute calibration coefficients.")
            
            col1, col2 = st.columns([3,1])
            
            with col1:
                if st.button("Compute Coefficients", type="secondary", width='stretch'):
                    with st.spinner("Processing automatic calibration..."):
                        calibration_data, txt_file = run_automatic_calibration()
                        
                        if calibration_data is not None:
                            # Save results in session state
                            st.session_state.calibration_coefficients = calibration_data
                            st.session_state.calibration_completed = True
                            st.session_state.calibration_txt_file = txt_file
                            st.rerun()
                        else:
                            st.error("Error during calibration. Check captured images.")                                
        
        else:
            # Show calibration results
            st.success("Calibration completed!")
            
            # Show coefficients
            calib_data = st.session_state.calibration_coefficients
            
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Coefficients for X (mm)")
                st.code(f"""
                X = α_x[0]*i + α_x[1]*j + α_x[2]

                α_x[0] = {calib_data['coefficients']['alpha_x'][0]:.6e}
                α_x[1] = {calib_data['coefficients']['alpha_x'][1]:.6e}
                α_x[2] = {calib_data['coefficients']['alpha_x'][2]:.6e}
                """)
                            
            with col2:
                st.subheader("Coefficients for Y (mm)")
                st.code(f"""
                Y = α_y[0]*i + α_y[1]*j + α_y[2]

                α_y[0] = {calib_data['coefficients']['alpha_y'][0]:.6e}
                α_y[1] = {calib_data['coefficients']['alpha_y'][1]:.6e}
                α_y[2] = {calib_data['coefficients']['alpha_y'][2]:.6e}
                """)
            
            st.subheader("Statistical Data:")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Accuracy:", f"{calib_data['validation']['accuracy_percentage']:.0f}%")
            with col2:
                st.metric("X Error (mm):", f"{calib_data['validation']['mean_error_x_mm']:.3f}")
            with col3:
                st.metric("Y Error (mm):", f"{calib_data['validation']['mean_error_y_mm']:.3f}")
                
            # Additional information
            if hasattr(st.session_state, 'calibration_txt_file'):
                st.info(f"Data saved in: {st.session_state.calibration_txt_file}")
            
        
        # Button to start a new session
        if st.button("Start New Capture Session", type="secondary"):
            reset_session()
            st.rerun()
    
    # Show capture history
    if st.session_state.captures_completed:
        st.markdown("---")
        st.subheader("Completed Captures")
        
        # Table with captures
        with st.expander(f"Captures ({len(st.session_state.captures_completed)})"):
            for idx, capture in enumerate(st.session_state.captures_completed, start=1):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Capture {idx}:** X{capture['x']:.3f}Y{capture['y']:.3f}.fits")
                with col2:
                    st.write(f"**Coordinates:** ({capture['x']:.3f}, {capture['y']:.3f}) mm")


with tab2:
    st.header("Get Calibration Coefficients")
    with st.expander("Instructions", type="step"):
        st.markdown("""
                ### **Objective**
                
                Compute calibration coefficients using existing FITS files, without running the capture process.
        
                ### **File Requirements**
                
                - Previously captured .fits files
                - Must contain real coordinates in the header (COORD_X and COORD_Y).
                
                ### **How to use**
        
                **Process:**
                1. **Select** the FITS files
                2. **Press** "Compute Calibration Coefficients"
        
                ### **What you get**
                - **TXT file** with calibration details and comparison between real and computed coordinates
                - **JSON file** with calibration coefficients (α_x and α_y) for pixel → mm conversion
        """)
        
    st.markdown("---")
    st.header("Select FITS files", help="Must have the real coordinates on the file name in order to get the Calibration Coefficients")
    
    # Tab 2 specific variables
    if 'tab2_calibration_completed' not in st.session_state:
        st.session_state.tab2_calibration_completed = False
    if 'tab2_calibration_coefficients' not in st.session_state:
        st.session_state.tab2_calibration_coefficients = None
    
    if not st.session_state.tab2_calibration_completed:
        
        # Folder path input
        uploaded_folder = st.text_input(
            "Enter the folder path containing FITS files:",
            key="tab2_folder_path",
            help="Example: C:\\Users\\user\\Documents\\MEDIS\\files\\Calibration Files\\Fits\\Fits_teste"
        )
        
        if uploaded_folder and os.path.isdir(uploaded_folder):
            # List .fits files in the folder
            fits_files = glob.glob(os.path.join(uploaded_folder, "*.fits"))
            
            if not fits_files:
                st.error("No .fits files found in the specified folder.")
            else:
                st.success(f"{len(fits_files)} FITS files found!")
                
                # Show list of found files
                with st.expander(f"Found files ({len(fits_files)})"):
                    for idx, file in enumerate(fits_files, start=1):
                        filename = os.path.basename(file)
                        st.write(f"**{idx}.** {filename}")
                
                if st.button("Compute Coefficients", type="secondary", width='stretch', key="tab2_compute_button"):
                    with st.spinner("Processing automatic calibration..."):
                        try:
                            # Configure session_folders to use existing folders
                            fit_session_dir = Path(uploaded_folder)
                            
                            # Derive the corresponding PNG folder: replace "Fits" with "Images"
                            png_session_dir = Path(str(fit_session_dir).replace("Fits", "Images"))
                            png_session_dir.mkdir(parents=True, exist_ok=True) # Ensure images folder exists
                            
                            # Configure session_folders for calibration()
                            st.session_state.session_folders = (fit_session_dir, png_session_dir)
                            
                            # Run calibration with files from folder (NOT temporary)
                            calibration_data, txt_file = calibration(fits_files)
                            
                            if calibration_data is not None:
                                # Save results in Tab 2 session state
                                st.session_state.tab2_calibration_coefficients = calibration_data
                                st.session_state.tab2_calibration_completed = True
                                st.session_state.tab2_calibration_txt_file = txt_file
                                st.rerun()
                            else:
                                st.error("Error during calibration. Check the images.")
                                
                        except Exception as e:
                            st.error(f"Error during processing: {str(e)}")
        
        elif uploaded_folder:
            st.error("Invalid path! Check if the folder exists.")
    
    else:
        # Show calibration results
        st.success("Calibration completed!")
        
        # Show coefficients
        calib_data = st.session_state.tab2_calibration_coefficients
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Coefficients for X (mm)")
            st.code(f"""
            X = α_x[0]*i + α_x[1]*j + α_x[2]

            α_x[0] = {calib_data['coefficients']['alpha_x'][0]:.6e}
            α_x[1] = {calib_data['coefficients']['alpha_x'][1]:.6e}
            α_x[2] = {calib_data['coefficients']['alpha_x'][2]:.6e}
            """)
                        
        with col2:
            st.subheader("Coefficients for Y (mm)")
            st.code(f"""
            Y = α_y[0]*i + α_y[1]*j + α_y[2]

            α_y[0] = {calib_data['coefficients']['alpha_y'][0]:.6e}
            α_y[1] = {calib_data['coefficients']['alpha_y'][1]:.6e}
            α_y[2] = {calib_data['coefficients']['alpha_y'][2]:.6e}
            """)
        
        st.subheader("Statistical Data:")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Accuracy:", f"{calib_data['validation']['accuracy_percentage']:.0f}%")
        with col2:
            st.metric("X Error (mm):", f"{calib_data['validation']['mean_error_x_mm']:.3f}")
        with col3:
            st.metric("Y Error (mm):", f"{calib_data['validation']['mean_error_y_mm']:.3f}")
                
        # Additional information
        if hasattr(st.session_state, 'tab2_calibration_txt_file'):
            st.info(f"Data saved in: {st.session_state.tab2_calibration_txt_file}")
        
        # Button to reset Tab 2
        if st.button("New Calibration", type="secondary"):
            st.session_state.tab2_calibration_completed = False
            st.session_state.tab2_calibration_coefficients = None
            st.session_state.uploader_key += 1  # Force uploader reset
            st.rerun()

