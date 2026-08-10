import io
import os
import logging
import qrcode
from PIL import Image as PILImage
from datetime import datetime
from utils.date_utils import format_datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable
from reportlab.pdfgen import canvas

logger = logging.getLogger("GeneticPurityAI")


class NumberedCanvasFactory:
    """
    Factory creating a ReportLab two-pass Canvas decorator that draws a
    fixed page-level footer (with Page X of Y and online verification URL)
    at fixed physical coordinates at the bottom of EVERY page.
    """
    @staticmethod
    def create(verify_url_str):
        class CustomNumberedCanvas(canvas.Canvas):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._saved_page_states = []

            def showPage(self):
                self._saved_page_states.append(dict(self.__dict__))
                self._startPage()

            def save(self):
                num_pages = len(self._saved_page_states)
                for state in self._saved_page_states:
                    self.__dict__.update(state)
                    self.draw_page_decorations(num_pages)
                    super().showPage()
                super().save()

            def draw_page_decorations(self, page_count):
                self.saveState()
                page_w, page_h = self._pagesize
                
                # FIXED PAGE FOOTER (Renders at physical bottom y = 13pt to 36pt of page)
                self.setStrokeColor(colors.HexColor('#cbd5e1'))
                self.setLineWidth(0.75)
                self.line(32, 36, page_w - 32, 36)
                
                # Left footer branding
                self.setFont('Helvetica-Bold', 8)
                self.setFillColor(colors.HexColor('#059669'))
                self.drawString(32, 24, "GENETIC PURITY AI")
                
                self.setFont('Helvetica', 8)
                self.setFillColor(colors.HexColor('#475569'))
                self.drawString(124, 24, "•   Agricultural Intelligence Diagnostic Report")
                
                # Right footer: Page X of Y
                page_str = f"Page {self._pageNumber} of {page_count}"
                self.drawRightString(page_w - 32, 24, page_str)
                
                # Subtext (y = 13pt)
                self.setFont('Helvetica', 7)
                self.setFillColor(colors.HexColor('#64748b'))
                self.drawString(32, 13, f"Scan QR code or visit {verify_url_str} to verify report online authenticity.")
                
                self.restoreState()

        return CustomNumberedCanvas


