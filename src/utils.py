"""
utils.py

This module contains Auxiliary functions for optimization, calibration and image processing.

## Basic Functions
1. create_folder - Create timestamped folders to save outputs.
2. save_png - Save PNG images with timestamp or coordinates.
3. save_fits - Save FITS files with custom headers and timestamp/coordinates.
4. name_file - Generate a filename from real-world coordinates (mm).

## Calibration Functions
5. linear_calibration - Linear/affine calibration (6 coefficients).
7. pixel_to_real - Convert pixel coordinates to real-world coordinates (pixels → mm).
8. real_to_pixel - Convert real-world coordinates to pixel coordinates (mm → pixels).
9. extract_xy_filename - Extract X and Y coordinates from filenames.

## Image Processing Functions
10. getcross - Compute cross center and tilt from its end.
11. yhor - Linear interpolation for the horizontal cross arm.
12. xver - Linear interpolation for the vertical cross arm.
13. xcen - Compute centroid (center of mass) of a 1D vector.
14. twodcut - Extract orthogonal 1D cuts from 2D images (0°, 90°, 180°, 270°).
15. straightlinefit - Fit a line considering errors on both axes (orthogonal regression/ODR).
"""

try:
    # Try relative import (when run standalone)
    from src.paths import fits_dir, img_dir, data_dir, calib_dir, synt_dir, img_synt_dir, test_dir, img_calib_dir, fits_calib_dir, json_dir, data_calib_dir
except ImportError:
    # Fallback to absolute import (when used as a module)
    from paths import fits_dir, img_dir, data_dir, calib_dir, synt_dir, img_synt_dir, test_dir, img_calib_dir, fits_calib_dir, json_dir, data_calib_dir

from scipy.odr import ODR, Model, RealData         # for orthogonal regression (ODR)
from datetime import datetime
from astropy.io import fits
from pathlib import Path
import numpy as np
import datetime
import json
import cv2
import os
import re

# --- Basic Auxiliary Functions ---

def create_folder(path=None, timestamp=None):    
    """Create a timestamped folder for saving outputs."""
    
    if timestamp is None:
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M')
        
    possible_paths = [fits_dir, img_dir, data_dir, calib_dir, synt_dir, img_synt_dir, test_dir, img_calib_dir, fits_calib_dir, json_dir, data_calib_dir]

    if path is None:
        raise ValueError("create_folder error: a valid directory must be provided.")
    
    if path in possible_paths: 
        session_dir = Path(path) / f"capture_{timestamp}"
        session_dir.mkdir(parents=True, exist_ok=True)
    else:
        raise ValueError("create_folder error: unrecognized directory (see paths.py).")
    
    return session_dir


def save_png(file, dest, type, coord=None, timestamp=None):
    """Save an image as PNG using coordinates or timestamp naming."""
    
    img_types = ["adapted", "original", "fig"] 
    
    if type not in img_types:
        raise ValueError(f"save_png error: type '{type}' is not supported. Use 'adapted', 'original', or 'fig'.")
    
    # Ensure destination folder exists
    os.makedirs(dest, exist_ok=True)
    
    if coord:
        try:
            x, y = coord
            filename = f"X{x:.3f}_Y{y:.3f}_{type}_img.png"
        except Exception as e:
            raise ValueError(f"save_png error: could not parse coordinates (x, y) from 'coord' argument."
                                f" Details: {e}")
    else:
        if timestamp is None:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"img_{type}_{timestamp}.png"

    # Full PNG file path
    png_dest = os.path.join(str(dest), filename)
    
    # Save as PNG
    success = cv2.imwrite(png_dest, file)
    
    if not success:
        raise IOError(f"save_png error: failed to save PNG at: {png_dest}")
    
    return png_dest
    

