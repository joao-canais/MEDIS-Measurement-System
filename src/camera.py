"""
camera.py

Capture a camera frame, preprocess it for cross detection, and return FITS header metadata.
"""

# --- Imports ---
import platform
import cv2

def capture_image(camera_i):
    """
    Capture one frame, convert to grayscale, apply threshold, and return metadata.

    Args:
        camera_i (int | str): Camera index (e.g., 0, 1) or device path (e.g., '/dev/video0').

    Returns:
        tuple[np.ndarray, np.ndarray, dict]: Processed image, original image, and FITS header parameters.
    """
    
    
 
    # --- 1. Camera initialization (OS detection) ---
    
    if platform.system() == "Linux":

        if isinstance(camera_i, int):
            dev_path = f"/dev/video{camera_i}"
            cap = cv2.VideoCapture(dev_path)
            print(f"Using camera: {dev_path} (first attempt)")
            if not cap.isOpened():
                # Fallback to integer index
                cap = cv2.VideoCapture(camera_i)
                print(f"Using camera: {camera_i} (fallback)")
        else:
            camera_i = "/dev/video0"
            print(f"Using camera: {camera_i} (default)")
            cap = cv2.VideoCapture(camera_i)
    else:
        # Windows/macOS: use integer index or provided string
        cap = cv2.VideoCapture(camera_i)
        print(f"Using camera: {camera_i} (Windows default)")
    
    if not cap.isOpened():
        print("Error: Unable to open camera.")
        raise RuntimeError("Unable to open camera.")
    

    # --- 2. Camera parameter setup ---

    # Resolution setup
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 4656)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 3496)
    
    
    # --- 3. Frame capture ---

    ret, image = cap.read()
    if not ret:
        print("Error: Unable to capture frame.")
        cap.release()
        raise RuntimeError("Unable to capture frame.")
    
    cap.release()
    

    # --- 4. Convert to grayscale ---

    # image = cv2.flip(image, -1)
    
    adapted_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    grayscale_applied = True if adapted_image is not None else False
    
    original_image = image.copy()
    
    
    # --- 5. Apply threshold ---
    
    threshold_value = 30
    threshold_value, adapted_image = cv2.threshold(adapted_image, threshold_value, 255, cv2.THRESH_TOZERO)

    
    # --- 6. FITS header parameters ---
    
    fits_header_parameters = {
        
        # Camera information
        'CAMERA': (str(camera_i), 'Camera index or device path'),
        'CAMSYS': (platform.system(), 'Operating system'),
        
        # Capture settings
        'WIDTH': (int(adapted_image.shape[1]), 'Frame width in pixels'),
        'HEIGHT': (int(adapted_image.shape[0]), 'Frame height in pixels'),
        'EXPOSURE': (float(50), 'Exposure_time_absolute in ms (set via v4l2-ctl)'),
        'DTYPE': (str(adapted_image.dtype), 'Image data type (e.g., uint8)'),

        # Applied processing
        'GRAY': (str(grayscale_applied), 'Image converted to grayscale'),
        'THRESH': (threshold_value, 'Threshold value for binary conversion'),
    }
        

    return adapted_image, original_image, fits_header_parameters



# --- DEBUG ---
if __name__ == "__main__":
    
    adapted_image, original_image, fits_header_parameters = capture_image(0)
    
    # Print captured parameters
    print("\n=== FITS header parameters ===\n")
    for key, (value, comment) in fits_header_parameters.items():
        print(f"{key:10s} = {str(value):20s} / {comment}")