class PDFReportService:
    @classmethod
    def generate_prediction_pdf(cls, user, prediction_rec, payment_rec=None, base_url="http://127.0.0.1:5000", upload_folder=None) -> bytes:
        """
        Generates an official single-page A4 PDF diagnostic report containing:
        - Header branding with QR Code verification
        - TESTED SPECIMEN INFORMATION (aspect-ratio preserved image, Test ID, Crop/Sample info)
        - User & Transaction Metadata
        - Diagnostic summary & class probability breakdown
        - Fixed physical page footer with Page 1 of 1
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=32,
            leftMargin=32,
            topMargin=26,
            bottomMargin=42  # Safe margin above canvas footer line (y = 36pt)
        )

        styles = getSampleStyleSheet()
        
        # Custom Colors
        primary_color = colors.HexColor('#059669') # Emerald
        dark_bg = colors.HexColor('#0b0f19')
        text_dark = colors.HexColor('#1f2937')
        slate_grey = colors.HexColor('#475569')
        light_bg = colors.HexColor('#f8fafc')

        # Custom Paragraph Styles (Optimized for 1-page A4 fit)
        title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=16,
            leading=18,
            textColor=primary_color
        )

        section_heading = ParagraphStyle(
            'SectionHeading',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=9.5,
            leading=11,
            textColor=primary_color,
            spaceAfter=2
        )

        cell_label = ParagraphStyle(
            'CellLabel',
            fontName='Helvetica-Bold',
            fontSize=8.5,
            leading=10.5,
            textColor=slate_grey
        )

        cell_value = ParagraphStyle(
            'CellValue',
            fontName='Helvetica',
            fontSize=8.5,
            leading=10.5,
            textColor=text_dark
        )

        cell_value_sm = ParagraphStyle(
            'CellValueSm',
            fontName='Helvetica',
            fontSize=8.0,
            leading=9.5,
            textColor=text_dark
        )

        story = []

        # 1. Header Table (Institution Name & Logo / Public Verification QR Code)
        token = getattr(prediction_rec, 'verificationToken', None) or prediction_rec.id
        verify_url = f"{base_url}/verify/{token}"
        
        # Generate QR Code image in memory
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=3,
            border=1,
        )
        qr.add_data(verify_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        qr_buffer = io.BytesIO()
        qr_img.save(qr_buffer, format='PNG')
        qr_buffer.seek(0)
        qr_reportlab_img = Image(qr_buffer, width=48, height=48)

        header_data = [
            [
                Paragraph("<b>GENETIC PURITY AI</b><br/><font size=8 color='#475569'>Agricultural Intelligence Labs - Official Diagnostic Report</font>", title_style),
                qr_reportlab_img
            ]
        ]
        
        header_table = Table(header_data, colWidths=[410, 121])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 4))
        story.append(HRFlowable(width="100%", thickness=1.2, color=primary_color, spaceAfter=6))

        # 2. TESTED SPECIMEN INFORMATION Section
        display_test_id = f"#GPV-{prediction_rec.id[:8].upper()}" if len(prediction_rec.id) >= 8 else f"#GPV-{prediction_rec.id}"
        crop_info = getattr(prediction_rec, 'crop', None) or getattr(user, 'customerUseCase', None) or 'Chilli / Plant Specimen'
        sample_info = prediction_rec.filename if prediction_rec.filename else 'Not Provided'

        # Locate Specimen Image File safely
        specimen_file_path = None
        if getattr(prediction_rec, 'specimenPath', None):
            specimen_file_path = prediction_rec.specimenPath
            if not os.path.isabs(specimen_file_path) and upload_folder:
                p1 = os.path.join(upload_folder, 'specimens', specimen_file_path)
                p2 = os.path.join(upload_folder, specimen_file_path)
                if os.path.exists(p1):
                    specimen_file_path = p1
                elif os.path.exists(p2):
                    specimen_file_path = p2

        if not specimen_file_path or not os.path.exists(specimen_file_path):
            if upload_folder:
                fallback_p = os.path.join(upload_folder, 'specimens', f"specimen_{prediction_rec.id}.jpg")
                if os.path.exists(fallback_p):
                    specimen_file_path = fallback_p

        # Render Specimen Image Flowable maintaining aspect ratio (Compact max_h=65.0)
        specimen_img_flowable = None
        if specimen_file_path and os.path.exists(specimen_file_path):
            try:
                with PILImage.open(specimen_file_path) as pimg:
                    pw, ph = pimg.size
                    aspect = pw / float(ph) if ph > 0 else 1.0
                    max_w, max_h = 130.0, 65.0
                    if pw > max_w or ph > max_h:
                        if aspect > (max_w / max_h):
                            target_w = max_w
                            target_h = max_w / aspect
                        else:
                            target_h = max_h
                            target_w = max_h * aspect
                    else:
                        target_w, target_h = float(pw), float(ph)
                specimen_img_flowable = Image(specimen_file_path, width=target_w, height=target_h)
            except Exception as e:
                logger.warning(f"Failed to load specimen image for PDF: {e}")
                specimen_img_flowable = Paragraph("<i>Specimen image unavailable</i>", cell_value)
        else:
            specimen_img_flowable = Paragraph("<i>Specimen image unavailable</i>", cell_value)

        specimen_info_data = [
            [Paragraph("<b>TESTED SPECIMEN INFORMATION</b>", section_heading), ""],
            [Paragraph("<b>Specimen Test ID:</b>", cell_label), Paragraph(f"<b>{display_test_id}</b>", cell_value)],
            [Paragraph("<b>Crop / Specimen Category:</b>", cell_label), Paragraph(crop_info, cell_value)],
            [Paragraph("<b>Sample Filename:</b>", cell_label), Paragraph(sample_info, cell_value)],
            [Paragraph("<b>Tested Specimen Image:</b>", cell_label), specimen_img_flowable],
        ]

        specimen_table = Table(specimen_info_data, colWidths=[140, 391])
        specimen_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
            ('TOPPADDING', (0, 0), (-1, -1), 2.5),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('VALIGN', (0, 4), (-1, 4), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ]))
        story.append(specimen_table)
        story.append(Spacer(1, 6))

        # 3. User & Test Metadata Grid
        created_str = format_datetime(prediction_rec.createdAt)
        payment_id_str = payment_rec.paymentId if payment_rec and payment_rec.paymentId else (payment_rec.orderId if payment_rec else "PAY-PREPAID-VERIFIED")

        user_info_data = [
            [Paragraph("<b>USER & TRANSACTION METADATA</b>", section_heading), ""],
            [Paragraph("<b>Client Name:</b>", cell_label), Paragraph(user.full_name, cell_value)],
            [Paragraph("<b>Email Address:</b>", cell_label), Paragraph(user.email, cell_value)],
            [Paragraph("<b>Mobile Number:</b>", cell_label), Paragraph(user.mobileNumber, cell_value)],
            [Paragraph("<b>Report Issue Date:</b>", cell_label), Paragraph(created_str, cell_value)],
            [Paragraph("<b>Payment Transaction ID:</b>", cell_label), Paragraph(payment_id_str, cell_value)],
        ]

        user_table = Table(user_info_data, colWidths=[140, 391])
        user_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), light_bg),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
            ('TOPPADDING', (0, 0), (-1, -1), 2.5),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ]))
        story.append(user_table)
        story.append(Spacer(1, 6))

        # 4. Diagnostic Results Box
        verdict_color = "#059669" if prediction_rec.purity.lower().startswith('pure') and prediction_rec.prediction != 'UNKNOWN' else "#d97706"
        
        result_box_data = [
            [Paragraph("<b>NEURAL DIAGNOSTIC DIAGNOSIS RESULTS</b>", section_heading), ""],
            [Paragraph("<b>Predicted Class Variant:</b>", cell_label), Paragraph(f"<b>{prediction_rec.prediction}</b>", cell_value)],
            [Paragraph("<b>Genetic Purity Verdict:</b>", cell_label), Paragraph(f"<font color='{verdict_color}'><b>{prediction_rec.purity}</b></font>", cell_value)],
            [Paragraph("<b>Model Confidence Score:</b>", cell_label), Paragraph(f"<b>{prediction_rec.confidence}</b>", cell_value)],
            [Paragraph("<b>Reliability Assessment:</b>", cell_label), Paragraph(f"<b>{prediction_rec.reliability}</b>", cell_value)],
            [Paragraph("<b>Inference Pipeline Time:</b>", cell_label), Paragraph(prediction_rec.predictionTime, cell_value)],
            [Paragraph("<b>Diagnostic Summary:</b>", cell_label), Paragraph(prediction_rec.reason, cell_value_sm)],
        ]

        result_table = Table(result_box_data, colWidths=[140, 391])
        result_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ecfdf5')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
            ('TOPPADDING', (0, 0), (-1, -1), 2.5),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#a7f3d0')),
        ]))
        story.append(result_table)
        story.append(Spacer(1, 6))

        # 5. Class Probability Distribution Table
        probs = prediction_rec.probabilities or {}
        female_p = f"{probs.get('female', 0.0):.2f}%"
        hybrid_p = f"{probs.get('hybrid', 0.0):.2f}%"
        male_p = f"{probs.get('male', 0.0):.2f}%"

        prob_data = [
            [Paragraph("<b>CLASS PROBABILITY DISTRIBUTION BREAKDOWN</b>", section_heading), "", ""],
            [Paragraph("<b>Female Inbred Line</b>", cell_label), Paragraph("<b>Pure Hybrid Seed</b>", cell_label), Paragraph("<b>Male Inbred Line</b>", cell_label)],
            [Paragraph(female_p, cell_value), Paragraph(hybrid_p, cell_value), Paragraph(male_p, cell_value)],
        ]

        prob_table = Table(prob_data, colWidths=[177, 177, 177])
        prob_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), light_bg),
            ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
            ('TOPPADDING', (0, 0), (-1, -1), 2.5),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(prob_table)

        # Build document using Custom NumberedCanvas to draw fixed page footer on EVERY page
        canvas_maker = NumberedCanvasFactory.create(verify_url)
        doc.build(story, canvasmaker=canvas_maker)
        
        pdf_data = buffer.getvalue()
        buffer.close()
        return pdf_data
