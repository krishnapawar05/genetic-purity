from flask import render_template, redirect, url_for, jsonify, request, make_response, flash, current_app
from flask_login import login_required, current_user
import os
from . import main_bp
from models.prediction import PredictionRecord
from models.payment import PaymentRecord
from services.pdf_service import PDFReportService
from database.db import get_payments_collection
from utils.date_utils import format_datetime

@main_bp.route('/')
def index():
    """
    Public Landing Page.
    """
    return render_template('index.html')

@main_bp.route('/dashboard')
@login_required
def dashboard():
    """
    Authenticated User Dashboard showing recent test history and summary metrics.
    """
    user_history = PredictionRecord.get_user_history(current_user.id, limit=10)
    user_stats = PredictionRecord.get_analytics_summary(current_user.id)
    return render_template('dashboard.html', user=current_user, history=user_history, stats=user_stats)

@main_bp.route('/test')
@main_bp.route('/upload')
@login_required
def test_purity():
    """
    Authenticated Plant Genetic Purity Testing UI.
    """
    return render_template('test_purity.html', user=current_user)

@main_bp.route('/result/<prediction_id>')
@login_required
def view_result(prediction_id):
    """
    Dedicated Modern Result View Page for a prediction.
    """
    pred_rec = PredictionRecord.get_by_id(prediction_id)
    if not pred_rec or pred_rec.userId != current_user.id:
        flash("Result record not found or access unauthorized.", "danger")
        return redirect(url_for('main.dashboard'))
        
    pmt_doc = get_payments_collection().find_one({'predictionId': prediction_id})
    pmt_rec = PaymentRecord(pmt_doc) if pmt_doc else None
    
    return render_template('result.html', user=current_user, record=pred_rec, payment=pmt_rec)

@main_bp.route('/download-report/<prediction_id>')
@login_required
def download_report(prediction_id):
    """
    Generates and downloads a PDF Diagnostic Report with QR code verification.
    """
    pred_rec = PredictionRecord.get_by_id(prediction_id)
    if not pred_rec or pred_rec.userId != current_user.id:
        flash("Result record not found or access unauthorized.", "danger")
        return redirect(url_for('main.dashboard'))

    pmt_doc = get_payments_collection().find_one({'predictionId': prediction_id})
    pmt_rec = PaymentRecord(pmt_doc) if pmt_doc else None

    base_url = os.getenv('PUBLIC_BASE_URL', '').strip() or request.host_url.rstrip('/')
    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    
    pdf_bytes = PDFReportService.generate_prediction_pdf(
        user=current_user,
        prediction_rec=pred_rec,
        payment_rec=pmt_rec,
        base_url=base_url,
        upload_folder=upload_folder
    )

    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename="Genetic_Purity_Report_{prediction_id[:8]}.pdf"'
    return response

@main_bp.route('/verify/<token>')
def verify_report(token):
    """
    Public verification endpoint (accessible WITHOUT login).
    Verifies authenticity of a generated diagnostic report by secure token or test ID.
    Does NOT expose any private user details (no names, phones, emails, payment keys, server paths).
    """
    pred_rec = PredictionRecord.get_by_verification_token(token)
    
    if not pred_rec:
        return render_template(
            'verify_report.html',
            is_valid=False,
            error_message="Invalid verification token or report not found."
        ), 404
        
    display_id = f"#GPV-{pred_rec.id[:8].upper()}" if len(pred_rec.id) >= 8 else f"#GPV-{pred_rec.id}"
    test_date_str = format_datetime(pred_rec.createdAt)
    
    # Safe public verification metrics ONLY (NO user full name, mobile, email, password, payment IDs, or server paths)
    public_data = {
        'status': 'VALID',
        'display_id': display_id,
        'crop': getattr(pred_rec, 'crop', None) or 'Chilli / Plant Specimen',
        'sample_filename': pred_rec.filename,
        'test_date': test_date_str,
        'prediction': pred_rec.prediction,
        'purity': pred_rec.purity,
        'confidence': pred_rec.confidence,
        'reliability': pred_rec.reliability
    }
    
    return render_template('verify_report.html', is_valid=True, report=public_data)

