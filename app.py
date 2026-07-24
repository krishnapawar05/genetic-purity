"""
Flask Web Application Server for Genetic Purity Prediction Testing UI.
Acts as a bridge to run detect.py on uploaded images and returns structured JSON results.
"""

import os
import sys
import tempfile
import uuid
import gc
import threading

# Configure environment variables before importing TensorFlow/Matplotlib
os.environ["MPLBACKEND"] = "Agg"
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

# Add current directory to sys.path so we can import detect
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

import detect
import numpy as np
from tensorflow.keras.models import load_model
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
from PIL import Image
import rawpy
from pillow_heif import register_heif_opener

# Register HEIC opener with Pillow to support HEIC files transparently
register_heif_opener()

app = Flask(__name__)
app.debug = False  # Set to False for production deployment

# Demo Mode Configuration
# "online" : Server functions normally.
# "offline": Simulates server outage (returns 503 Service Unavailable).
SERVER_STATUS = "online"

# Configure upload directory
UPLOAD_FOLDER = os.path.join(current_dir, 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Set MAX_CONTENT_LENGTH to 50 MB for Railway large uploads
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'webp', 'dng', 'heic'}

# Global thread lock for TensorFlow model inference thread-safety
model_lock = threading.Lock()


@app.errorhandler(413)
def request_entity_too_large(error):
    """
    Catches 413 Payload Too Large errors gracefully and returns structured JSON.
    """
    return jsonify({
        "success": False,
        "error": "Uploaded image is too large. Maximum allowed file size is 50 MB."
    }), 413


def downscale_image_if_large(filepath, max_dim=1280):
    """
    Downscales large images in-place to max_dim pixels while preserving aspect ratio.
    Reduces RAM usage by over 90% during subsequent Pillow/OpenCV processing.
    """
    ext = os.path.splitext(filepath)[1].lower()
    if ext in ['.heic', '.dng']:
        return
    try:
        with Image.open(filepath) as img:
            w, h = img.size
            if max(w, h) > max_dim:
                img.thumbnail((max_dim, max_dim), Image.Resampling.BILINEAR)
                fmt = img.format if img.format else 'JPEG'
                # Convert RGBA/Palette to RGB for JPEG compatibility
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                img.save(filepath, fmt, quality=90)
    except Exception as e:
        print(f"Warning during downscaling {filepath}: {e}", file=sys.stderr, flush=True)


def convert_to_standard_format(filepath, max_dim=1280):
    """
    Converts .heic or .dng files to RGB JPEG format, downscaling if larger than max_dim.
    Returns the path to the converted image file, or None if conversion fails.
    """
    ext = os.path.splitext(filepath)[1].lower()
    if ext not in ['.heic', '.dng']:
        return filepath

    converted_path = os.path.splitext(filepath)[0] + "_converted.jpg"
    try:
        if ext == '.heic':
            with Image.open(filepath) as img:
                rgb_img = img.convert('RGB')
                if max(rgb_img.width, rgb_img.height) > max_dim:
                    rgb_img.thumbnail((max_dim, max_dim), Image.Resampling.BILINEAR)
                rgb_img.save(converted_path, 'JPEG', quality=90)
        elif ext == '.dng':
            with rawpy.imread(filepath) as raw:
                # Use half_size=True to decode at 1/4 resolution from Bayer matrix, saving massive RAM and CPU time
                rgb = raw.postprocess(use_camera_wb=True, half_size=True, bright=1.0)
                with Image.fromarray(rgb) as img:
                    if max(img.width, img.height) > max_dim:
                        img.thumbnail((max_dim, max_dim), Image.Resampling.BILINEAR)
                    img.save(converted_path, 'JPEG', quality=90)
                del rgb
        return converted_path
    except Exception as e:
        print(f"Error converting {ext} file: {e}", file=sys.stderr, flush=True)
        if os.path.exists(converted_path):
            try:
                os.remove(converted_path)
            except Exception:
                pass
        return None


# Pre-load the model when starting up application
model = None
model_path = os.path.join(current_dir, "model.keras")

try:
    print("Loading TensorFlow and AI model into memory. Please wait...", flush=True)
    model = load_model(model_path, compile=False)
    
    # Warmup the model with a dummy prediction to compile TensorFlow execution paths
    dummy_input = np.zeros((1, 224, 224, 3), dtype=np.float32)
    model.predict(dummy_input, verbose=0)
    del dummy_input
    gc.collect()
    
    print("Model loaded and warmed up successfully.", flush=True)
except Exception as e:
    print(f"Error loading model at startup: {e}", file=sys.stderr, flush=True)


