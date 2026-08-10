"""
Flask Production Application Architecture for Genetic Purity AI.
Integrates MongoDB Atlas User Store, Flask-Login Authentication, SMS OTP Reset,
Razorpay Payment Gateway with HMAC Signature Verification, CSRF Protection,
Rate Limiting, Production Logging, and encapsulates detect.py prediction middleware.
"""

import os
import sys
import tempfile
import uuid
import gc
import logging
import threading

# Configure environment variables before importing TensorFlow/Matplotlib
os.environ["MPLBACKEND"] = "Agg"
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

# Configure Production Logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("GeneticPurityAI")

# Add current directory to sys.path so we can import detect
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

import detect
import numpy as np
from tensorflow.keras.models import load_model
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_login import LoginManager, login_required, current_user
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename
from PIL import Image
import rawpy
from pillow_heif import register_heif_opener

from config import Config
from models.user import User
from models.prediction import PredictionRecord
from models.payment import PaymentRecord
from services.payment_service import PaymentService
from utils.date_utils import format_datetime
from auth import auth_bp
from routes import main_bp

# Register HEIC opener with Pillow to support HEIC files transparently
register_heif_opener()

app = Flask(__name__)
app.config.from_object(Config)

# Register central Date & Time formatting filter
app.jinja_env.filters['format_datetime'] = format_datetime

@app.context_processor
def inject_format_datetime():
    return dict(format_datetime=format_datetime)


# Security Extensions
csrf = CSRFProtect(app)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["300 per day", "60 per hour"],
    storage_uri="memory://"
)

# Initialize Flask-Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = "Please log in to access your testing workspace."
login_manager.login_message_category = "warning"

@login_manager.user_loader
def load_user(user_id):
    return User.get_by_id(user_id)

@login_manager.unauthorized_handler
def unauthorized_callback():
    if request.is_json or request.path in ['/predict', '/create-order', '/verify-payment']:
        return jsonify({
            "success": False,
            "error": "Authentication required. Please log in first."
        }), 401
    return redirect(url_for('auth.login', next=request.path))


# Requirement 26: Automatic Logout & Session Security Handler
from datetime import datetime, timezone
from flask import session

@app.before_request
def check_session_inactivity():
    """
    Requirement 26: Inactivity-Based Automatic Logout.
    Tracks user activity timestamps and automatically logs out sessions
    that have been inactive for SESSION_TIMEOUT_MINUTES.
    Active users making requests or interacting with the platform stay logged in.
    """
    if current_user.is_authenticated:
        now = datetime.now(timezone.utc)
        last_act_str = session.get('last_activity')
        timeout_seconds = Config.SESSION_TIMEOUT_MINUTES * 60
        
        if last_act_str:
            try:
                last_act = datetime.fromisoformat(last_act_str)
                if last_act.tzinfo is None:
                    last_act = last_act.replace(tzinfo=timezone.utc)
                
                elapsed = (now - last_act).total_seconds()
                if elapsed > timeout_seconds:
                    from flask_login import logout_user
                    logout_user()
                    session.clear()
                    flash("Your session has expired due to inactivity. Please sign in again.", "warning")
                    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.path in ['/predict', '/create-order', '/verify-payment', '/convert-preview']:
                        return jsonify({
                            "success": False,
                            "error": "Session expired due to inactivity.",
                            "redirect": url_for('auth.login')
                        }), 401
                    return redirect(url_for('auth.login'))
            except Exception as e:
                logger.warning(f"Error evaluating session inactivity: {e}")
                
        session['last_activity'] = now.isoformat()
        session.permanent = True

# Register Blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(main_bp)

# Demo Status Flag
SERVER_STATUS = "online"

# Configure upload directory
UPLOAD_FOLDER = os.path.join(current_dir, 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'webp', 'dng', 'heic', 'heif'}

# Global thread lock for TensorFlow model inference thread-safety
model_lock = threading.Lock()