@main_bp.route('/analytics')
@login_required
def analytics():
    """
    Analytics & Searchable/Filterable History Dashboard.
    """
    q = request.args.get('q', '').strip()
    class_filter = request.args.get('class_filter', 'all').strip()
    
    stats = PredictionRecord.get_analytics_summary(current_user.id)
    filtered_history = PredictionRecord.search_and_filter(current_user.id, search_query=q, class_filter=class_filter)
    
    # Refresh pending payments before rendering page
    from services.payment_service import PaymentService
    import datetime
    
    pending_pmts = get_payments_collection().find({
        'userId': str(current_user.id),
        'status': 'created'
    })
    
    now = datetime.datetime.utcnow()
    for doc in pending_pmts:
        pmt_rec = PaymentRecord(doc)
        actual_status = PaymentService.verify_order_status(pmt_rec.orderId)
        
        if pmt_rec.orderId.startswith("order_dev_") and pmt_rec.createdAt:
            age_seconds = (now - pmt_rec.createdAt).total_seconds()
            if age_seconds > 300:
                actual_status = 'failed'
                
        if actual_status == 'paid':
            get_payments_collection().update_one(
                {'_id': doc['_id']},
                {'$set': {'status': 'paid', 'updatedAt': now}}
            )
        elif actual_status == 'failed' or (not pmt_rec.orderId.startswith("order_dev_") and pmt_rec.createdAt and (now - pmt_rec.createdAt).total_seconds() > 1800):
            get_payments_collection().update_one(
                {'_id': doc['_id']},
                {'$set': {'status': 'failed', 'updatedAt': now}}
            )

    # Get Payment Transaction History
    pmt_cursor = get_payments_collection().find({'userId': str(current_user.id)}).sort('createdAt', -1).limit(50)
    payments = [PaymentRecord(doc) for doc in pmt_cursor]
    
    return render_template(
        'analytics.html',
        user=current_user,
        stats=stats,
        history=filtered_history,
        payments=payments,
        q=q,
        class_filter=class_filter
    )


@main_bp.route('/api/payment-status')
@login_required
def payment_status_api():
    """
    Returns the user's latest payment records in JSON, after verifying and updating pending transactions.
    """
    from services.payment_service import PaymentService
    import datetime
    
    pending_pmts = get_payments_collection().find({
        'userId': str(current_user.id),
        'status': 'created'
    })
    
    now = datetime.datetime.utcnow()
    for doc in pending_pmts:
        pmt_rec = PaymentRecord(doc)
        actual_status = PaymentService.verify_order_status(pmt_rec.orderId)
        
        if pmt_rec.orderId.startswith("order_dev_") and pmt_rec.createdAt:
            age_seconds = (now - pmt_rec.createdAt).total_seconds()
            if age_seconds > 300:
                actual_status = 'failed'
                
        if actual_status == 'paid':
            get_payments_collection().update_one(
                {'_id': doc['_id']},
                {'$set': {'status': 'paid', 'updatedAt': now}}
            )
        elif actual_status == 'failed' or (not pmt_rec.orderId.startswith("order_dev_") and pmt_rec.createdAt and (now - pmt_rec.createdAt).total_seconds() > 1800):
            get_payments_collection().update_one(
                {'_id': doc['_id']},
                {'$set': {'status': 'failed', 'updatedAt': now}}
            )

    pmt_cursor = get_payments_collection().find({'userId': str(current_user.id)}).sort('createdAt', -1).limit(50)
    payments_data = []
    for doc in pmt_cursor:
        created_str = format_datetime(doc.get('createdAt'))
        
        status_label = 'Pending'
        if doc.get('status') == 'paid':
            status_label = 'Successful'
        elif doc.get('status') == 'failed':
            status_label = 'Cancelled Payment'
            
        payments_data.append({
            'orderId': doc.get('orderId', ''),
            'paymentId': doc.get('paymentId', '') or 'N/A',
            'amount': doc.get('amount', 0),
            'currency': doc.get('currency', 'INR'),
            'status': status_label,
            'date': created_str
        })
        
    return jsonify({"success": True, "payments": payments_data})


