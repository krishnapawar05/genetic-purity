import re

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
MOBILE_REGEX = re.compile(r'^\+?[0-9]{6,15}$')

def validate_email(email: str) -> tuple[bool, str]:
    if not email or not email.strip():
        return False, "Email address is required."
    clean_email = email.strip()
    if not EMAIL_REGEX.match(clean_email):
        return False, "Please enter a valid email address."
    return True, ""

def validate_mobile(mobile: str) -> tuple[bool, str]:
    if not mobile or not mobile.strip():
        return False, "Mobile number is required."
    clean_mobile = mobile.strip().replace(" ", "").replace("-", "")
    if not MOBILE_REGEX.match(clean_mobile):
        return False, "Please enter a valid mobile number (6 to 15 digits)."
    return True, ""

def validate_password_strength(password: str) -> tuple[bool, str]:
    if not password:
        return False, "Password is required."
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one number."
    return True, ""

def validate_signup_input(data: dict) -> tuple[bool, list[str]]:
    errors = []
    
    first_name = data.get('firstName', '').strip()
    last_name = data.get('lastName', '').strip()
    username = data.get('username', '').strip()
    mobile = data.get('mobileNumber', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    confirm_password = data.get('confirmPassword', '')
    
    if not first_name:
        errors.append("First name is required.")
    if not last_name:
        errors.append("Last name is required.")
    if not username:
        errors.append("Username is required.")
    elif not username.isalnum() or len(username) < 3:
        errors.append("Username must be at least 3 characters long and contain only alphanumeric characters.")
        
    valid_m, err_m = validate_mobile(mobile)
    if not valid_m:
        errors.append(err_m)
        
    valid_e, err_e = validate_email(email)
    if not valid_e:
        errors.append(err_e)
        
    valid_p, err_p = validate_password_strength(password)
    if not valid_p:
        errors.append(err_p)
        
    if password != confirm_password:
        errors.append("Passwords do not match.")
        
    return len(errors) == 0, errors
