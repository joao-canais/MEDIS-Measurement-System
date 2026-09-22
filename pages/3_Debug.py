from src.styles import apply_page_config, github_link
from src.utils import create_folder, save_fits, save_png
from src.compute_calibration import compute_calibration
from src.paths import fits_dir, img_dir, json_dir
from src.camera import capture_image

import matplotlib.pyplot as plt
from astropy.io import fits
from io import BytesIO
import streamlit as st
import pandas as pd
import numpy as np
import tempfile
import cv2
import os


# Apply page config and styles
apply_page_config()
github_link("https://github.com/joao-canais/MEDIS-Measurement-System.git")

tab1, tab2, tab3 = st.tabs(["Image Capture & Adaptation", "Image Processing (px)", "Image Processing (mm)"])


with tab1:
    st.header("Image Capture & Adaptation")
    with st.expander("Instructions", type="step"):
        st.markdown("""
        ### **Objective:**
        Capture an image from the camera or upload an existing FITS file and verify adapted-image quality for processing.
        
        ### **How to use:**
        
        **Option 1 - Camera Capture:**
        1. **Press** the "Capture Image" button
        2. **Wait** for automatic image processing
        3. **Check** the displayed original and adapted images
        4. **Analyze** FITS header parameters (if available)
        
        **Option 2 - FITS File Upload:**
        1. **Upload** a previously captured FITS file
        2. **Check** the displayed adapted image
        3. **Analyze** FITS header parameters (if available)
        
        ### **Displayed Information:**
        
        **Images:**
        - **Original:** Original image captured by the camera (no processing applied)
        - **Adapted:** Processed image.
        
        **FITS Header Parameters** (if available):
        - **Camera Settings:** Index, system, size, data type...
        - **Capture Parameters:** Exposure, gain, brightness, contrast, saturation
        - **Applied Processing:** Grayscale, threshold
        - **Image Quality:** Saturated pixels, maximum intensity
        
        **Cross Arm Dimensions:**
        - Arm lengths at the margins (left, right, top, bottom)
        - Camera tilt indication based on percentage error between opposite arms
        
        **Intensity Profile:**
        - Intensity profile graph for the right edge
        
        ### **Quality Checks:**
        
        **Saturation:**
        - **No saturation:** Maximum intensity < 254
        - **Saturated:** Pixels with intensity >= 254 (adjust exposure/gain)
        
        **Camera Alignment:**
        - X/Y error < 5%: Camera well aligned
        - X/Y error >= 5%: Camera tilted
        """)
        
    # st.markdown("---")
    
    if "uploader_key" not in st.session_state:
        st.session_state.uploader_key = 0
    if 'captured_data' not in st.session_state:
        st.session_state.captured_data = None
    
    st.divider()
    
    # Always keep buttons at the top
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        st.subheader("Capture Image")
        capture_pressed = st.button("Capture Image", width="stretch", key="capture_image")
    with col_btn2:
        st.subheader("Upload FITS file")
        fits_pressed = st.file_uploader(
            "Upload FITS file",
            type=["fits"],
            key=f"tab1_folder_files_{st.session_state.uploader_key}",
            label_visibility="collapsed",
            # width= 400
        )
            
    # Variable to control which processing path to run
    img = None
    img_original = None
    coef_folder = None
    fits_data_list = []  # Store FITS data in memory
    save_img = False  # Always initialize
    
    # Processing based on pressed button
    if capture_pressed:
        with st.spinner("Capturing image..."):
            try:
                img, img_original, fits_header = capture_image(0)
                st.session_state.captured_data = {'img': img, 'img_original': img_original, 'fits_header': fits_header}
                save_img = True
                coord_x, coord_y = None, None
            except Exception as e:
                st.error(f"Error in capture_image function: {str(e)}")
                img, img_original, fits_header = None, None, None
    
    elif fits_pressed:
        # Clear previously captured data when a FITS file is uploaded
        st.session_state.captured_data = None
        
        # Load image and FITS header
        try:
            with fits.open(fits_pressed) as hdul:
                img = hdul[0].data
                # Extract FITS header parameters (if available)
                header = hdul[0].header
                fits_header = {}
                
                # List of keywords to extract
                keywords = ['CAMERA', 'CAMSYS', 'WIDTH', 'HEIGHT', 'EXPOSURE', 'GAIN', 
                           'BRIGHT', 'CONTRAST', 'SATUR', 'FPS', 'FOURCC',
                           'FLIPMODE', 'BGR', 'GAUSIGMA', 'THRESH', 'THTYPE',
                           'SATURPX', 'MAXVAL', 'DTYPE', 'DARKFR', 'GRAY']
                
                if 'COORD_X' in header and 'COORD_Y' in header:
                    coord_x = str(header['COORD_X'])
                    coord_y = str(header['COORD_Y'])
                else:
                    coord_x = None
                    coord_y = None
                    
                if 'COEF_F' in header:
                    coef_folder = str(header['COEF_F'])
                    
                for key in keywords:
                    if key in header:
                        # Store in the same format returned by capture_image: (value, comment)
                        fits_header[key] = (header[key], header.comments[key])
                
                # If no parameter is found, keep empty
                if not fits_header:
                    fits_header = None
        except Exception as e:
            st.error(f"Error loading FITS: {str(e)}")
            img, fits_header = None, None
            coord_x, coord_y = None, None
    
    # Use session_state data if available (only if no FITS file was uploaded)
    elif st.session_state.captured_data is not None:
        img = st.session_state.captured_data['img']
        img_original = st.session_state.captured_data['img_original']
        fits_header = st.session_state.captured_data['fits_header']
        save_img = True
        coord_x, coord_y = None, None
                
    # Display results (only if img is defined)
    if img is not None:
        # Display images
        if img_original is not None:
            col1, col2 = st.columns(2)
            with col1:
                img_original = cv2.cvtColor(img_original, cv2.COLOR_BGR2RGB)
                st.image(img_original, caption='Original Image', width='stretch')
            with col2:
                st.image(img, caption='Adapted Image', width='stretch')
        else:
            st.subheader(f"File {fits_pressed.name}:")
            st.image(img, caption='Adapted Image', width='stretch')

        if fits_header is not None:
            
            
            # Display FITS header parameters in an organized layout
            with st.expander("FITS Header Parameters", expanded=False):
                if fits_header:
                    # Split into 3 columns
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.markdown("**Camera Settings**")
                        if 'CAMERA' in fits_header:
                            st.text(f"Camera: {fits_header['CAMERA'][0]}")
                        if 'CAMSYS' in fits_header:
                            st.text(f"System: {fits_header['CAMSYS'][0]}")
                        if 'WIDTH' in fits_header:
                            st.text(f"Width: {fits_header['WIDTH'][0]} px")
                        if 'HEIGHT' in fits_header:
                            st.text(f"Height: {fits_header['HEIGHT'][0]} px")
                        if 'DTYPE' in fits_header:
                            st.text(f"Data type: {fits_header['DTYPE'][0]}")
                    
                    with col2:
                        st.markdown("**Capture Parameters**")
                        if 'EXPOSURE' in fits_header:
                            st.text(f"Exposure time absolute: {fits_header['EXPOSURE'][0]} (ms)")
                        if 'GAIN' in fits_header:
                            st.text(f"Gain: {fits_header['GAIN'][0]}")
                        if 'BRIGHT' in fits_header:
                            st.text(f"Brightness: {fits_header['BRIGHT'][0]}")
                        if 'CONTRAST' in fits_header:
                            st.text(f"Contrast: {fits_header['CONTRAST'][0]}")
                        if 'SATUR' in fits_header:
                            st.text(f"Saturation: {fits_header['SATUR'][0]}")
                    
                    with col3:
                        st.markdown("**Applied Processing**")
                        if 'GRAY' in fits_header:
                            st.text(f"Grayscale: {fits_header['GRAY'][0]}")
                        if 'FLIPMODE' in fits_header:
                            st.text(f"Flip Mode: {fits_header['FLIPMODE'][0]}")
                        if 'BGR' in fits_header:
                            st.text(f"BGR: {fits_header['BGR'][0]}")
                        if 'GAUSIGMA' in fits_header:
                            st.text(f"Gauss σ: {fits_header['GAUSIGMA'][0]}")
                        if 'THRESH' in fits_header:
                            st.text(f"Threshold: {fits_header['THRESH'][0]}")
                        if 'DARKFR' in fits_header:
                            status = "Applied" if fits_header['DARKFR'][0] == 'True' else "Not applied"
                            st.text(f"Dark Frame: {status}")
                    
                    if coef_folder:
                        st.markdown("")
                        st.markdown(f"**Calibration coefficients saved in:** {coef_folder}")
                    
                    if coord_x is not None and coord_y is not None:
                        st.markdown("---")
                        st.markdown("**Real Coordinates:**")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("X Coordinate", f"{float(coord_x):.3f} mm")
                        with col2:
                            st.metric("Y Coordinate", f"{float(coord_y):.3f} mm")
                    else:
                        st.markdown("---")
                        st.markdown("Real coordinates (X, Y) **not found** in the FITS Header.")
                        
                    
        else:
            st.info("No FITS header parameters available for this image.")
            st.info(f"Dimensions: \n - Width: {img.shape[1]} px \n - Height: {img.shape[0]} px")
        
        # --- Saturation check ---
        saturated_pixels = np.sum(img >= 254)
        max_val = np.max(img)
        
        if saturated_pixels > 0:
            st.warning(f"Saturated image! Saturated pixels: {saturated_pixels}")
        else:
            if max_val == 0:
                st.warning("Maximum intensity is 0. Check the image.")
            else:
                st.success(f"No saturated pixels. Maximum intensity: {max_val}")


        height = img.shape[0]
        width = img.shape[1]
                
        N = 1  # Number of right-edge columns to consider
        right_margin = img[:, -N:]   # Select last N columns
        left_margin = img[:, :N]     # Select first N columns
        top_margin = img[:N, :]      # Select first N rows
        bottom_margin = img[-N:, :]  # Select last N rows

        sum_right = np.sum(right_margin, axis=1)
        sum_left = np.sum(left_margin, axis=1)
        sum_top = np.sum(top_margin, axis=0)
        sum_bottom = np.sum(bottom_margin, axis=0)

        dimension_right = len(np.nonzero(sum_right)[0])
        dimension_left = len(np.nonzero(sum_left)[0])
        dimension_top = len(np.nonzero(sum_top)[0])
        dimension_bottom = len(np.nonzero(sum_bottom)[0])

        # Check if there are non-zero values before calculating error
        if np.mean([dimension_right, dimension_left]) > 0:
            erro_x = abs(dimension_right - dimension_left) / np.mean([dimension_right, dimension_left]) * 100
        else:
            erro_x = 0.0  # ou np.nan

        if np.mean([dimension_top, dimension_bottom]) > 0:
            erro_y = abs(dimension_top - dimension_bottom) / np.mean([dimension_top, dimension_bottom]) * 100
        else:
            erro_y = 0.0  # ou np.nan
        
        st.header("Cross Arm Dimensions at the Edges")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Left Edge Arm Length:", f"{dimension_left} px")
            st.metric("Top Edge Arm Length:", f"{dimension_top} px")
        with col2:                
            st.metric("Right Edge Arm Length:", f"{dimension_right} px")
            st.metric("Bottom Edge Arm Length:", f"{dimension_bottom} px")
        with col3:
            st.metric("X Error:", f"{erro_x:.2f}%")
            st.metric("Y Error:", f"{erro_y:.2f}%")

        if dimension_right > dimension_left and erro_x > 10:
            horizontal = "left"
        elif dimension_left > dimension_right and erro_x > 10:
            horizontal = "right"
        else:
            horizontal = None
        
        if dimension_top > dimension_bottom and erro_y > 10:
            vertical = "down"
        elif dimension_bottom > dimension_top and erro_y > 10:
            vertical = "up"
        else:
            vertical = None

        if horizontal and vertical:
            st.warning(f"Tilted to the {horizontal}/{vertical}.")
        elif vertical and horizontal == None:
            st.warning(f"Tilted {vertical}.")
        elif horizontal and vertical == None:
            st.warning(f"Tilted to the {horizontal}.")
        else:
            st.success("The camera is aligned with the cross.")
            
        # Sum of intensities along rows (for each vertical pixel)
        histogram = np.sum(right_margin, axis=1)

        indices = np.nonzero(histogram)[0]
        if indices.size > 0:
            start = max(indices[0] - 2, 0)  # Ensure start is not negative
            end = min(indices[-1] + 3, len(histogram))  # Ensure end does not exceed array length
            histogram_cropped = histogram[start:end]
            x_cropped = np.arange(start, end)
        else:
            histogram_cropped = np.array([])  # Empty array for histogram
            x_cropped = np.array([])  # Empty array for x-coordinates

        if histogram_cropped.size > 0 and x_cropped.size > 0:
            # Plot the histogram
            st.header("Right Edge Intensity Profile")
            fig, ax = plt.subplots()
            ax.plot(height - x_cropped, histogram_cropped)

            ax.set_xlabel("Right-edge pixels with non-zero intensity")
            ax.set_ylabel("Intensity")
            st.pyplot(fig)
        else:
            st.warning("Not enough data to plot the histogram.")
        
        if save_img:
            st.divider()
            if st.button("Save image", width="stretch"):
                try:
                    with st.spinner("Saving image..."):
                        fits_path = create_folder(fits_dir)
                        img_path = create_folder(img_dir)
                        fits_path = save_fits(img, fits_path, header_params=fits_header)
                        png_path = save_png(img, img_path, "adapted")
                        st.info(f"Image and Fits saved successfully! \n - FITS: {fits_path} \n - PNG: {png_path}")
                except Exception as e:
                    st.error(f"Error saving image: {str(e)}")

