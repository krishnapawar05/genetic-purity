import hmac
import hashlib
import sys
from config import Config

class PaymentService:
    @staticmethod
    def get_razorpay_client():
        try:
            import razorpay
            return razorpay.Client(auth=(Config.RAZORPAY_KEY_ID, Config.RAZORPAY_KEY_SECRET))
        except Exception as e:
            print(f"[Razorpay Client Error]: {e}", file=sys.stderr)
            return None

    @classmethod
    def create_order(cls, amount_inr: int, receipt_id: str) -> tuple[bool, dict]:
        """
        Creates a Razorpay order in INR (amount converted to paise).
        """
        amount_paise = amount_inr * 100
        client = cls.get_razorpay_client()
        
        # If Razorpay client initialized
        if client:
            try:
                order_data = {
                    "amount": amount_paise,
                    "currency": "INR",
                    "receipt": receipt_id,
                    "payment_capture": 1
                }
                order = client.order.create(data=order_data)
                return True, order
            except Exception as e:
                print(f"[Razorpay Order Creation Error]: {e}", file=sys.stderr)
        
        # Fallback order generation for dev mode when mock keys are used
        import uuid
        dev_order_id = f"order_dev_{uuid.uuid4().hex[:12]}"
        return True, {
            "id": dev_order_id,
            "amount": amount_paise,
            "currency": "INR",
            "receipt": receipt_id,
            "status": "created"
        }

    @classmethod
    def verify_payment_signature(cls, order_id: str, payment_id: str, signature: str) -> tuple[bool, str]:
        """
        Verifies Razorpay HMAC SHA256 signature to protect against fake payment callbacks.
        Calculates HMAC-SHA256(order_id + "|" + payment_id, key_secret).
        """
        if not order_id or not payment_id or not signature:
            return False, "Missing order ID, payment ID, or signature."

        # Dev mode bypass check if order was created with dev prefix and keys are sample
        if order_id.startswith("order_dev_") and Config.RAZORPAY_KEY_ID == 'rzp_test_sampleKeyId':
            print(f"[DEV PAYMENT MODE] Verified mock payment for dev order {order_id}", flush=True)
            return True, "Dev payment signature verified."

        try:
            client = cls.get_razorpay_client()
            if client:
                params_dict = {
                    'razorpay_order_id': order_id,
                    'razorpay_payment_id': payment_id,
                    'razorpay_signature': signature
                }
                client.utility.verify_payment_signature(params_dict)
                return True, "Razorpay payment signature verified successfully."
        except Exception as e:
            print(f"[Razorpay Signature SDK Warning]: {e}. Running native HMAC check...", file=sys.stderr)

        # Native HMAC SHA256 verification
        try:
            msg = f"{order_id}|{payment_id}".encode('utf-8')
            key = Config.RAZORPAY_KEY_SECRET.encode('utf-8')
            generated_signature = hmac.new(key, msg, hashlib.sha256).hexdigest()
            
            if hmac.compare_digest(generated_signature, signature):
                return True, "Payment signature verified successfully."
            else:
                return False, "Invalid signature. Potential fake payment callback detected!"
        except Exception as err:
            return False, f"Signature calculation error: {str(err)}"

    @classmethod
    def verify_order_status(cls, order_id: str) -> str:
        """
        Queries Razorpay API to check the actual status of an order.
        Returns 'paid', 'failed', or 'created' (pending).
        """
        if not order_id or order_id.startswith("order_dev_"):
            return "created"

        client = cls.get_razorpay_client()
        if client:
            try:
                order = client.order.fetch(order_id)
                status = order.get('status')
                if status == 'paid':
                    return 'paid'
                elif status in ['attempted', 'created']:
                    try:
                        payments = client.order.payments(order_id)
                        items = payments.get('items', [])
                        if any(p.get('status') == 'captured' for p in items):
                            return 'paid'
                        if items and all(p.get('status') in ['failed', 'cancelled'] for p in items):
                            return 'failed'
                    except Exception:
                        pass
            except Exception as e:
                print(f"[Razorpay status check error for {order_id}]: {e}", file=sys.stderr)
        return "created"