def save_fits(file, dest, header_params=None, coord=None, timestamp=None):
    """Save an array as a FITS file with optional header metadata."""
    
    # Ensure destination folder exists
    os.makedirs(dest, exist_ok=True)
        
    # Create a PrimaryHDU object to store the image data
    hdu = fits.PrimaryHDU(file)
                
    # Add camera/processing parameters to header when provided
    if header_params:
        for key, (value, comment) in header_params.items():
            try:
                hdu.header[key] = value
                hdu.header.comments[key] = comment
            except Exception as e:
                print(f"Warning: could not add '{key}' to FITS header: {e}")
    
    if coord:
        try:
            x, y = coord
        except Exception as e:
            raise ValueError(f"save_fits error: could not parse coordinates (x, y) from 'coord' argument."
                                f" Details: {e}")
        fits_dest = os.path.join(str(dest), f"X{x:.3f}_Y{y:.3f}.fits")
    else:
        if timestamp is None:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        fits_dest = os.path.join(str(dest), f"fits_{timestamp}.fits")
                
    # Save FITS file
    hdu.writeto(fits_dest, overwrite=True)
        
    return fits_dest


def name_file(x, y):
    """Return a FITS filename from real-world coordinates (mm)."""
    return f"X{x:.3f}_Y{y:.3f}.fits"


# --- Linear Calibration Auxiliary Functions ---


def linear_calibration(pixel_points, real_points, coef_folder=None, timestamp=None):
    """
    Linear calibration to transform pixel coordinates into real-world coordinates.
    Uses np.linalg.lstsq, which solves linear systems with least squares.
    Useful when there is no exact solution (for example, more equations than unknowns).

    np.linalg.lstsq returns:
    - coefficients (system solution)
    - residuals (difference between real and estimated values)
    - number of linearly independent rows/columns
    - singular values of the coefficient matrix (useful for numerical stability analysis)
    
    For points, it computes affine transformation coefficients:
        x = α_x[0]*i + α_x[1]*j + α_x[2]
        y = α_y[0]*i + α_y[1]*j + α_y[2]
    """
    
    # Create folder to save coefficients
    if timestamp is None:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
    folder_name = f"calibration_{timestamp}"
    session_dir = os.path.join(json_dir, folder_name)
    os.makedirs(session_dir, exist_ok=True)
    
    if pixel_points is None or real_points is None:
        raise ValueError("pixel_points and real_points must be provided to linear_calibration.")

    pixel_points = np.asarray(pixel_points)
    real_points = np.asarray(real_points)

    # points (N,2)
    # if pixel_points.ndim == 2 and pixel_points.shape[1] == 2 and real_points.shape[1] == 2:
    if pixel_points.shape[1] == 2 and real_points.shape[1] == 2:
        
        i = pixel_points[:, 0]
        j = pixel_points[:, 1]
        x = real_points[:, 0]
        y = real_points[:, 1]

        # Affine model: [i, j, 1]
        A = np.hstack([i[:, np.newaxis], j[:, np.newaxis], np.ones((i.size, 1))])

        # For X
        alpha_x, resid_x, rank_x, s_x = np.linalg.lstsq(A, x, rcond=None)
        # For Y
        alpha_y, resid_y, rank_y, s_y = np.linalg.lstsq(A, y, rcond=None)
        
        
        # VALIDATION
        coord_i = pixel_points[:, 0]
        coord_j = pixel_points[:, 1]
        x_estimated = alpha_x[0]*coord_i + alpha_x[1]*coord_j + alpha_x[2]
        y_estimated = alpha_y[0]*coord_i + alpha_y[1]*coord_j + alpha_y[2]
        estimated_points = np.column_stack([x_estimated, y_estimated])
        
        # errors
        errors = np.abs(estimated_points - real_points)
        errors_x = errors[:, 0]
        errors_y = errors[:, 1]
        errors_magnitude = np.sqrt(errors_x**2 + errors_y**2)
        
        # Statistics
        num_total = len(real_points)
        num_below_50um = np.sum(errors_magnitude < 0.050)
        percentage_below_50um = (num_below_50um / num_total) * 100
        
        calibration_data = {
            "coefficients": {
                "alpha_x": alpha_x.tolist(),
                "alpha_y": alpha_y.tolist(),
                "resi_x": float(np.sum(resid_x)),
                "resi_y": float(np.sum(resid_y)),
                "model": "linear",
            },
            # "calibration_points": {
                # "pixel_points": pixel_points.tolist(),
                # "estimated_coords": estimated_points.tolist(),
                # "real_coords": real_points.tolist(),
                # "num_points": int(num_total)
            # },
            "validation": {
                # "num_samples": int(num_total),
                # "num_below_50um": int(num_below_50um),
                "accuracy_percentage": float(f"{percentage_below_50um:.2f}"),
                "mean_error_x_mm": float(f"{np.mean(errors_x):.3f}"),
                "mean_error_y_mm": float(f"{np.mean(errors_y):.3f}"),
                # "max_error_x_mm": float(f"{np.max(errors_x):.6f}"),
                # "max_error_y_mm": float(f"{np.max(errors_y):.6f}"),
                # "rms_error_mm": float(f"{np.sqrt(np.mean(errors_magnitude**2)):.6f}")
            },
            "folder_name": folder_name
        }
    
    
    else:
        raise ValueError("Unsupported input format for linear calibration.")

    # Save results
    json_file = os.path.join(session_dir, "calibration_coeffs.json")
    with open(json_file, 'w') as f:
        json.dump(calibration_data, f, indent=4)

    return calibration_data, estimated_points, folder_name


