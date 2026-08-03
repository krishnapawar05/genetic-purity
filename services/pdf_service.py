import io
import os
import qrcode
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable

class PDFReportService:
    @classmethod
    def generate_prediction_pdf(cls, user, prediction_rec, payment_rec=None, base_url="http://127.0.0.1:5000") -> bytes:
        """
        Generates a PDF diagnostic report in memory and returns raw bytes.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()
        
        # Custom Colors
        primary_color = colors.HexColor('#059669') # Emerald
        dark_bg = colors.HexColor('#0b0f19')
        text_dark = colors.HexColor('#1f2937')
        slate_grey = colors.HexColor('#4b5563')
        light_bg = colors.HexColor('#f3f4f6')

        # Custom Paragraph Styles
        title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=20,
            leading=24,
            textColor=primary_color
        )

        subtitle_style = ParagraphStyle(
            'ReportSubtitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=12,
            textColor=slate_grey
        )

        section_heading = ParagraphStyle(
            'SectionHeading',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=12,
            leading=14,
            textColor=primary_color,
            spaceAfter=6
        )

        cell_label = ParagraphStyle(
            'CellLabel',
            fontName='Helvetica-Bold',
            fontSize=9,
            leading=11,
            textColor=slate_grey
        )

        cell_value = ParagraphStyle(
            'CellValue',
            fontName='Helvetica',
            fontSize=9,
            leading=11,
            textColor=text_dark
        )

        story = []

        # 1. Header Table (Institution Name & Logo / Date)
        verify_url = f"{base_url}/result/{prediction_rec.id}"
        
        # Generate QR Code image in memory
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=4,
            border=2,
        )
        qr.add_data(verify_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        qr_buffer = io.BytesIO()
        qr_img.save(qr_buffer, format='PNG')
        qr_buffer.seek(0)
        qr_reportlab_img = Image(qr_buffer, width=64, height=64)

        header_data = [
            [
                Paragraph("<b>GENETIC PURITY AI</b><br/><font size=8 color='#4b5563'>Agricultural Intelligence Labs - Official Diagnostic Report</font>", title_style),
                qr_reportlab_img
            ]
        ]
        
        header_table = Table(header_data, colWidths=[420, 120])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", thickness=1.5, color=primary_color, spaceAfter=15))

        # 2. Metadata Grid (User & Specimen Details)
        created_str = prediction_rec.createdAt.strftime('%B %d, %Y - %H:%M:%S UTC') if prediction_rec.createdAt else datetime.utcnow().strftime('%B %d, %Y')
        payment_id_str = payment_rec.paymentId if payment_rec and payment_rec.paymentId else (payment_rec.orderId if payment_rec else "PAY-PREPAID-VERIFIED")

        user_info_data = [
            [Paragraph("<b>USER & TEST METADATA</b>", section_heading), ""],
            [Paragraph("<b>Client Name:</b>", cell_label), Paragraph(user.full_name, cell_value)],
            [Paragraph("<b>Email Address:</b>", cell_label), Paragraph(user.email, cell_value)],
            [Paragraph("<b>Mobile Number:</b>", cell_label), Paragraph(user.mobileNumber, cell_value)],
            [Paragraph("<b>Specimen Filename:</b>", cell_label), Paragraph(prediction_rec.filename, cell_value)],
            [Paragraph("<b>Report Issue Date:</b>", cell_label), Paragraph(created_str, cell_value)],
            [Paragraph("<b>Payment Transaction ID:</b>", cell_label), Paragraph(payment_id_str, cell_value)],
        ]

        user_table = Table(user_info_data, colWidths=[150, 390])
        user_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), light_bg),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ]))
        story.append(user_table)
        story.append(Spacer(1, 15))

        # 3. Diagnostic Results Box
        verdict_color = "#059669" if prediction_rec.purity.lower().startswith('pure') and prediction_rec.prediction != 'UNKNOWN' else "#d97706"
        
        result_box_data = [
            [Paragraph("<b>NEURAL DIAGNOSTIC DIAGNOSIS RESULTS</b>", section_heading), ""],
            [Paragraph("<b>Predicted Class Variant:</b>", cell_label), Paragraph(f"<b>{prediction_rec.prediction}</b>", cell_value)],
            [Paragraph("<b>Genetic Purity Verdict:</b>", cell_label), Paragraph(f"<font color='{verdict_color}'><b>{prediction_rec.purity}</b></font>", cell_value)],
            [Paragraph("<b>Model Confidence Score:</b>", cell_label), Paragraph(f"<b>{prediction_rec.confidence}</b>", cell_value)],
            [Paragraph("<b>Reliability Assessment:</b>", cell_label), Paragraph(f"<b>{prediction_rec.reliability}</b>", cell_value)],
            [Paragraph("<b>Inference Pipeline Time:</b>", cell_label), Paragraph(prediction_rec.predictionTime, cell_value)],
            [Paragraph("<b>Diagnostic Summary:</b>", cell_label), Paragraph(prediction_rec.reason, cell_value)],
        ]

        result_table = Table(result_box_data, colWidths=[150, 390])
        result_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ecfdf5')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1fae5')),
        ]))
        story.append(result_table)
        story.append(Spacer(1, 15))

        # 4. Class Probability Distribution Table
        probs = prediction_rec.probabilities or {}
        female_p = f"{probs.get('female', 0.0):.2f}%"
        hybrid_p = f"{probs.get('hybrid', 0.0):.2f}%"
        male_p = f"{probs.get('male', 0.0):.2f}%"

        prob_data = [
            [Paragraph("<b>CLASS PROBABILITY DISTRIBUTION BREAKDOWN</b>", section_heading), "", ""],
            [Paragraph("<b>Female Inbred Line</b>", cell_label), Paragraph("<b>Pure Hybrid Seed</b>", cell_label), Paragraph("<b>Male Inbred Line</b>", cell_label)],
            [Paragraph(female_p, cell_value), Paragraph(hybrid_p, cell_value), Paragraph(male_p, cell_value)],
        ]

        prob_table = Table(prob_data, colWidths=[180, 180, 180])
        prob_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), light_bg),
            ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(prob_table)
        story.append(Spacer(1, 20))

        # 5. Footer & Authenticity Notice
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e5e7eb'), spaceAfter=10))
        footer_text = Paragraph(
            f"<font size=7 color='#6b7280'>This official PDF diagnostic report was generated automatically by Genetic Purity AI Neural Middleware Engine.<br/>Scan the QR code above or visit {verify_url} to verify online authenticity.<br/>&copy; 2026 Genetic Purity AI Inc. All rights reserved.</font>",
            subtitle_style
        )
        story.append(footer_text)

        # Build document
        doc.build(story)
        pdf_data = buffer.getvalue()
        buffer.close()
        return pdf_data
