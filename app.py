"""
Flask Web Application Server for Genetic Purity Prediction Testing UI.
Acts as a bridge to run detect.py on uploaded images and returns structured JSON results.
"""

import os
import sys

# Configure environment variables before importing TensorFlow/Matplotlib
os.environ["MPLBACKEND"] = "Agg"
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

# Add current directory to sys.path so we can import detect
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

import detect
from tensorflow.keras.models import load_model
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.debug = True


# Configure upload directory
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Limit file size to 16MB
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'webp'}

# Pre-load the model when starting up
# In Flask's debug mode, to prevent loading twice, check WERKZEUG_RUN_MAIN
model = None
model_path = os.path.join(app.config['UPLOAD_FOLDER'], "model.keras")

if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    try:
        print("Loading TensorFlow and AI model into memory. Please wait...", flush=True)
        model = load_model(model_path, compile=False)
        
        # Warmup the model with a dummy prediction to compile TensorFlow execution paths
        import numpy as np
        dummy_input = np.zeros((1, 224, 224, 3), dtype=np.float32)
        model.predict(dummy_input, verbose=0)
        
        print("Model loaded and warmed up successfully.", flush=True)
    except Exception as e:
        print(f"Error loading model at startup: {e}", file=sys.stderr, flush=True)



def allowed_file(filename):
    """
    Checks if the uploaded file has a supported image extension.
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def parse_prediction_output(output_text):
    """
    Parses the CLI output text of detect.py and converts it to a structured dictionary.
    """
    probabilities = {}
    predicted_class = "UNKNOWN"
    genetic_purity = "UNKNOWN / IMPURE"
    reason = ""
    confidence_score = "0.00%"
    prediction_time = "0.00s"
    
    lines = output_text.split('\n')
    
    parsing_probs = False
    parsing_report = False
    reason_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Parse Class Probabilities section
        if "AI-Assisted Genetic Purity Prediction - Class Probabilities" in line:
            parsing_probs = True
            continue
        elif parsing_probs and line.startswith("==="):
            if len(probabilities) > 0:
                parsing_probs = False
            continue
        elif parsing_probs:
            if ":" in line:
                parts = line.split(":", 1)
                class_name = parts[0].strip().lower()
                prob_str = parts[1].replace("%", "").strip()
                try:
                    probabilities[class_name] = float(prob_str)
                except ValueError:
                    pass
            continue
            
        # Parse Prediction Decision Report section
        if "PREDICTION DECISION REPORT" in line:
            parsing_report = True
            continue
        elif parsing_report and line.startswith("==="):
            parsing_report = False
            continue
        elif parsing_report:
            if line.startswith("Predicted Class"):
                predicted_class = line.split(":", 1)[1].strip()
            elif line.startswith("Genetic Purity"):
                genetic_purity = line.split(":", 1)[1].strip()
            elif line.startswith("Reason"):
                continue
            elif line.startswith("----------------------------------------------------------------------"):
                continue
            else:
                reason_lines.append(line)
                continue
                
        # Parse confidence score and prediction time printed after report
        if line.startswith("Confidence Score"):
            confidence_score = line.split(":", 1)[1].strip()
        elif line.startswith("Prediction Time"):
            prediction_time = line.split(":", 1)[1].strip()
            
    reason = "\n".join(reason_lines).strip()
    
    return {
        "class": predicted_class,
        "purity": genetic_purity,
        "confidence": confidence_score,
        "probabilities": probabilities,
        "reason": reason,
        "prediction_time": prediction_time
    }


@app.route('/')
def index():
    """
    Serves the landing testing dashboard page.
    """
    return render_template('index.html')


@app.route('/predict', methods=['POST'])
def predict():
    """
    Endpoint that handles image upload, runs inference via detect.py in-memory, and returns JSON.
    """
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
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Access pre-loaded global model
        global model
        if model is None:
            # Lazy load model if it was not loaded on startup
            model_path = os.path.join(app.config['UPLOAD_FOLDER'], "model.keras")
            model = load_model(model_path, compile=False)
            
        # Run inference in-memory
        result = detect.predict_image(filepath, model)
        
        # Format probabilities as percentages (0-100 scale) to keep UI compatibility
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
        # Guarantee cleanup of uploaded file
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass


if __name__ == "__main__":
    app.run(host='127.0.0.1', port=5000, debug=True)
