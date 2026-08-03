from datetime import datetime
from bson import ObjectId
from database.db import get_payments_collection

class PaymentRecord:
    def __init__(self, doc: dict):
        self.id = str(doc.get('_id'))
        self.userId = str(doc.get('userId'))
        self.orderId = doc.get('orderId', '')
        self.paymentId = doc.get('paymentId', '')
        self.signature = doc.get('signature', '')
        self.amount = doc.get('amount', 0)
        self.currency = doc.get('currency', 'INR')
        self.status = doc.get('status', 'created')
        self.tempSpecimenPath = doc.get('tempSpecimenPath', '')
        self.tempToken = doc.get('tempToken', '')
        self.predictionId = doc.get('predictionId', '')
        self.createdAt = doc.get('createdAt')

    @classmethod
    def create_pending_payment(cls, user_id: str, order_id: str, amount: int, currency: str, temp_path: str, temp_token: str):
        """
        Creates a pending payment record in MongoDB prior to payment completion.
        """
        now = datetime.utcnow()
        doc = {
            'userId': user_id,
            'orderId': order_id,
            'paymentId': '',
            'signature': '',
            'amount': amount,
            'currency': currency,
            'status': 'created',
            'tempSpecimenPath': temp_path,
            'tempToken': temp_token,
            'predictionId': '',
            'createdAt': now
        }
        
        pmts_col = get_payments_collection()
        res = pmts_col.insert_one(doc)
        doc['_id'] = res.inserted_id
        return cls(doc)

    @classmethod
    def get_by_order_id(cls, order_id: str):
        if not order_id:
            return None
        doc = get_payments_collection().find_one({'orderId': order_id})
        return cls(doc) if doc else None

    @classmethod
    def get_by_token(cls, temp_token: str):
        if not temp_token:
            return None
        doc = get_payments_collection().find_one({'tempToken': temp_token})
        return cls(doc) if doc else None

    @classmethod
    def mark_completed(cls, order_id: str, payment_id: str, signature: str, prediction_id: str):
        """
        Marks payment record as paid, storing paymentId, signature, and predictionId.
        """
        try:
            get_payments_collection().update_one(
                {'orderId': order_id},
                {
                    '$set': {
                        'paymentId': payment_id,
                        'signature': signature,
                        'predictionId': prediction_id,
                        'status': 'paid',
                        'updatedAt': datetime.utcnow()
                    }
                }
            )
            return True
        except Exception as e:
            print(f"Error marking payment completed: {e}")
            return False

    @classmethod
    def mark_failed(cls, order_id: str, reason: str = ""):
        """
        Marks payment record as failed.
        """
        try:
            get_payments_collection().update_one(
                {'orderId': order_id},
                {
                    '$set': {
                        'status': 'failed',
                        'failReason': reason,
                        'updatedAt': datetime.utcnow()
                    }
                }
            )
            return True
        except Exception:
            return False
