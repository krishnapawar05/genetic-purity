import sys
import os
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv
from config import Config
from database.db import get_otps_collection

class SMSService:
    @staticmethod
    def generate_otp() -> str:
        """Generates a secure 6-digit OTP code for dev fallback."""
        return f"{random.randint(100000, 999999)}"

    @staticmethod
    def format_to_e164(mobile_number: str) -> str:
        """Formats mobile number into valid E.164 international format (+91...)."""
        clean = mobile_number.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if clean.startswith("+"):
            return clean
        if len(clean) == 10 and clean.isdigit():
            return f"+91{clean}"
        return f"+{clean}"

    @classmethod
    def send_otp(cls, mobile_number: str) -> tuple[bool, str, str]:
        """
        Initiates OTP dispatch via Twilio Verify Service (v2 API).
        Uses TWILIO_VERIFY_SERVICE_SID with Twilio's pre-approved default verification template.
        Does NOT use client.messages.create or custom template names.
        Returns (success: bool, message: str, otp_code: str).
        """
        # Force fresh read of environment variables from .env
        load_dotenv(override=True)
        
        clean_mobile = mobile_number.strip().replace(" ", "").replace("-", "")
        e164_mobile = cls.format_to_e164(mobile_number)

        account_sid = (os.getenv('TWILIO_ACCOUNT_SID', '') or Config.TWILIO_ACCOUNT_SID).strip()
        auth_token = (os.getenv('TWILIO_AUTH_TOKEN', '') or Config.TWILIO_AUTH_TOKEN).strip()
        verify_sid = (os.getenv('TWILIO_VERIFY_SERVICE_SID', '') or getattr(Config, 'TWILIO_VERIFY_SERVICE_SID', '')).strip()

        # Check if Twilio Verify credentials are configured
        if account_sid and auth_token and verify_sid:
            try:
                from twilio.rest import Client
                client = Client(account_sid, auth_token)

                # Twilio Verify Service API (Sends SMS using Twilio's pre-approved default verification template)
                verification = client.verify.v2.services(verify_sid).verifications.create(
                    to=e164_mobile,
                    channel='sms'
                )
                print(f"[Twilio Verify API] Requested OTP verification for {e164_mobile}, sid={verification.sid}, status={verification.status}", flush=True)
                return True, "OTP has been sent to your mobile number via SMS.", ""

            except Exception as e:
                # Log detailed Twilio exception on server console silently (NEVER expose SID/Token/error to browser)
                print(f"[Twilio Verify Error] Failed to request OTP via Twilio Verify for {e164_mobile}: {e}", file=sys.stderr, flush=True)
                return False, "Unable to send OTP. Please try again later.", ""

        # Dev Mode Fallback when Twilio credentials are not configured
        otp_code = cls.generate_otp()
        otps_col = get_otps_collection()
        otps_col.delete_many({'mobileNumber': {'$in': [clean_mobile, e164_mobile]}})
        otps_col.insert_one({
            'mobileNumber': clean_mobile,
            'e164Mobile': e164_mobile,
            'otp': otp_code,
            'createdAt': datetime.utcnow(),
            'expiresAt': datetime.utcnow() + timedelta(minutes=10)
        })

        print(f"==========================================", flush=True)
        print(f"[DEV OTP FALLBACK] Mobile: {clean_mobile} ({e164_mobile}) | OTP: {otp_code}", flush=True)
        print(f"==========================================", flush=True)
        return True, "OTP sent successfully. (Dev Mode: OTP logged in server console)", otp_code

    @classmethod
    def verify_otp(cls, mobile_number: str, submitted_otp: str) -> tuple[bool, str]:
        """
        Verifies submitted OTP against Twilio Verify API or MongoDB fallback record.
        """
        load_dotenv(override=True)
        clean_mobile = mobile_number.strip().replace(" ", "").replace("-", "")
        e164_mobile = cls.format_to_e164(mobile_number)
        clean_otp = submitted_otp.strip()

        account_sid = (os.getenv('TWILIO_ACCOUNT_SID', '') or Config.TWILIO_ACCOUNT_SID).strip()
        auth_token = (os.getenv('TWILIO_AUTH_TOKEN', '') or Config.TWILIO_AUTH_TOKEN).strip()
        verify_sid = (os.getenv('TWILIO_VERIFY_SERVICE_SID', '') or getattr(Config, 'TWILIO_VERIFY_SERVICE_SID', '')).strip()

        if account_sid and auth_token and verify_sid:
            try:
                from twilio.rest import Client
                client = Client(account_sid, auth_token)

                verification_check = client.verify.v2.services(verify_sid).verification_checks.create(
                    to=e164_mobile,
                    code=clean_otp
                )
                print(f"[Twilio Verify Check] Checked OTP for {e164_mobile}, status={verification_check.status}", flush=True)
                if verification_check.status == 'approved':
                    return True, "OTP verified successfully."
                else:
                    return False, "Invalid or expired OTP code. Please try again."
            except Exception as e:
                print(f"[Twilio Verify Check Error] Verification check failed: {e}", file=sys.stderr, flush=True)
                # Fallback to check MongoDB if Twilio check encounters an issue
                pass

        # Dev Mode / Fallback MongoDB verification check
        record = get_otps_collection().find_one({'$or': [{'mobileNumber': clean_mobile}, {'mobileNumber': e164_mobile}, {'e164Mobile': e164_mobile}]})
        if not record:
            return False, "No OTP request found for this mobile number or OTP expired."

        if record.get('expiresAt') and datetime.utcnow() > record.get('expiresAt'):
            get_otps_collection().delete_one({'_id': record['_id']})
            return False, "OTP has expired. Please request a new OTP."

        if record.get('otp') != clean_otp:
            return False, "Invalid OTP code. Please try again."

        get_otps_collection().delete_one({'_id': record['_id']})
        return True, "OTP verified successfully."