def is_valid_image(filepath):
    """
    Server-side security verification ensuring uploaded file is a valid image.
    Does not rely only on filename extension or client Content-Type headers.
    """
    if not filepath or not os.path.exists(filepath):
        return False
    ext = os.path.splitext(filepath)[1].lower()
    if ext not in ['.png', '.jpg', '.jpeg', '.bmp', '.webp', '.dng', '.heic', '.heif']:
        return False
    if ext == '.dng':
        try:
            with rawpy.imread(filepath) as raw:
                return True
        except Exception:
            return False
    try:
        with Image.open(filepath) as img:
            img.verify()
        return True
    except Exception:
        return False


# Error Handlers
@app.errorhandler(404)
def not_found_error(error):
    if request.is_json:
        return jsonify({"success": False, "error": "Requested resource not found."}), 404
    return render_template('404.html'), 404

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({
        "success": False,
        "error": "Uploaded image is too large. Maximum allowed file size is 50 MB."
    }), 413

@app.errorhandler(429)
def ratelimit_handler(e):
    if request.is_json:
        return jsonify({"success": False, "error": "Rate limit exceeded. Please wait a moment."}), 429
    return render_template('429.html'), 429

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal Server Error: {error}")
    if request.is_json:
        return jsonify({"success": False, "error": "Internal server error."}), 500
    return render_template('500.html'), 500


def downscale_image_if_large(filepath, max_dim=1280):
    ext = os.path.splitext(filepath)[1].lower()
    if ext in ['.heic', '.heif', '.dng']:
        return
    try:
        with Image.open(filepath) as img:
            w, h = img.size
            if max(w, h) > max_dim:
                img.thumbnail((max_dim, max_dim), Image.Resampling.BILINEAR)
                fmt = img.format if img.format else 'JPEG'
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                img.save(filepath, fmt, quality=90)
    except Exception as e:
        logger.warning(f"Warning during downscaling {filepath}: {e}")


def convert_to_standard_format(filepath, max_dim=1280):
    ext = os.path.splitext(filepath)[1].lower()
    if ext not in ['.heic', '.heif', '.dng']:
        return filepath

    converted_path = os.path.splitext(filepath)[0] + "_converted.jpg"
    try:
        if ext in ['.heic', '.heif']:
            with Image.open(filepath) as img:
                rgb_img = img.convert('RGB')
                if max(rgb_img.width, rgb_img.height) > max_dim:
                    rgb_img.thumbnail((max_dim, max_dim), Image.Resampling.BILINEAR)
                rgb_img.save(converted_path, 'JPEG', quality=90)
        elif ext == '.dng':
            with rawpy.imread(filepath) as raw:
                rgb = raw.postprocess(use_camera_wb=True, half_size=True, bright=1.0)
                with Image.fromarray(rgb) as img:
                    if max(img.width, img.height) > max_dim:
                        img.thumbnail((max_dim, max_dim), Image.Resampling.BILINEAR)
                    img.save(converted_path, 'JPEG', quality=90)
                del rgb
        return converted_path
    except Exception as e:
        logger.error(f"Error converting {ext} file: {e}")
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
    logger.info("Loading TensorFlow and AI model into memory. Please wait...")
    model = load_model(model_path, compile=False)
    
    # Warmup the model with a dummy prediction to compile TensorFlow execution paths
    dummy_input = np.zeros((1, 224, 224, 3), dtype=np.float32)
    model.predict(dummy_input, verbose=0)
    del dummy_input
    gc.collect()
    
    logger.info("Model loaded and warmed up successfully.")
except Exception as e:
    logger.error(f"Error loading model at startup: {e}")


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/health')
@limiter.exempt
def health():
    if SERVER_STATUS == "online":
        return jsonify({"status": "online"}), 200
    else:
        return jsonify({"status": "offline"}), 503


@app.route('/convert-preview', methods=['POST'])
@login_required
@limiter.limit("20 per minute")
def convert_preview():
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
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext, dir=app.config['UPLOAD_FOLDER']) as tmp:
            temp_path = tmp.name
            file.save(temp_path)
            
        if not is_valid_image(temp_path):
            return jsonify({"success": False, "error": "Uploaded file is not a valid image format."}), 400

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
        for p in [temp_path, converted_path]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
        gc.collect()