with tab2:
    st.header("Image Processing (px)")
    col1, col2 = st.columns([2, 1])
    with col1:
        with st.expander("Instructions", type="step"):
            st.markdown("""
            ### **Objective:**
            Process FITS files and compute cross-center coordinates in **pixels**.
            
            ### **How to use:**
            
            **File Selection:**
            1. **Upload** a FITS file
            2. Press **"Clear Files"** to restart selection
            
            **Visualization Options:**
            - **Figures:** Enable/disable visualization of processing figures
            - **Data:** Enable/disable visualization of numeric data
            
            ### **Algorithm:**
            
            1. **Initial estimate:** Locates the 4 cross ends (top, right, bottom, left) and obtains approximate line equations for horizontal and vertical arms.
            2. **Point lists:** With the line equations, computes intensity centroids, along each arm, to build two precise coordinate lists.
            3. **Line fitting:** Computes fit lines from those two lists, considering error weighting based on point relevance.
            4. **Final center:** The intersection of fitted lines is the center (i, j) in pixels with sub-pixel precision.
            
            ### **Displayed Results:**
            
            **Processing Figure:**
            - Cross image visualization
            - Detected centroid points on each arm (red: horizontal, blue: vertical)
            - Computed center coordinates (i, j) in pixels
            
            **Numeric Data:**
            
            **Cross Center:**
            - Computed center coordinates (i, j) in pixels
            
            **Cross Ends:**
            - Coordinates of the 4 ends (Top, Right, Bottom, Left)
            
            **Fit Parameters:**
            - **Slope (m):** Line slope ± error
            - **Intercept (b):** Axis intercept ± error
            - **χ²:** Fit quality (reduced chi-square)
            """)
    
    # Initialize session_state for expander options
    if 'fig_option' not in st.session_state:
        st.session_state.fig_option = True
    if 'data_option' not in st.session_state:
        st.session_state.data_option = True
    if "uploader_key" not in st.session_state:
        st.session_state.uploader_key = 0
    
    with col2:
        with st.expander("Result Options", type="step"):
            # Create checkboxes with callback to update session_state
            fig_option = st.checkbox("Figures", value=st.session_state.fig_option, key="cb_figuras")
            data_option = st.checkbox("Data", value=st.session_state.data_option, key="cb_data")
            
            # Update session_state
            st.session_state.fig_option = fig_option
            st.session_state.data_option = data_option

    st.divider()
    
    col1, col2 = st.columns([5, 0.92])
    
    with col1:
        st.subheader("Choose FITS File", help= "Use Shift+Click to select consecutive files or Ctrl+Click to select multiple individual files")
        files_pressed = st.file_uploader(
            "Select ALL .fits files from the folder",
            type=["fits"],
            # accept_multiple_files=True,
            key=f"tab2_folder_files_{st.session_state.uploader_key}",
            label_visibility="collapsed",
        )
    
    with col2:
        st.subheader("")
        if st.button("Clear Files", help="Remove all selected files", key="clear_files", width= "stretch", ):
            st.session_state.uploader_key += 1
            st.rerun() # Restart page, clearing file_uploader
            
    # Variable to control which processing path to run
    fits_data_list = []
    
    if files_pressed:
        
        # Process files uploaded directly from memory
        try:
            # Create a BytesIO object from uploaded file
            file_bytes = BytesIO(files_pressed.getvalue())
            
            # Open directly from BytesIO
            with fits.open(file_bytes) as hdul:
                fits_data_list.append({
                    'filename': files_pressed.name,
                    'data': hdul[0].data.astype(float),
                    'source': 'upload_folder'
                })
                
        except Exception as e:
            st.error(f"Error loading {files_pressed.name}: {str(e)}")
        
        # Sort by filename
        fits_data_list.sort(key=lambda x: x['filename'])

    # FITS DATA PROCESSING
    if fits_data_list:  # Only process if files exist
        
        results = []
        erros_i = []  
        erros_j = []  
        dados_tabela = []
        data_estatistica = []
        figuras = []
        
        with st.spinner("Processing FITS files..."):
            for idx, fits_info in enumerate(fits_data_list, start=1):
                data = fits_info['data']
                filename = fits_info['filename']
                
                saturated_pixels = np.sum(data >= 254)
                intensidade = np.max(data)
                
                # compute_calibration can return a figure, capture it
                result = compute_calibration(data, calib=False)
                results.append(result)

                # Capture figure if it was created
                if st.session_state.fig_option and 'figure' in result:  # If matplotlib figures are open
                    fig_atual = result['figure']  # Get current figure
                    figuras.append({
                        'figura': fig_atual,
                        'titulo': f'FITS {idx}: {filename}',
                        'indice': idx
                    })
                    plt.close(fig_atual)  # Close figure to free memory
                    plt.figure()  # Create a new figure for next processing

                # Dados
                data = {
                    "File": filename,
                    "i (px)": f"{result['center_pixel_points'][0]:.3f}",
                    "j (px)": f"{result['center_pixel_points'][1]:.3f}",
                    "i (theoretical)": "-",
                    "j (theoretical)": "-",
                    "i Error (px)": "-",
                    "j Error (px)": "-"
                }
                
                data_estatistica.append(data)

            # Display figures in an organized layout
            if st.session_state.fig_option and figuras:
                if len(figuras) > 1:
                    st.subheader("Processing Figures")
                    num_colunas = 3
                    st.subheader("Cross-center coordinates in pixels")
                    st.text(f"(i, j) = ({result['center_pixel_points'][0]:.3f}, {result['center_pixel_points'][1]:.3f})")
                    for i in range(0, len(figuras), num_colunas):
                        cols = st.columns(num_colunas)
                        for j in range(num_colunas):
                            if i + j < len(figuras):
                                figura_info = figuras[i + j]
                                with cols[j]:
                                    st.pyplot(figura_info['figura'])
                                    st.write(f"**{figura_info['titulo']}**")
                                    
                else:
                    for figura_info in figuras:
                        st.pyplot(figura_info['figura'])
                        st.write(f"**File Name:** {figura_info['titulo']}")

        # Create and display the table
        if data:
            st.subheader("Processing Results")
            
            # Center coordinates
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Cross Center Coordinates:**")
                st.metric("i Coordinate", f"{result['center_pixel_points'][0]:.3f} px")
                st.metric("j Coordinate", f"{result['center_pixel_points'][1]:.3f} px")
            
            with col2:
                st.markdown("**End Coordinates:**")
                end_df = pd.DataFrame({
                    "End": ["Top", "Left", "Bottom", "Right"],
                    "i (px)": [f"{result['end_i_fit'][0]:.3f}", f"{result['end_i_fit'][1]:.3f}", 
                               f"{result['end_i_fit'][2]:.3f}", f"{result['end_i_fit'][3]:.3f}"],
                    "j (px)": [f"{result['end_j_fit'][0]:.3f}", f"{result['end_j_fit'][1]:.3f}", 
                               f"{result['end_j_fit'][2]:.3f}", f"{result['end_j_fit'][3]:.3f}"]
                })
                
                styled_end = end_df.style.set_properties(**{
                    'text-align': 'center'
                }).set_table_styles([
                    {'selector': 'th', 'props': [('text-align', 'center'), ('font-weight', 'bold')]},
                    {'selector': 'td', 'props': [('text-align', 'center')]}
                ])
                
                st.dataframe(styled_end, width='stretch', hide_index=True)
            
            # Fit parameters
            st.markdown("---")
            st.markdown("**Fit Parameters:**")
            
            fithor = result['horizontal_fit_parameters']
            fitver = result['vertical_fit_parameters']
            
            fit_df = pd.DataFrame({
                "Parameter": ["Slope (m)", "Intercept (b)", "χ²"],
                "Horizontal": [
                    f"{fithor[0]:.3f} ± {fithor[2]:.3f}",
                    f"{fithor[1]:.3f} ± {fithor[3]:.3f}",
                    f"{fithor[4]:.2e}"
                ],
                "Vertical": [
                    f"{fitver[0]:.3f} ± {fitver[2]:.3f}",
                    f"{fitver[1]:.3f} ± {fitver[3]:.3f}",
                    f"{fitver[4]:.2e}"
                ]
            })
            
            styled_fit = fit_df.style.set_properties(**{
                'text-align': 'center'
            }).set_table_styles([
                {'selector': 'th', 'props': [('text-align', 'center'), ('font-weight', 'bold')]},
                {'selector': 'td', 'props': [('text-align', 'center')]}
            ])
            
            st.dataframe(styled_fit, width='stretch', hide_index=True)
                
