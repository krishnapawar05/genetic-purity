from flask import render_template, redirect, url_for, jsonify, request, make_response, flash
from flask_login import login_required, current_user
from . import main_bp
from models.prediction import PredictionRecord
from models.payment import PaymentRecord
from services.pdf_service import PDFReportService
from database.db import get_payments_collection

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

    base_url = request.host_url.rstrip('/')
    pdf_bytes = PDFReportService.generate_prediction_pdf(
        user=current_user,
        prediction_rec=pred_rec,
        payment_rec=pmt_rec,
        base_url=base_url
    )

    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename="Genetic_Purity_Report_{prediction_id[:8]}.pdf"'
    return response

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
