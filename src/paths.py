"""
paths.py

Define project output directories and timestamp helpers.
"""

from datetime import datetime
import os


# --- 1. Directory definitions ---

# Base directory (project root)
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Main output directory
files_dir = os.path.join(base_dir, 'files')

# Main subdirectories: Main Files, Calibration Files, and Test
main_dir = os.path.join(files_dir, 'Main_Files')
calib_dir = os.path.join(files_dir, 'Calibration_Files')
test_dir = os.path.join(files_dir, 'Teste')

# Subdirectories for Main Files
fits_dir = os.path.join(main_dir, 'Fits')                   # Cross FITS files
# line_fits_dir = os.path.join(main_dir, 'Lines_Fits')      # FITS files for image-edge cuts
img_dir = os.path.join(main_dir, 'Images')                  # PNG images/plots
data_dir = os.path.join(main_dir, 'Data')                   # Computed cross data

# Subdirectories for Calibration Files
json_dir = os.path.join(calib_dir, 'coefficients')          # JSON files with calibration coefficients
data_calib_dir = os.path.join(calib_dir, 'Data')            # Calibration data
fits_calib_dir = os.path.join(calib_dir, 'Fits')            # FITS files from captured frames
img_calib_dir = os.path.join(calib_dir, 'Images')           # Captured images for calibration
synt_dir = os.path.join(calib_dir, 'Synthetic_Fits')        # FITS files for synthetic crosses
img_synt_dir = os.path.join(calib_dir, 'Synthetic_Images')  # PNG files for synthetic crosses

    

# --- 2. Create directories if they do not exist ---

os.makedirs(fits_dir, exist_ok=True)
# os.makedirs(line_fits_dir, exist_ok=True)
os.makedirs(img_dir, exist_ok=True)
os.makedirs(data_dir, exist_ok=True)
os.makedirs(calib_dir, exist_ok=True)
os.makedirs(json_dir, exist_ok=True)
os.makedirs(synt_dir, exist_ok=True)
os.makedirs(img_synt_dir, exist_ok=True)
os.makedirs(fits_calib_dir, exist_ok=True)
os.makedirs(test_dir, exist_ok=True)
os.makedirs(img_calib_dir, exist_ok=True)
os.makedirs(data_calib_dir, exist_ok=True)
os.makedirs(main_dir, exist_ok=True)
os.makedirs(files_dir, exist_ok=True)

# --- 3. Timestamp helpers for file naming ---

def get_timestamp():
    return datetime.now().strftime('%Y-%m-%d_%H-%M')  # Format: YYYY-MM-DD_HH-MM

def get_timestamp_sec():
    return datetime.now().strftime('%Y-%m-%d_%H-%M-%S')  # Format: YYYY-MM-DD_HH-MM-SS
