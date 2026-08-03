from datetime import datetime
from bson import ObjectId
import bcrypt
from flask_login import UserMixin
from database.db import get_users_collection

class User(UserMixin):
    def __init__(self, user_doc: dict):
        self.user_doc = user_doc
        self.id = str(user_doc.get('_id'))
        self.firstName = user_doc.get('firstName', '')
        self.lastName = user_doc.get('lastName', '')
        self.mobileNumber = user_doc.get('mobileNumber', '')
        self.email = user_doc.get('email', '')
        self.passwordHash = user_doc.get('passwordHash', '')
        self.createdAt = user_doc.get('createdAt')
        self.updatedAt = user_doc.get('updatedAt')
        self.isVerified = user_doc.get('isVerified', False)
        self.role = user_doc.get('role', 'user')

    def get_id(self):
        return self.id

    @property
    def full_name(self):
        return f"{self.firstName} {self.lastName}".strip()

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hashes password using bcrypt.
        """
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    def check_password(self, password: str) -> bool:
        """
        Verifies plaintext password against bcrypt hash.
        """
        if not self.passwordHash:
            return False
        return bcrypt.checkpw(password.encode('utf-8'), self.passwordHash.encode('utf-8'))

    @classmethod
    def get_by_id(cls, user_id: str):
        try:
            doc = get_users_collection().find_one({'_id': ObjectId(user_id)})
            return cls(doc) if doc else None
        except Exception:
            return None

    @classmethod
    def get_by_email(cls, email: str):
        if not email:
            return None
        doc = get_users_collection().find_one({'email': email.strip().lower()})
        return cls(doc) if doc else None

    @classmethod
    def get_by_mobile(cls, mobile: str):
        if not mobile:
            return None
        clean_mobile = mobile.strip().replace(" ", "").replace("-", "")
        doc = get_users_collection().find_one({'mobileNumber': clean_mobile})
        return cls(doc) if doc else None

    @classmethod
    def get_by_email_or_mobile(cls, identifier: str):
        if not identifier:
            return None
        clean_id = identifier.strip()
        # Clean mobile representation
        clean_mobile = clean_id.replace(" ", "").replace("-", "")
        doc = get_users_collection().find_one({
            '$or': [
                {'email': clean_id.lower()},
                {'mobileNumber': clean_mobile}
            ]
        })
        return cls(doc) if doc else None

    @classmethod
    def create_user(cls, first_name: str, last_name: str, mobile: str, email: str, password: str, role: str = 'user'):
        clean_email = email.strip().lower()
        clean_mobile = mobile.strip().replace(" ", "").replace("-", "")
        now = datetime.utcnow()
        
        doc = {
            'firstName': first_name.strip(),
            'lastName': last_name.strip(),
            'mobileNumber': clean_mobile,
            'email': clean_email,
            'passwordHash': cls.hash_password(password),
            'createdAt': now,
            'updatedAt': now,
            'isVerified': True,  # Default to True upon registration
            'role': role
        }
        
        result = get_users_collection().insert_one(doc)
        doc['_id'] = result.inserted_id
        return cls(doc)

    @classmethod
    def update_password(cls, user_id: str, new_password: str) -> bool:
        try:
            new_hash = cls.hash_password(new_password)
            result = get_users_collection().update_one(
                {'_id': ObjectId(user_id)},
                {
                    '$set': {
                        'passwordHash': new_hash,
                        'updatedAt': datetime.utcnow()
                    }
                }
            )
            return result.modified_count > 0
        except Exception:
            return False
