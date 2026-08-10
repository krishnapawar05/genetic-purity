import os
import sys
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables from .env file before reading
load_dotenv(override=True)

# Read MongoDB configuration strictly from environment variables
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")

# Startup Validation: Ensure MONGO_URI and DB_NAME are present
if not MONGO_URI or not MONGO_URI.strip():
    raise RuntimeError("MONGO_URI is not configured. Please check your .env file and set your MongoDB Atlas connection string.")

if not DB_NAME or not DB_NAME.strip():
    raise RuntimeError("DB_NAME is not configured. Please check your .env file and set your target database name.")

class Config:
    """
    Application Configuration loaded strictly from environment variables.
    """
    SECRET_KEY = os.getenv('SECRET_KEY', 'default-genetic-purity-secret-key-change-in-production')
    
    # MongoDB Atlas Connection Parameters
    MONGO_URI = MONGO_URI.strip()
    DB_NAME = DB_NAME.strip()
    
    # Twilio SMS Configuration
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID', '')
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN', '')
    TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER', '')
    TWILIO_VERIFY_SERVICE_SID = os.getenv('TWILIO_VERIFY_SERVICE_SID', '')
    
    # Razorpay Payment Gateway Configuration
    RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID', 'rzp_test_sampleKeyId')
    RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET', 'sampleKeySecret')
    ANALYSIS_PRICE_INR = int(os.getenv('ANALYSIS_PRICE_INR', '99'))
    
    # Session & Cookie Security (Requirement 26)
    SESSION_TIMEOUT_MINUTES = int(os.getenv('SESSION_TIMEOUT_MINUTES', '30'))
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=SESSION_TIMEOUT_MINUTES)
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.getenv('FLASK_ENV', 'development') == 'production'
    
    # CSRF Protection
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600
    
    # Upload settings
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB max limit