def allowed_file(filename):
    """
    Checks if the uploaded file has a supported image extension.
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    """
    Serves the landing testing dashboard page.
    """
    return render_template('index.html')


@app.route('/health')
def health():
    """
    Status endpoint indicating if the server is healthy.
    """
    if SERVER_STATUS == "online":
        return jsonify({"status": "online"}), 200
    else:
        return jsonify({"status": "offline"}), 503


@app.route('/convert-preview', methods=['POST'])
def convert_preview():
    """
    Temporary endpoint to convert uploaded HEIC/DNG file to a base64 JPEG for browser preview.
    """
    if SERVER_STATUS == "offline":
        return jsonify({"success": False, "error": "Preview service is offline."}), 503

    if 'image' not in request.files:
        return jsonify({"success": False, "error": "No image file provided."}), 400
        
    file = request.files['image']
    if file.filename == '':
        return jsonify({"success": False, "error": "No file was selected."}), 400
        
    import base64
    
    filename = secure_filename(file.filename)
    ext = os.path.splitext(filename)[1].lower()
    if not ext:
        ext = '.tmp'
        
    temp_path = None
    converted_path = None
    try:
        # Stream file upload directly to a temporary disk location
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext, dir=app.config['UPLOAD_FOLDER']) as tmp:
            temp_path = tmp.name
            file.save(temp_path)
            
        downscale_image_if_large(temp_path, max_dim=1280)
        converted_path = convert_to_standard_format(temp_path, max_dim=1280)
        
        if not converted_path or not os.path.exists(converted_path):
            return jsonify({"success": False, "error": "Failed to generate preview image."}), 400
            
        with open(converted_path, "rb") as img_file:
            encoded_string = base64.b64encode(img_file.read()).decode('utf-8')
            
        return jsonify({
            "success": True,
            "preview": f"data:image/jpeg;base64,{encoded_string}"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        # Guarantee cleanup of temporary disk files
        for p in [temp_path, converted_path]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
        gc.collect()


@app.route('/predict', methods=['POST'])
def predict():
    """
    Endpoint that handles image upload, runs inference via detect.py in-memory, and returns JSON.
    """
    if SERVER_STATUS == "offline":
        return jsonify({"success": False, "error": "Prediction service is currently unavailable. Please try again later."}), 503

    if 'image' not in request.files:
        return jsonify({"success": False, "error": "No image file provided in upload request."}), 400
        
    file = request.files['image']
    if file.filename == '':
        return jsonify({"success": False, "error": "No file was selected."}), 400
        
    if not allowed_file(file.filename):
        return jsonify({
            "success": False, 
            "error": f"Unsupported format. Allowed formats are: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        }), 400
        
    filepath = None
    converted_filepath = None
    try:
        filename = secure_filename(file.filename)
        ext = os.path.splitext(filename)[1].lower()
        if not ext:
            ext = '.tmp'

        # Stream upload directly to tempfile on disk to avoid keeping multiple copies in RAM
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext, dir=app.config['UPLOAD_FOLDER']) as tmp:
            filepath = tmp.name
            file.save(filepath)

        # Downscale large images immediately to max 1280px dimension to prevent RAM spikes
        downscale_image_if_large(filepath, max_dim=1280)

        # Convert HEIC/DNG to standard JPEG
        if ext in ['.heic', '.dng']:
            converted_filepath = convert_to_standard_format(filepath, max_dim=1280)
            if not converted_filepath:
                return jsonify({
                    "success": False,
                    "error": "Unable to process this DNG/HEIC image. Please try another image or convert it to PNG or JPEG."
                }), 400
            inference_path = converted_filepath
        else:
            inference_path = filepath

        # Access pre-loaded global model thread-safely
        global model
        if model is None:
            with model_lock:
                if model is None:
                    print("Lazy loading TensorFlow model into memory...", flush=True)
                    model = load_model(model_path, compile=False)

        # Run inference under thread lock for safety
        with model_lock:
            result = detect.predict_image(inference_path, model)

        # Format probabilities as percentages (0-100 scale) for UI compatibility
        probabilities_scaled = {
            class_name: prob * 100 
            for class_name, prob in result["probabilities"].items()
        }

        parsed_data = {
            "success": True,
            "class": result["class"],
            "purity": result["purity"],
            "confidence": result["confidence"],
            "probabilities": probabilities_scaled,
            "reason": result["reason"],
            "prediction_time": result["prediction_time"]
        }

        return jsonify(parsed_data)

    except Exception as e:
        return jsonify({"success": False, "error": f"Internal server error: {str(e)}"}), 500

    finally:
        # Guarantee cleanup of uploaded and converted disk files
        for p in [filepath, converted_filepath]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
        gc.collect()


if __name__ == "__main__":
    app.run(host='127.0.0.1', port=5000, debug=True)