@app.route('/create-order', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def create_order():
    """
    Step 1 of Payment Flow: Accepts specimen image, saves temp file, 
    creates Razorpay Order, and returns Order details to client.
    """
    if SERVER_STATUS == "offline":
        return jsonify({"success": False, "error": "Prediction service is offline."}), 503

    if 'image' not in request.files:
        return jsonify({"success": False, "error": "No image file provided."}), 400
        
    file = request.files['image']
    if file.filename == '':
        return jsonify({"success": False, "error": "No file selected."}), 400
        
    if not allowed_file(file.filename):
        return jsonify({
            "success": False,
            "error": f"Unsupported format. Allowed formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        }), 400

    filename = secure_filename(file.filename)
    ext = os.path.splitext(filename)[1].lower()
    if not ext:
        ext = '.tmp'

    temp_token = f"tok_{uuid.uuid4().hex}"
    temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{temp_token}{ext}")
    
    try:
        file.save(temp_path)
        
        # Server-Side Image Integrity Verification (Reject non-image payloads)
        if not is_valid_image(temp_path):
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return jsonify({"success": False, "error": "Uploaded file is invalid or not a supported image file."}), 400

        # Create Razorpay order
        price_inr = Config.ANALYSIS_PRICE_INR
        success, order = PaymentService.create_order(amount_inr=price_inr, receipt_id=temp_token)
        
        if not success or not order:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return jsonify({"success": False, "error": "Failed to create payment order. Please try again."}), 500

        # Save pending payment record in MongoDB
        PaymentRecord.create_pending_payment(
            user_id=current_user.id,
            order_id=order["id"],
            amount=price_inr,
            currency="INR",
            temp_path=temp_path,
            temp_token=temp_token
        )

        return jsonify({
            "success": True,
            "order_id": order["id"],
            "amount": order["amount"], # in paise
            "currency": "INR",
            "key_id": Config.RAZORPAY_KEY_ID,
            "temp_token": temp_token,
            "original_filename": file.filename
        })

    except Exception as e:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        return jsonify({"success": False, "error": f"Failed to initialize payment: {str(e)}"}), 500


@app.route('/verify-payment', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def verify_payment():
    """
    Step 2 of Payment Flow: Verifies Razorpay HMAC SHA256 signature.
    ONLY IF payment verification succeeds, calls detect.predict_image(),
    stores prediction history, updates payment record, and returns results.
    If signature fails or fake callback detected, BLOCKS prediction and returns 400 error.
    """
    data = request.get_json() or {}
    order_id = data.get('razorpay_order_id', '')
    payment_id = data.get('razorpay_payment_id', '')
    signature = data.get('razorpay_signature', '')
    temp_token = data.get('temp_token', '')

    if not order_id or not temp_token:
        return jsonify({"success": False, "error": "Missing payment verification parameters."}), 400

    # Retrieve payment record from MongoDB
    payment_rec = PaymentRecord.get_by_token(temp_token)
    if not payment_rec or payment_rec.userId != current_user.id:
        return jsonify({"success": False, "error": "Invalid payment transaction session."}), 400

    # 1. Verify Razorpay HMAC Signature
    is_valid, msg = PaymentService.verify_payment_signature(order_id, payment_id, signature)
    
    temp_path = payment_rec.tempSpecimenPath
    converted_filepath = None

    if not is_valid:
        # Payment verification failed - Mark payment failed & cleanup disk temp file
        PaymentRecord.mark_failed(order_id, reason=msg)
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        # CRITICAL: DO NOT RUN PREDICTION AND DO NOT REVEAL RESULT!
        return jsonify({
            "success": False,
            "error": f"Payment signature verification failed. {msg}"
        }), 400

    # 2. Signature Verified Successfully! Now and ONLY now execute prediction logic.
    try:
        if not temp_path or not os.path.exists(temp_path):
            return jsonify({"success": False, "error": "Specimen image file expired. Please re-upload image."}), 400

        downscale_image_if_large(temp_path, max_dim=1280)

        ext = os.path.splitext(temp_path)[1].lower()
        if ext in ['.heic', '.dng']:
            converted_filepath = convert_to_standard_format(temp_path, max_dim=1280)
            if not converted_filepath:
                return jsonify({
                    "success": False,
                    "error": "Unable to process DNG/HEIC image format."
                }), 400
            inference_path = converted_filepath
        else:
            inference_path = temp_path

        global model
        if model is None:
            with model_lock:
                if model is None:
                    logger.info("Lazy loading TensorFlow model into memory...")
                    model = load_model(model_path, compile=False)

        # Run unmodified inference engine under thread lock
        with model_lock:
            result = detect.predict_image(inference_path, model)

        probabilities_scaled = {
            class_name: prob * 100 
            for class_name, prob in result["probabilities"].items()
        }

        user_crop = getattr(current_user, 'customerUseCase', None) or 'Chilli / Plant Specimen'

        # Save prediction record in MongoDB
        pred_record = PredictionRecord.create_record(
            user_id=current_user.id,
            filename=data.get('original_filename', 'specimen_image'),
            result={
                'class': result["class"],
                'purity': result["purity"],
                'confidence': result["confidence"],
                'probabilities': probabilities_scaled,
                'reason': result["reason"],
                'prediction_time': result["prediction_time"]
            },
            status="completed",
            crop=user_crop
        )

        # Permanently store copy of analyzed specimen image for PDF report embedding
        try:
            specimens_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'specimens')
            os.makedirs(specimens_dir, exist_ok=True)
            saved_specimen_filename = f"specimen_{pred_record.id}.jpg"
            saved_specimen_full_path = os.path.join(specimens_dir, saved_specimen_filename)
            import shutil
            shutil.copy2(inference_path, saved_specimen_full_path)

            from bson import ObjectId
            from database.db import get_predictions_collection
            get_predictions_collection().update_one(
                {'_id': ObjectId(pred_record.id)},
                {'$set': {'specimenPath': saved_specimen_filename}}
            )
            pred_record.specimenPath = saved_specimen_filename
        except Exception as e:
            logger.warning(f"Warning saving permanent specimen image: {e}")

        # Mark Payment completed in MongoDB
        PaymentRecord.mark_completed(
            order_id=order_id,
            payment_id=payment_id,
            signature=signature,
            prediction_id=pred_record.id
        )

        download_url = url_for('main.download_report', prediction_id=pred_record.id)

        parsed_data = {
            "success": True,
            "record_id": pred_record.id,
            "download_url": download_url,
            "class": result["class"],
            "purity": result["purity"],
            "confidence": result["confidence"],
            "probabilities": probabilities_scaled,
            "reason": result["reason"],
            "prediction_time": result["prediction_time"]
        }

        return jsonify(parsed_data)

    except Exception as e:
        logger.error(f"[Payment Verification Error] Order {order_id} failed: {e}", exc_info=True)
        PaymentRecord.mark_failed(order_id, reason=str(e))
        return jsonify({"success": False, "error": f"Internal server error during report generation: {str(e)}"}), 500

    finally:
        for p in [temp_path, converted_filepath]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
        gc.collect()


@app.route('/cancel-payment', methods=['POST'])
@login_required
@limiter.limit("20 per minute")
def cancel_payment():
    """
    Step 3 of Payment Flow: Explicitly marks a payment order as failed/cancelled
    when cancelled on the client-side checkout.
    """
    data = request.get_json() or {}
    order_id = data.get('razorpay_order_id', '')
    temp_token = data.get('temp_token', '')

    if not order_id:
        return jsonify({"success": False, "error": "Missing order ID."}), 400

    payment_rec = PaymentRecord.get_by_order_id(order_id)
    if payment_rec and payment_rec.userId == current_user.id:
        if payment_rec.status in ['paid', 'completed']:
            return jsonify({"success": True, "message": "Payment already completed."}), 200
        PaymentRecord.mark_failed(order_id, reason="Cancelled by user checkout")
        temp_path = payment_rec.tempSpecimenPath
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        return jsonify({"success": True, "message": "Payment cancelled successfully."})
    
    return jsonify({"success": False, "error": "Payment session not found."}), 404



@app.route('/predict', methods=['POST'])
@login_required
def predict():
    return jsonify({
        "success": False,
        "error": "Direct un-paid predictions are disabled. Please use the paid analysis checkout."
    }), 402


if __name__ == "__main__":
    app.run(host='127.0.0.1', port=5000, debug=True)
