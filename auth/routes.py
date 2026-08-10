from flask import render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from . import auth_bp
from models.user import User
from services.sms_service import SMSService
from utils.validators import validate_signup_input, validate_password_strength, validate_mobile

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
        
    if request.method == 'POST':
        first_name = request.form.get('firstName', '')
        last_name = request.form.get('lastName', '')
        username = request.form.get('username', '')
        email = request.form.get('email', '')
        country_code = request.form.get('countryCode', '')
        mobile = request.form.get('mobileNumber', '')
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirmPassword', '')
        
        form_data = {
            'firstName': first_name,
            'lastName': last_name,
            'username': username,
            'email': email,
            'countryCode': country_code,
            'mobileNumber': mobile,
            'password': password,
            'confirmPassword': confirm_password
        }
        
        valid, errors = validate_signup_input(form_data)
        
        if valid:
            # Check duplicate email
            if User.get_by_email(email):
                errors.append("An account with this email address already exists.")
            # Check duplicate username
            if User.get_by_username(username):
                errors.append("An account with this username already exists.")
            # Check duplicate mobile
            if User.get_by_mobile(mobile, country_code=country_code):
                errors.append("An account with this mobile number already exists.")
                
        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('auth/signup.html', form_data=form_data)
            
        # Create new user
        user = User.create_user(
            first_name=first_name,
            last_name=last_name,
            username=username,
            mobile=mobile,
            email=email,
            password=password,
            country_code=country_code
        )
        
        # Log user in directly after signup
        User.update_last_login(user.id)
        login_user(user)
        flash("Account created successfully! Welcome to Gen Pure Vision.", "success")
        
        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        return redirect(url_for('main.dashboard'))
        
    return render_template('auth/signup.html', form_data={})

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
        
    if request.method == 'POST':
        login_method = request.form.get('loginMethod', 'email')
        remember = True if request.form.get('rememberMe') else False
        
        user = None
        error_msg = ""
        
        if login_method == 'username':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            if not username or not password:
                error_msg = "Please enter both username and password."
            else:
                user = User.get_by_username(username)
                if not user or not user.check_password(password):
                    error_msg = "Invalid username or password."
                    
        elif login_method == 'mobile':
            country_code = request.form.get('countryCode', '').strip()
            mobile = request.form.get('mobileNumber', '').strip()
            password = request.form.get('password', '')
            if not mobile or not password:
                error_msg = "Please enter both mobile number and password."
            else:
                user = User.get_by_mobile(mobile, country_code=country_code)
                if not user or not user.check_password(password):
                    error_msg = "Invalid mobile number or password."
                    
        else: # email
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '')
            if not email or not password:
                error_msg = "Please enter both email and password."
            else:
                user = User.get_by_email(email)
                if not user or not user.check_password(password):
                    error_msg = "Invalid email or password."
                    
        if error_msg:
            flash(error_msg, 'danger')
            return render_template('auth/login.html', login_method=login_method, form_data=request.form)
            
        User.update_last_login(user.id)
        login_user(user, remember=remember)
        from datetime import datetime, timezone
        session['last_activity'] = datetime.now(timezone.utc).isoformat()
        session.permanent = True
        flash(f"Welcome back, {user.firstName}!", "success")
        
        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        return redirect(url_for('main.dashboard'))
        
    return render_template('auth/login.html', login_method='email', form_data={})

@auth_bp.route('/logout')
@login_required
def logout():
    reason = request.args.get('reason')
    logout_user()
    session.clear()
    if reason == 'inactivity':
        flash("Your session has expired due to inactivity. Please sign in again.", "warning")
        return redirect(url_for('auth.login'))
    flash("You have been logged out safely.", "info")
    return redirect(url_for('main.index'))

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        mobile = request.form.get('mobileNumber', '')
        valid, err = validate_mobile(mobile)
        if not valid:
            flash(err, "danger")
            return render_template('auth/forgot_password.html', mobile=mobile)
            
        user = User.get_by_mobile(mobile)
        if not user:
            flash("No registered user found with this mobile number.", "danger")
            return render_template('auth/forgot_password.html', mobile=mobile)
            
        # Send OTP
        success, msg, _ = SMSService.send_otp(mobile)
        if not success:
            flash(msg or "Unable to send OTP. Please try again later.", "danger")
            return render_template('auth/forgot_password.html', mobile=mobile)

        session['reset_mobile'] = mobile.strip().replace(" ", "").replace("-", "")
        session['reset_user_id'] = user.id
        flash(msg, "info")
        return redirect(url_for('auth.verify_otp'))
        
    return render_template('auth/forgot_password.html')

@auth_bp.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    mobile = session.get('reset_mobile')
    if not mobile:
        flash("Please enter your mobile number first.", "warning")
        return redirect(url_for('auth.forgot_password'))
        
    if request.method == 'POST':
        otp_input = request.form.get('otp', '')
        success, msg = SMSService.verify_otp(mobile, otp_input)
        if not success:
            flash(msg, "danger")
            return render_template('auth/verify_otp.html', mobile=mobile)
            
        session['otp_verified'] = True
        flash("OTP verified successfully! Please enter your new password.", "success")
        return redirect(url_for('auth.reset_password'))
        
    return render_template('auth/verify_otp.html', mobile=mobile)

@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if not session.get('otp_verified') or not session.get('reset_user_id'):
        flash("Unauthorized access. Please complete OTP verification first.", "danger")
        return redirect(url_for('auth.forgot_password'))
        
    if request.method == 'POST':
        new_password = request.form.get('newPassword', '')
        confirm_password = request.form.get('confirmPassword', '')
        
        valid_p, err_p = validate_password_strength(new_password)
        if not valid_p:
            flash(err_p, "danger")
            return render_template('auth/reset_password.html')
            
        if new_password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template('auth/reset_password.html')
            
        user_id = session.get('reset_user_id')
        if User.update_password(user_id, new_password):
            # Clear reset session variables
            session.pop('reset_mobile', None)
            session.pop('reset_user_id', None)
            session.pop('otp_verified', None)
            flash("Your password has been reset successfully! Please log in.", "success")
            return redirect(url_for('auth.login'))
        else:
            flash("Failed to update password. Please try again.", "danger")
            
    return render_template('auth/reset_password.html')