def pixel_to_real(coord_i, coord_j, json_folder=None, json_file=None):
    """
    Convert pixel coordinates (i, j) to real-world coordinates (x, y) in millimeters using calibration coefficients.
        x = α_x[0]*i + α_x[1]*j + α_x[2]
        y = α_y[0]*i + α_y[1]*j + α_y[2]
    """

    
    # If json_folder is provided, build the path
    if json_folder is not None:
        json_path = os.path.join(json_dir, json_folder, "calibration_coeffs.json")
        # Check whether folder and file exist
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"Calibration file not found: {json_path}")
        
    # If json_file is provided, use it directly
    elif json_file is not None:
        if isinstance(json_file, str):
            json_path = json_file  # already a complete path
        else:
            raise TypeError("json_file must be a path string to the JSON file")
    
    else:
        raise ValueError("You must provide json_folder or json_file to locate the calibration JSON file.")
    
    # Load JSON file
    try:
        with open(json_path, 'r') as f:
            calib = json.load(f)
    except Exception as e:
        raise ValueError(f"Error reading JSON file: {e}")
    
    model = calib["coefficients"]["model"]
    
    # Convert inputs to numpy arrays
    i = np.asarray(coord_i)
    j = np.asarray(coord_j)    

    # Linear calibration
    a_x = np.array(calib["coefficients"]["alpha_x"])
    a_y = np.array(calib["coefficients"]["alpha_y"])
    x = a_x[0]*i + a_x[1]*j + a_x[2]
    y = a_y[0]*i + a_y[1]*j + a_y[2]
    return x, y


def real_to_pixel(coord_x, coord_y):
    """
    Convert real-world coordinates (x, y) in millimeters to pixel coordinates (i, j) using calibration coefficients.
    """

    with open(os.path.join(json_dir, "calibration_coeffs.json"), 'r') as f: 
        calib = json.load(f)
    
    # Convert inputs to numpy arrays
    x = np.asarray(coord_x)
    y = np.asarray(coord_y)    

    # Direct transform coefficients:
    # x = α_x[0]*i + α_x[1]*j + α_x[2]
    # y = α_y[0]*i + α_y[1]*j + α_y[2]
    
    # Inverse of affine transform matrix
    # [i]   [α_x[0]  α_x[1]]^-1  [x - α_x[2]]
    # [j] = [α_y[0]  α_y[1]]     [y - α_y[2]]

    a00 = calib["coefficients"]["alpha_x"][0]
    a01 = calib["coefficients"]["alpha_x"][1]
    a02 = calib["coefficients"]["alpha_x"][2]
    a10 = calib["coefficients"]["alpha_y"][0]
    a11 = calib["coefficients"]["alpha_y"][1]
    a12 = calib["coefficients"]["alpha_y"][2]
    
    # Determinant of 2x2 matrix
    det = a00 * a11 - a01 * a10
    
    if abs(det) < 1e-10:
        raise ValueError("Calibration matrix is singular (determinant ≈ 0). Cannot invert.")
    
    # Apply inverse transformation
    i = (a11 * (x - a02) - a01 * (y - a12)) / det
    j = (-a10 * (x - a02) + a00 * (y - a12)) / det
    
    # For a single point, return scalars instead of arrays
    if len(np.atleast_1d(i)) == 1:
        return float(i), float(j)
    
    return i, j