with tab3:
    st.header("Image Processing (mm)")
    col1, col2 = st.columns([2, 1])
    with col1:
        with st.expander("Instructions", type="step"):
            st.markdown("""
            ### **Objective:**
            Process FITS files and compute real coordinates (x, y) in millimeters using calibration coefficients ( $$\\alpha_x$$ , $$\\alpha_y$$ ).
            
            **Linear Calibration Equation:**
            
            $$x = \\alpha_x[0] \\cdot i + \\alpha_x[1] \\cdot j + \\alpha_x[2]$$
            
            $$y = \\alpha_y[0] \\cdot i + \\alpha_y[1] \\cdot j + \\alpha_y[2]$$
            
            ### **How to use:**
            
            **FITS File Selection:**
            1. **Upload** one or multiple  files
            2. Use **Shift+Click** to select consecutive files or drag
            3. Press **"Clear Files"** to restart selection
                    
            **Calibration Coefficients Selection:**
            1. By default, the app automatically extracts the respective calibration coefficients (if available in the FITS header)
            2. To use another set of coefficients, upload a .json file.
            
            **Visualization Options:**
            - **Figures:** Enable/disable visualization of processing figures
            - **Data:** Enable/disable visualization of numeric data
            
            ### **Calculation Process:**
            
            **Processing Algorithm:**
            1. **Pixel detection:** Gets cross-center pixel coordinates (i,j) with sub-pixel precision (explained in **Image processing**).
            2. **Coefficient extraction:** Extracts folder name containing calibration coefficients ( $$\\alpha_x$$ , $$\\alpha_y$$ ) from FITS header or uploaded .json file. 
            2. **Calibration:** Applies calibration to convert center (i, j) -> (x, y) in mm.        
            3. **Comparison:** Computes absolute error between calculated and real coordinates previously stored in FITS file header.
            4. **Statistical analysis:** Provides precision metrics (mean, maximum).
            
            ### **Displayed Results:**
            
            **Processing Figures:**
            - Cross visualization with fitted lines
            - Computed center in millimeters
            
            **Results Table:**
            - **File:** Processed file number
            - **X/Y Milling Machine (mm):** Real coordinates extracted from filename
            - **X/Y Computed (mm):** Coordinates computed by system
            - **X/Y Error (mm):** Absolute difference between milling machine and computed
            
            **Cells with error > 0.050 mm are highlighted in red.**
            
            **Statistics** (multiple files):
            - Percentage of errors below 0.050 mm
            - Mean errors in X and Y
            - Maximum error found on each axis
            """)
        
    
    # Initialize session_state for expander options
    if 'fig_option' not in st.session_state:
        st.session_state.fig_option = True
    if 'data_option' not in st.session_state:
        st.session_state.data_option = True
    if "uploader_key" not in st.session_state:
        st.session_state.uploader_key = 0
    
    with col2:
        with st.expander("Result Options", type="step"):
            # Create checkboxes with callback to update session_state
            fig_option = st.checkbox("Figures", value=st.session_state.fig_option, key="figuras")
            data_option = st.checkbox("Data", value=st.session_state.data_option, key="data")
            
            # Update session_state
            st.session_state.fig_option = fig_option
            st.session_state.data_option = data_option
    
    st.divider()
        
    col1, col2, col3 = st.columns([4, 4, 1.5])
    with col1:
        st.subheader("Choose FITS files", help= "Use Shift+Click to select consecutive files or Ctrl+Click to select multiple individual files")
        files_pressed = st.file_uploader(
            "Select .fits files",
            type=["fits"],
            accept_multiple_files=True,
            key=f"tab3_folder_files_{st.session_state.uploader_key}", 
            label_visibility="collapsed"
            )
        
    with col2:
        st.subheader("Choose Calibration Coefficients", help= "Must be a json file.")
        json_file = st.file_uploader(
                "Choose Calibration Coefficients",
                type=["json"],
                label_visibility="collapsed"
                )
    with col3:
        st.subheader("")
        if st.button("Clear Files", help="Remove all selected files", key="clear_files_2", width= "stretch"):
            st.session_state.uploader_key += 1  # change key -> widget resets
            st.rerun() # Restart page, clearing file_uploader

    # Variable to control which processing path to run
    fits_data_list = []  # Store FITS data in memory

    if files_pressed:
        
        # Process files uploaded directly from memory
        for uploaded_file in files_pressed:
            try:
                # Create a BytesIO object from uploaded file
                file_bytes = BytesIO(uploaded_file.getvalue())
                
                # Open directly from BytesIO
                with fits.open(file_bytes) as hdul:
                    fits_data_list.append({
                        'filename': uploaded_file.name,
                        'data': hdul[0].data.astype(float),
                        'source': 'upload_folder',
                        'x_fresadora': float(hdul[0].header['COORD_X']) if 'COORD_X' in hdul[0].header else None,
                        'y_fresadora': float(hdul[0].header['COORD_Y']) if 'COORD_Y' in hdul[0].header else None,
                        'coef_folder': hdul[0].header['COEF_F'] if 'COEF_F' in hdul[0].header else None
                    })
                                    
            except Exception as e:
                st.error(f"Error loading {uploaded_file.name}: {str(e)}")
        
        # Sort by filename
        fits_data_list.sort(key=lambda x: x['filename'])

    # Only process if files exist
    if fits_data_list:
        
        if len(files_pressed) > 1:
            st.success(f"{len(files_pressed)} files selected")
        else:
            st.success("1 file selected")
        
        
        # Check whether to use JSON path from FITS header
        json_path_from_header = None
        
        if json_file is not None:
            st.info(f"Using selected calibration coefficients.")

        elif fits_data_list[0]['coef_folder'] is not None:
            
            # Build JSON path
            json_path_from_header = os.path.join(json_dir, fits_data_list[0]['coef_folder'], "calibration_coeffs.json")
            
            # Check if file exists
            if os.path.exists(json_path_from_header):
                st.info(f"Using calibration coefficients from FITS Header: {fits_data_list[0]['coef_folder']}")
            else:
                st.warning(f"Coefficients folder '{fits_data_list[0]['coef_folder']}' found in FITS header but JSON file does not exist.")
                json_path_from_header = None

                
        results = []
        error_x = []  
        error_y = []  
        erros = []
        dados_tabela = []
        figuras = []
            
        with st.spinner("Processing FITS files..."):
            
            for idx, fits_info in enumerate(fits_data_list, start=1):
                
                data = fits_info['data']
                filename = fits_info['filename']
                
                saturated_pixels = np.sum(data >= 254)
                intensidade = np.max(data)
                
                if json_file is None and json_path_from_header is None:
                    st.warning("No calibration coefficients file selected or found in FITS header.")
                    st.stop()
                    
                # compute_calibration may return a figure
                if json_file is not None:
                    # Create temporary JSON file
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
                        tmp.write(json_file.getvalue())
                        tmp_path = tmp.name
                        
                    result = compute_calibration(data, calib=True, json_file=tmp_path)
                elif json_path_from_header is not None:
                    # Use JSON from FITS header
                    result = compute_calibration(data, calib=True, json_file=json_path_from_header)
                    
                    
                results.append(result)
                
                x_fresadora = fits_info['x_fresadora']
                y_fresadora = fits_info['y_fresadora']
                
                # Update file name with formatted coordinates
                filename = f"X{x_fresadora:.3f}_Y{y_fresadora:.3f}.fits"
                
                # Capture figure if it was created
                if st.session_state.fig_option and 'figure' in result:  # If matplotlib figures are open
                    fig_atual = result['figure']  # Get current figure
                    figuras.append({
                        'figura': fig_atual,
                        'titulo': f'FITS {idx}: {filename}',
                        'indice': idx
                    })
                    plt.close(fig_atual)  # Close figure to free memory
                    plt.figure()  # Create a new figure for next processing
                    
                # Prepare row data for the table
                linha_tabela = {
                    "File": idx,
                    "X Milling (mm)": f"{x_fresadora:.3f}",
                    "Y Milling (mm)": f"{y_fresadora:.3f}",
                    "X Computed (mm)": f"{result['center_real_points'][0]:.3f}",
                    "Y Computed (mm)": f"{result['center_real_points'][1]:.3f}",
                    "X Error (mm)": "-",
                    "Y Error (mm)": "-"
                }

                if saturated_pixels == 0:
                                    
                    erro_x = abs(x_fresadora - result['center_real_points'][0])
                    erro_y = abs(y_fresadora - result['center_real_points'][1])
                
                    error_x.append(erro_x)
                    error_y.append(erro_y)
                    erros.append((erro_x, erro_y))

                    # Update error values in table row
                    linha_tabela["X Error (mm)"] = f"{erro_x:.3f}"
                    linha_tabela["Y Error (mm)"] = f"{erro_y:.3f}"
                else:
                    st.warning(f"File {idx}: Has saturated pixels")
                
                dados_tabela.append(linha_tabela)
            
            # Display figures in an organized layout
            if st.session_state.fig_option:
                if len(figuras) > 1:
                    st.subheader("Processing Figures")
                    num_colunas = 3
                    for i in range(0, len(figuras), num_colunas):
                        cols = st.columns(num_colunas)
                        for j in range(num_colunas):
                            if i + j < len(figuras):
                                figura_info = figuras[i + j]
                                with cols[j]:
                                    st.pyplot(figura_info['figura'])
                                    st.write(f"**{figura_info['titulo']}**")
                else:
                    for figura_info in figuras:
                        st.pyplot(figura_info['figura'])
                        st.write(f"**File Name:** {figura_info['titulo']}")


        # Create and display the table
        st.subheader("Results Table")
        df = pd.DataFrame(dados_tabela)
        df.set_index('File', inplace=True)
        
        # Convert error columns to float
        df['X Error (mm)'] = pd.to_numeric(df['X Error (mm)'], errors='coerce').round(3)
        df['Y Error (mm)'] = pd.to_numeric(df['Y Error (mm)'], errors='coerce').round(3)

        def red_color(val):
            if val >= 0.05:
                return 'background-color: rgba(255, 0, 0, 0.3)'  # red with 30% opacity
            else:
                return ''
        
        # Identify non-float columns (i.e., not "Error" columns)
        colunas_nao_float = [c for c in df.columns if c not in ['X Error (mm)', 'Y Error (mm)']]

        styled_df = (
            df.style
            .map(red_color, subset=['X Error (mm)', 'Y Error (mm)'])
            .format({
                'X Error (mm)': '{:.3f}',
                'Y Error (mm)': '{:.3f}'
            })
            .set_properties(subset=colunas_nao_float,**{'text-align': 'center'})
            .set_table_styles([
                {'selector': 'th', 'props': [('text-align', 'center'), ('font-weight', 'bold')]},
                {'selector': 'td', 'props': [('text-align', 'center')]}
            ])
)

        
        # Compute dynamic height
        altura = len(df) * 39  # 40 px per row

        st.dataframe(styled_df, width='stretch')

        # Compute and display error statistics
        if len(files_pressed) > 1:
            if error_x and error_y:
                mean_error_x = np.mean(error_x)
                mean_error_y = np.mean(error_y)
                max_error_x = np.max(error_x)
                max_error_y = np.max(error_y)
                
                # Calculate error magnitude (Euclidean distance)
                errors_magnitude = np.sqrt(np.array(error_x)**2 + np.array(error_y)**2)
                
                # Count how many errors are below 50um (0.050 mm)
                num_total = len(errors_magnitude)
                num_below_50um = np.sum(errors_magnitude < 0.050)
                percentage_below_50um = (num_below_50um / num_total) * 100
                
                st.subheader("Statistics")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Accuracy:", f"{percentage_below_50um:.2f}%")
                with col2:
                    st.metric("Mean X Error:", f"{mean_error_x:.3f} mm")
                    st.metric("Maximum X Error:", f"{max_error_x:.3f} mm")
                with col3:
                    st.metric("Mean Y Error:", f"{mean_error_y:.3f} mm")
                    st.metric("Maximum Y Error:", f"{max_error_y:.3f} mm")
            else:
                st.warning("No error was computed due to saturation or other issues.")
        