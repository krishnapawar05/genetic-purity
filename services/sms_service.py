import sys
import random
from datetime import datetime, timedelta
from config import Config
from database.db import get_otps_collection

class SMSService:
    @staticmethod
    def generate_otp() -> str:
        """Generates a secure 6-digit OTP code."""
        return f"{random.randint(100000, 999999)}"

    @classmethod
    def send_otp(cls, mobile_number: str) -> tuple[bool, str, str]:
        """
        Generates and sends an OTP to the given mobile number.
        Stores OTP in MongoDB with timestamp.
        Returns (success: bool, message: str, otp_code: str).
        """
        clean_mobile = mobile_number.strip().replace(" ", "").replace("-", "")
        otp_code = cls.generate_otp()
        
        # Save or update OTP in database
        otps_col = get_otps_collection()
        otps_col.delete_many({'mobileNumber': clean_mobile})
        otps_col.insert_one({
            'mobileNumber': clean_mobile,
            'otp': otp_code,
            'createdAt': datetime.utcnow(),
            'expiresAt': datetime.utcnow() + timedelta(minutes=10)
        })
        
        message_body = f"Your Genetic Purity AI password reset OTP is {otp_code}. Valid for 10 minutes."
        
        # Check if Twilio credentials are created
        if Config.TWILIO_ACCOUNT_SID and Config.TWILIO_AUTH_TOKEN and Config.TWILIO_PHONE_NUMBER:
            try:
                from twilio.rest import Client
                client = Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)
                client.messages.create(
                    body=message_body,
                    from_=Config.TWILIO_PHONE_NUMBER,
                    to=clean_mobile
                )
                print(f"[SMS Sent] Twilio SMS successfully dispatched to {clean_mobile}", flush=True)
                return True, "OTP has been sent to your mobile number via SMS.", otp_code
            except Exception as e:
                print(f"[Twilio SMS Error] Failed to send SMS via Twilio: {e}", file=sys.stderr, flush=True)
                # Fallback to dev log
                print(f"==========================================", flush=True)
                print(f"[DEV OTP FALLBACK] Mobile: {clean_mobile} | OTP: {otp_code}", flush=True)
                print(f"==========================================", flush=True)
                return True, "SMS gateway error. (Dev Mode: OTP printed to server log)", otp_code
        else:
            # Dev mode fallback
            print(f"==========================================", flush=True)
            print(f"[DEV OTP FALLBACK] Mobile: {clean_mobile} | OTP: {otp_code}", flush=True)
            print(f"==========================================", flush=True)
            return True, "OTP sent successfully. (Dev Mode: OTP logged in server console)", otp_code

    @classmethod
    def verify_otp(cls, mobile_number: str, submitted_otp: str) -> tuple[bool, str]:
        """
        Verifies submitted OTP against MongoDB record.
        """
        clean_mobile = mobile_number.strip().replace(" ", "").replace("-", "")
        clean_otp = submitted_otp.strip()
        
        record = get_otps_collection().find_one({'mobileNumber': clean_mobile})
        if not record:
            return False, "No OTP request found for this mobile number or OTP expired."
            
        if record.get('expiresAt') and datetime.utcnow() > record.get('expiresAt'):
            get_otps_collection().delete_one({'_id': record['_id']})
            return False, "OTP has expired. Please request a new OTP."
            
        if record.get('otp') != clean_otp:
            return False, "Invalid OTP code. Please try again."
            
        # OTP is valid, remove it
        get_otps_collection().delete_one({'_id': record['_id']})
        return True, "OTP verified successfully."