def extract_xy_filename(filename):
    """
    Extract X and Y coordinates from a filename.
    """
    # Try newer format first: X<num>_Y<num>_<timestamp>.fits
    match = re.search(r'X(-?\d+(?:\.\d+)?)_Y(-?\d+(?:\.\d+)?)_', filename)
    
    # If not found, try older format: X<num>_Y<num>
    if not match:
        match = re.search(r'X(-?\d+(?:\.\d+)?)_Y(-?\d+(?:\.\d+)?)', filename)
    
    if match:
        x = float(match.group(1))
        y = float(match.group(2))
        return x, y
    else:
        raise ValueError(f"Filename does not contain valid coordinates: {filename}")

    
# --- Image Processing Auxiliary Functions (compute_calibration.py) ---


def getcross(x, y):
    """
    Compute cross center and tilt from the 4 ends of its arms.

    Functionality:
    1. Computes horizontal arm slope: m1 = (y[3] - y[1]) / (x[3] - x[1])
    2. Computes vertical arm slope: m2 = -(x[2] - x[0]) / (y[2] - y[0])
    4. Average slope: m = (m1 + m2) / 2
    5. Solve the equation system to find center (x0, y0)       
        
    """
    # Horizontal arm slope (between left and right end)
    m1 = (y[3] - y[1]) / (x[3] - x[1])
    # Vertical arm slope (between bottom and top end)
    m2 = -(x[2] - x[0]) / (y[2] - y[0])
    
    
    # Average slope (cross orientation)
    m = (m1 + m2) / 2
    # Compute cross center (x0, y0) from fitted line equations
    x0 = (m * (y[0] - y[3]) + m * m * x[3] + x[0]) / (m * m + 1)
    y0 = (m * (x[0] - x[3]) + m * m * y[0] + y[3]) / (m * m + 1)
            
    return m, x0, y0

  
def yhor(xx, x, y):
    """
    Compute y-coordinate on the horizontal arm line of the cross.

    Functionality:
    - Uses linear interpolation between left and right end of the horizontal arm.
    - Computes y for any x value along the arm line.
    - Based on line equation: y = y0 + m*(x - x0)
    """
    return y[3] + (y[1] - y[3]) / (x[1] - x[3]) * (xx - x[3]) 


def xver(yy, x, y):
    """
    Compute x-coordinate on the vertical arm line of the cross.

    Functionality:
    - Uses linear interpolation between top and bottom end of the vertical arm.
    - Computes x for any y value along the arm line.
    - Based on line equation: x = x0 + m*(y - y0)
    """
    
    return x[0] + (x[2] - x[0]) / (y[2] - y[0]) * (yy - y[0])


def xcen(LINE):
    """
    Compute the centroid of a 1D intensity vector.

    Functionality:
    - Returns centroid position (index weighted by intensity values).
    - Used to find cross-arm position in each image row/column.
    - If all values are zero (empty row/column), returns None.
    """
    a = np.asarray(LINE)                  # Convert to NumPy array
    sum_values = np.sum(LINE)             # Sum of array values
    
    # To ignore divergences when the line is partially clipped
    # threshold = len(LINE) * 40
       
    # if sum_values == 0 or sum_values < threshold:
    if sum_values == 0:
        return None 

    indices = np.arange(len(LINE))       
    return np.sum(indices * LINE) / sum_values