@main_bp.route('/payments')
@login_required
def payments():
    """
    Dedicated Payment Logs page.
    """
    from services.payment_service import PaymentService
    import datetime
    
    # Refresh pending payments before rendering
    pending_pmts = get_payments_collection().find({
        'userId': str(current_user.id),
        'status': 'created'
    })
    
    now = datetime.datetime.utcnow()
    for doc in pending_pmts:
        pmt_rec = PaymentRecord(doc)
        actual_status = PaymentService.verify_order_status(pmt_rec.orderId)
        
        if pmt_rec.orderId.startswith("order_dev_") and pmt_rec.createdAt:
            age_seconds = (now - pmt_rec.createdAt).total_seconds()
            if age_seconds > 300:
                actual_status = 'failed'
                
        if actual_status == 'paid':
            get_payments_collection().update_one(
                {'_id': doc['_id']},
                {'$set': {'status': 'paid', 'updatedAt': now}}
            )
        elif actual_status == 'failed' or (not pmt_rec.orderId.startswith("order_dev_") and pmt_rec.createdAt and (now - pmt_rec.createdAt).total_seconds() > 1800):
            get_payments_collection().update_one(
                {'_id': doc['_id']},
                {'$set': {'status': 'failed', 'updatedAt': now}}
            )

    # Get all payments
    pmt_cursor = get_payments_collection().find({'userId': str(current_user.id)}).sort('createdAt', -1).limit(50)
    payments_list = [PaymentRecord(doc) for doc in pmt_cursor]
    
    # Calculate simple statistics
    total_spent = sum(p.amount for p in payments_list if p.status == 'paid')
    total_transactions = len(payments_list)
    successful_count = sum(1 for p in payments_list if p.status == 'paid')
    failed_count = sum(1 for p in payments_list if p.status == 'failed')
    pending_count = sum(1 for p in payments_list if p.status == 'created')
    
    return render_template(
        'payments.html',
        payments=payments_list,
        total_spent=total_spent,
        total_transactions=total_transactions,
        successful_count=successful_count,
        failed_count=failed_count,
        pending_count=pending_count
    )


@main_bp.route('/history')
@login_required
def history():
    """
    Separate screening history page grouped by Year and Month.
    """
    from collections import OrderedDict
    from database.db import get_predictions_collection
    
    cursor = get_predictions_collection().find({'userId': str(current_user.id)}).sort('createdAt', -1)
    records = [PredictionRecord(doc) for doc in cursor]
    
    grouped_history = OrderedDict()
    total_records = len(records)
    
    for rec in records:
        if not rec.createdAt:
            continue
        year = rec.createdAt.year
        month_name = rec.createdAt.strftime('%B')
        
        if year not in grouped_history:
            grouped_history[year] = OrderedDict()
            
        if month_name not in grouped_history[year]:
            grouped_history[year][month_name] = []
            
        grouped_history[year][month_name].append(rec)
        
    return render_template(
        'history.html',
        grouped_history=grouped_history,
        total_records=total_records
    )

@main_bp.route('/customer-use-case', methods=['GET', 'POST'])
@login_required
def customer_use_case():
    from database.db import get_users_collection
    from bson import ObjectId
    
    if request.method == 'POST':
        use_case = request.form.get('useCase', '').strip()
        custom_use_case = request.form.get('customUseCase', '').strip()
        
        selected_use_case = custom_use_case if use_case == 'Other' else use_case
        
        if not selected_use_case:
            flash("Please select or specify a customer use case.", "danger")
            return render_template('customer_use_case.html', user=current_user)
            
        get_users_collection().update_one(
            {'_id': ObjectId(current_user.id)},
            {'$set': {'customerUseCase': selected_use_case}}
        )
        
        current_user.customerUseCase = selected_use_case
        
        flash(f"Thank you! Your customer use case '{selected_use_case}' has been registered.", "success")
        return redirect(url_for('main.dashboard'))
        
    return render_template('customer_use_case.html', user=current_user)
