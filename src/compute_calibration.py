"""
compute_calibration.py

Detect cross center and orientation from image data, with optional pixel-to-mm calibration.
"""


# Import fallback for standalone and package execution
try:
    # Relative import (when executed from another module)
    from src.utils import getcross, twodcut, straightlinefit, xcen, xver, yhor, pixel_to_real
    from src.paths import fits_calib_dir, json_dir
except ImportError:
    # Fallback for standalone execution in the same folder
    from utils import getcross, twodcut, straightlinefit, xcen, xver, yhor, pixel_to_real
    from paths import fits_calib_dir, json_dir

import matplotlib.pyplot as plt
from astropy.io import fits
import numpy as np
import math
import glob
import os



# --- Configuration parameters ---

delta = 2 # cut thickness used by twodcut
sq = 50 # band width for cross-arm centroid estimation used in fitting


def compute_calibration(results, calib=False, json_file=None):
    """
    Compute cross center and angle from a 2D image using cross ends detection and line fitting.
    """


    # --- 1. Cross end localization (px) ---
        
    # Define vertical and horizontal cuts near image borders.
    # The location of the maximum intensity pixel in each cut corresponds to an estimate of each cross end.
    # function: twodcut(files, xcenter, ycenter, angle, width)
    
    # Image dimensions
    height = results.shape[0] 
    width = results.shape[1]

    # Store coordinates (x, y) of the 4 cross ends.
    ends_i = np.zeros(4)
    ends_j = np.zeros(4)    
    
    # Vertical cut at (width/2, height - delta): top end
    top_end = twodcut(results, int(width/2), height - delta, 90, 2 * delta)
    ends_i[0] = np.argmax(top_end)
    ends_j[0] = height - delta
    
    # Horizontal cut at (delta, height/2): left end
    left_end = twodcut(results, delta, int(height/2), 0, 2 * delta)
    ends_i[1] = delta
    ends_j[1] = np.argmax(left_end)

    # Vertical cut at (width/2, delta): bottom end
    bottom_end = twodcut(results, int(width/2), delta, 90, 2 * delta)
    ends_i[2] = np.argmax(bottom_end)
    ends_j[2] = delta

    # Horizontal cut at (width - delta, height/2): right end
    right_end = twodcut(results, width - delta, int(height/2), 0, 2 * delta)
    ends_i[3] = width - delta
    ends_j[3] = np.argmax(right_end)


    # --- 2. Cross center and angle estimation (px) ---
    
    slope_ij, center_i, center_j = getcross(ends_i, ends_j)
    angle_deg_ij = math.degrees(math.atan(slope_ij))
     
    
    # --- 3. Build bands along each cross arm ---

    # Use estimated end coordinates to define arm equations (yhor/xver) and sample
    # centroids along each arm. Points with centroid=None are skipped.

    # Horizontal cross arm
    list_i_hor = []
    list_j_hor = []
    list_errors_i_hor = []
    list_errors_j_hor = []

    for i in range(width):
        yy0_val = yhor(i, ends_i, ends_j)
        y_center = int(yy0_val)
        y_start = max(0, y_center - sq)
        y_end = min(results.shape[0], y_center + sq)
        LINE = results[y_start:y_end, i]
        c = xcen(LINE)
        
        if c is None:
            continue

        list_i_hor.append(i)
        list_j_hor.append(c + y_start)
        
        if abs(i - center_i) < sq:
            list_errors_i_hor.append(100000)
            list_errors_j_hor.append(100000)
        else:
            list_errors_i_hor.append(1)
            list_errors_j_hor.append(1)
        
    
    # Vertical cross arm
    list_i_ver = []  
    list_j_ver = []
    list_errors_i_ver = []
    list_errors_j_ver = []

    for i in range(height):
        xx0_val = xver(i, ends_i, ends_j)
        x_center = int(xx0_val)
        x_start = max(0, x_center - sq)
        x_end = min(results.shape[1], x_center + sq)
        LINE = results[i, x_start:x_end]
        c = xcen(LINE)
        
        if c is None:
            continue

        list_j_ver.append(i)
        list_i_ver.append(c + x_start)
        
        if abs(i - center_j) < sq:
            list_errors_i_ver.append(100000)
            list_errors_j_ver.append(100000)
        else:
            list_errors_i_ver.append(1)
            list_errors_j_ver.append(1)

    
    
    # --- 4. Line fitting for cross arms (px) ---
    
    fithor = straightlinefit(np.array(list_i_hor), np.array(list_j_hor), np.array(list_errors_i_hor), np.array(list_errors_j_hor))
    fitver = straightlinefit(np.array(list_j_ver), np.array(list_i_ver), np.array(list_errors_j_ver), np.array(list_errors_i_ver))
    
    
    # --- 5. Compute fitted end (px) ---
    
    # Index: [0]=top, [1]=left, [2]=bottom, [3]=right
    
    end_i_fit = np.zeros(4)
    end_j_fit = np.zeros(4)
        
    # 1st point: top end (y=height), x from fitted vertical line
    end_j_fit[0] = height - 1
    end_i_fit[0] = fitver[0]*end_j_fit[0] + fitver[1]

    # 2nd point: left end (x=0), y from fitted horizontal line
    end_i_fit[1] = 0
    end_j_fit[1] = fithor[0]*end_i_fit[1] + fithor[1]
    
    # 3rd point: bottom end (y=0), x from fitted vertical line
    end_j_fit[2] = 0
    end_i_fit[2] = fitver[0]*end_j_fit[2] + fitver[1]

    # 4th point: right end (x=width), y from fitted horizontal line
    end_i_fit[3] = width - 1
    end_j_fit[3] = fithor[0]*end_i_fit[3] + fithor[1]

        
    # --- 6. Compute fitted cross center (px) ---
    
    slope_ij_fit, center_i_fit, center_j_fit = getcross(end_i_fit, end_j_fit)
    angle_deg_ij_fit = math.degrees(math.atan(slope_ij_fit))
    center_pixel_points = np.array([center_i_fit, center_j_fit])
           
           
    # --- 7. Build fitted plot (px) ---
    
    figure, ax = plt.subplots(figsize=(7, 7))
    # By default, image display starts at top-left (0,0) with Y increasing downward.
    # origin='lower' flips visualization to bottom-left origin while preserving coordinates.
    im = ax.imshow(results, cmap='gray', origin='lower')
    figure.colorbar(im, ax=ax, label='Intensity', shrink=0.8)

    # Plot sampled points used in fitting
    ax.plot(list_i_hor, list_j_hor, 'r.', markersize=0.07, label='Horizontal points') 
    ax.plot(list_i_ver, list_j_ver, 'b.', markersize=0.07, label='Vertical points')

    # Display center text on lower-left corner
    center_text = f"Center: ({center_i_fit:.3f}, {center_j_fit:.3f})"
    ax.text(
        0.02, 0.02,
        center_text,
        transform=ax.transAxes,
        color='white',
        fontsize=10,
        weight='bold',
        verticalalignment='bottom',
        bbox=dict(facecolor='black', alpha=0.5, boxstyle='round,pad=0.3')
    )
    
    ax.set_title("Processed Image", fontsize=14, weight='bold', pad=15)
    ax.set_xlabel("X", fontsize=12)
    ax.set_ylabel("Y", fontsize=12)
    figure.tight_layout()
    # plt.show()



    # --- 8. Cross center calibration (mm) ---
    
    # If calib=True, convert center coordinates from pixels to mm.
    
    if calib == True:
        if json_file is None:
            raise ValueError("compute_calibration with calib=True requires 'json_file' path.")

        center_x, center_y = pixel_to_real(center_i_fit, center_j_fit, json_file=json_file)
            
        center_real_points = np.array([center_x, center_y])
            
                   
    result = {
        "center_pixel_points": center_pixel_points,
        "end_i_fit": end_i_fit, "end_j_fit": end_j_fit,        
        "slope_ij_fit": slope_ij_fit,
        "angle_deg_ij_fit": angle_deg_ij_fit,
        "shape": (width, height),
        "figure": figure,
        "horizontal_fit_parameters": fithor,
        "vertical_fit_parameters": fitver,
        "num_horizontal_points": len(list_i_hor),
        "num_vertical_points": len(list_i_ver),
    }
    if calib:
        result.update({
            "center_real_points": center_real_points
        })
        
        
    return result