def twodcut(image, xcenter, ycenter, angle, width):
    """
    Extract a 1D intensity profile from a 2D image along a strip with chosen orientation and width.

    Functionality:
    - Extracts a 1D slice centered at a specific image position.
    - Supports horizontal cuts (0°/180°) and vertical cuts (90°/270°).
    - Sums intensity over the strip thickness (width).
    """
    
    # Get image dimensions (height and width)
    height, length = image.shape

    # --- Horizontal or vertical cut ---

    # angle equal to 0 or 180: horizontal cut (vertical profile)
    if angle in [0, 180]:                             
        xmin = max(0, xcenter - width // 2)           # left cut boundary
        xmax = min(length, xcenter + width // 2 + 1)  # right cut boundary
        line = image[:, xmin:xmax]                    # extract vertical strip from image
        profile = np.sum(line, axis=1)                # sum columns to build vertical profile

        # If width is even, correct edge over-counting
        if width % 2 == 0:
            profile -= 0.5 * (line[:, 0] + line[:, -1])

        # If angle is 180, reverse profile
        if angle == 180:
            profile = profile[::-1]

        return profile

    # angle equal to 90 or 270: vertical cut (horizontal profile)
    elif angle in [90, 270]:                          
        ymin = max(0, ycenter - width // 2)           # upper cut boundary
        ymax = min(height, ycenter + width // 2 + 1)  # lower cut boundary
        line = image[ymin:ymax, :]                    # extract horizontal strip from image
        profile = np.sum(line, axis=0)                # sum rows to build horizontal profile

        # Correct edge over-counting when width is even
        if width % 2 == 0:
            profile -= 0.5 * (line[0, :] + line[-1, :])

        # If angle is 270, reverse profile
        if angle == 270:
            profile = profile[::-1]

        return profile


def straightlinefit(xv, yv, xerr, yerr):
    """
    Fit a line to data considering errors on both axes using orthogonal regression (ODR).

    Functionality:
    - Fits linear model y = m*x + b to experimental data (xv, yv).
    - Considers uncertainties in both axes (xerr, yerr) simultaneously.
    - Uses ODR to minimize each point's perpendicular distance to the line.
    - More accurate than simple linear regression when both x and y have significant errors.
    - Returns fitted parameters, errors, fit-quality statistics, and diagnostics.

    Algorithm:
    1. Initial estimate with np.polyfit (considers only y errors)
    2. Define linear model for ODR: y = B[0]*x + B[1]
    3. Create RealData object with data and uncertainties
    4. Run ODR with initial estimate (beta0) for faster convergence
    5. Extract output parameters including coefficients, errors, and diagnostics
    """

    # Initial line estimate using weighted polyfit (ignores x errors)
    estimate = np.polyfit(xv, yv, 1, w=1/yerr)

    # Define the linear model to fit the data
    def linear_model(B, x):
        return B[0] * x + B[1]   # Line slope (B[0]) and intercept (B[1])
    model = Model(linear_model)  # Tell ODR which function to fit (here, y = m*x + b).
    
    # Create object holding experimental data (x, y) and uncertainties in x and y.
    data = RealData(xv, yv, sx=xerr, sy=yerr) 
    
    # Run orthogonal fit using data (RealData) and model (Model).
    odr = ODR(data, model, beta0=[estimate[0], estimate[1]]) # beta0 is the initial line estimate (m, b)
    output = odr.run()
   
    return [
        output.beta[0],              # [0] slope
        output.beta[1],              # [1] intercept
        output.sd_beta[0],           # [2] slope error
        output.sd_beta[1],           # [3] intercept error
        output.sum_square,           # [4] chi_square / sum of squared residuals
        # output.res_var,            # [5] residual variance
        # output.cov_beta,           # [6] covariance matrix
        # output.cov_beta[0,1] / (output.sd_beta[0]*output.sd_beta[1]),  # [7] m-b correlation
        # output.eps,                # [8] residual_standard_deviation
        # output.delta,              # [9] parameter_standard_deviation
        # output.stopreason,         # [10] stop_reason
        # output.info,               # [11] fit_success_code
        # output.inv_condnum,        # [12] inv_condition_number
    ]