if __name__ == "__main__":
                        
    # To test the function, we can run this script directly.
    
    # Open a specific subfolder within the directory
    subfolder_name = "capture_fits_test"                         # Set the subfolder name to use
    selected_dir = os.path.join(fits_calib_dir, subfolder_name)  # Full path to the subfolder
    fits_files = glob.glob(os.path.join(selected_dir, '*.fits')) # List all .fits files in selected subfolder
    
    # Alternatively, to search a specific file:
    # fits_files = glob.glob(os.path.join(fits_calib_dir, 'capture_fits_test', 'X-1.084_Y0.813.fits'))
    
    fits_files.sort(key=os.path.getmtime)                        # Sort files by modification time (oldest to newest)


    print(f"Files found: {len(fits_files)}")
    
    results_list = []
    print(f"\n=== DEBUG ===")
    for idx, fits_path in enumerate(fits_files, start=1):
        print(f"\nProcessing {idx}/{len(fits_files)}: {os.path.basename(fits_path)}")
        with fits.open(fits_path) as hdul:
            x_fres = hdul[0].header.get('COORD_X')
            y_fres = hdul[0].header.get('COORD_Y')
            data = hdul[0].data.astype(float)
            json_path = os.path.join(json_dir, "calibration_test", "calibration_coeffs.json")
            result = compute_calibration(data, json_file=json_path, calib=True) # Set the JSON file path to use for calibration
            results_list.append(result)
            
            i_center, j_center = result['center_pixel_points']
            x_center, y_center = result.get('center_real_points', (None, None))
            num_hor = result['num_horizontal_points']
            num_ver = result['num_vertical_points']
            num_hor_perc = num_hor / result['shape'][0] * 100
            num_ver_perc = num_ver / result['shape'][1] * 100
            print(f"  Center in pixels:  ({i_center:.2f}, {j_center:.2f})")
            print(f"  Center in mm:      ({x_center:.2f}, {y_center:.2f})")
            print(f"  Horizontal points: {num_hor} / {result['shape'][0]} ({num_hor_perc:.1f}%)")
            print(f"  Vertical points:   {num_ver} / {result['shape'][1]} ({num_ver_perc:.1f}%)")
                            
        