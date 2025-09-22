# --- Standard Library ---
import os
import json
import uuid
import secrets
import mimetypes
from datetime import datetime

# --- Third-Party ---
from flask import (
    Blueprint,
    request,
    jsonify,
    current_app,
    send_from_directory,
    render_template,
    session,
    Response
)
from PyPDF2 import PdfReader
from redis import Redis
from rq import Queue
from rq.job import Job

# --- Local Imports ---
from worker import (
    perform_merge,
    perform_remove_pages,
    perform_split,
    perform_contact_email,
    convert_pdf_to_images,
    perform_extract_pages,
    perform_organize_pages,
    perform_compress_pdf,
    perform_ocr_pdf,
    perform_images_to_pdf,
    perform_add_page_numbers,
    perform_rotate_pages
)

from app.wordtopdf import perform_word_to_pdf
from app.perform_ppt_to_pdf import perform_ppt_to_pdf
from app.perform_excel_to_pdf import perform_excel_to_pdf
from app.perform_html_to_pdf import perform_html_to_pdf
from app.perform_pdf_to_image import perform_pdf_to_image
from app.perform_pdf_to_word import perform_pdf_to_word
from app.perform_pdf_to_ppt import convert_pdf_to_pptx
from app.perform_pdf_to_excel import perform_pdf_to_excel
from app.perform_pdf_to_pdfa import perform_pdf_to_pdfa
from app.split_logic import split_job  # Assuming split_job exists in split_logic

# --- Optional Dependency ---
try:
    from pdf2image import convert_from_path
except ImportError:
    convert_from_path = None  # Handle missing library gracefully

# --- App Setup ---
redis_conn = Redis(host='localhost', port=6379, db=0)
q = Queue(connection=redis_conn)

main = Blueprint('main', __name__)


# --- FRONTEND PAGES ---
@main.route('/')
def home_page():
    return render_template('home.html')

@main.route('/contact-us')
def contact_page():
    return render_template('contact_us.html', title='Contact Us')

@main.route('/about-us')
def about_us():
    return render_template('about_us.html', title='About Us')

@main.route('/Privacy-policy')
def privacy_policy():
    return render_template('privacy_policy.html', title='Privacy Policy')

@main.route('/terms-of-service')
def terms_of_service():
    return render_template('terms_of_service.html', title='Terms of Service')

@main.route('/merge-pdf')
def merge_pdf_page():
    return render_template('merge.html')

@main.route('/split-pdf')
def split_pdf_page():
    return render_template('split.html')

@main.route('/remove-pages')
def remove_pdf_page():
    return render_template('remove_pages.html')

@main.route('/extract-pages')
def extract_pdf_page():
    return render_template('extract-pages.html')


@main.route('/organize-pdf')
def organize_pdf_page():
    return render_template('organize_pdf.html')


@main.route('/compress-pdf')
def compress_pdf_page():
    return render_template('compress.html')

@main.route('/ocr-pdf')
def ocr_pdf_page():
    return render_template('ocr_pdf.html')

@main.route('/jpg-to-pdf')
def jpg_to_pdf():
    return render_template('jpg_to_pdf.html')


@main.route('/word-to-pdf')
def wordto_pdf():
    return render_template('word-to-pdf.html')

@main.route('/ppt-to-pdf')
def pptto_pdf():
    return render_template('powerpoint-to-pdf.html')

@main.route('/excel-to-pdf')
def excelto_pdf():
    return render_template('excel-to-pdf.html')


@main.route('/html-to-pdf')
def htmlto_pdf():
    return render_template('html-to-pdf.html')


@main.route('/pdf-to-jpg')
def pdfto_img():
    return render_template('pdf-to-image.html')


@main.route('/pdf-to-word')
def pdfto_word():
    return render_template('pdf_to_word.html')


@main.route('/pdf-to-ppt')
def pdfto_ppt():
    return render_template('pdf-to-ppt.html')


@main.route('/pdf-to-excel')
def pdfto_excel():
    return render_template('pdf_to_excel.html')


@main.route('/pdf-to-pdfa')
def pdfto_pdfaa():
    return render_template('pdftopdfa.html')

@main.route('/add-pdf-page-numbers')
def add_page_numbers_page():
    return render_template('add_page_numbers.html')

@main.route('/rotate-pdf')
def rotate_pdf_page():
    return render_template('rotate.html')

@main.route('/add-watermark')
def add_pdf_watermark():
    return render_template('add_water_mark.html')

@main.route('/crop-pdf')
def crop_pdf():
    return render_template('crop_pdf.html')


@main.route('/edit-pdf')
def edit_pdfg():
    return render_template('edit.html')


@main.route('/protect-pdf')
def protect_pdfg():
    return render_template('protect_pdf.html')

@main.route('/unlock-pdf')
def unlock_protect_pdf():
    return render_template('unlock_pdf.html')


@main.route('/sign-pdf')
def sign_pdfs():
    return render_template('sign-pdf.html')


@main.route('/redact-pdf')
def redact_pdfs():
    return render_template('redact-pdf.html')


# ----------------------------------------------------------------------
# Upload route
# ----------------------------------------------------------------------
@main.route('/api/upload', methods=['POST'])
def upload_files():
    if 'files' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    files = request.files.getlist('files')
    if not files or files[0].filename == '':
        return jsonify({'error': 'No selected file'}), 400

    uploaded_files_data = []

    for file in files:
        if file.filename.lower().endswith('.pdf'):
            try:
                unique_filename = f"{uuid.uuid4().hex}.pdf"
                save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                file.save(save_path)

                reader = PdfReader(save_path)
                page_count = len(reader.pages)

                uploaded_files_data.append({
                    'original_name': file.filename,
                    'unique_name': unique_filename,
                    'path': save_path,
                    'pages': page_count
                })

            except Exception as e:
                return jsonify({'error': f'Failed to process file: {e}'}), 500
        else:
            return jsonify({'error': 'File type not allowed'}), 400

    return jsonify({'files': uploaded_files_data}), 200


# ----------------------------------------------------------------------
# Merge route
# ----------------------------------------------------------------------
@main.route('/api/merge', methods=['POST'])
def start_merge_job():
    data = request.json
    files_to_merge = data.get('files')
    if not files_to_merge:
        return jsonify({'error': 'No files provided for merging'}), 400

    # Pass the OUTPUT_FOLDER explicitly to the worker
    output_folder = current_app.config['OUTPUT_FOLDER']

    job = q.enqueue(
        perform_merge,
        file_data=files_to_merge,
        output_folder=output_folder,
        job_timeout='10m'
    )

    redis_conn.set(
        f'job_status:{job.id}',
        json.dumps({'status': 'queued', 'result': None})
    )

    return jsonify({'message': 'Job submitted', 'job_id': job.id}), 202

# ----------------------------------------------------------------------
# Split pdf 
# ----------------------------------------------------------------------
@main.route('/api/split', methods=['POST'])
def start_split_job():
    file_path = request.form.get('file_path')
    if not file_path:
        return jsonify({'error': 'No file path provided'}), 400

    split_option = request.form.get('split_option')
    if split_option not in ('all', 'range'):
        return jsonify({'error': 'Invalid split_option, must be "all" or "range"'}), 400

    start_page = end_page = None
    if split_option == 'range':
        try:
            start_page = int(request.form.get('start_page'))
            end_page = int(request.form.get('end_page'))
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid or missing start_page/end_page for range split'}), 400

    # Get the output folder from the application config
    output_folder = current_app.config['UPLOAD_FOLDER']

    # Pass the output_folder to the worker function as an argument
    job = q.enqueue(perform_split, file_path, split_option, output_folder, start_page, end_page, job_timeout='10m')
    redis_conn.set(f'job_status:{job.id}', json.dumps({'status': 'queued', 'result': None}))

    return jsonify({'message': 'Split job submitted', 'job_id': job.id}), 202



# ----------------------------------------------------------------------
# Generate previews
# ----------------------------------------------------------------------
@main.route('/api/remove/previews', methods=['POST'])
def generate_previews():
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    try:
        file = request.files['pdf_file']
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'File must be a PDF'}), 400

        filename = f"{uuid.uuid4().hex}.pdf"
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        file.save(file_path)

        preview_folder = current_app.config['PREVIEW_FOLDER']

        job = q.enqueue(
            convert_pdf_to_images,
            file_path,
            preview_folder,
            job_timeout='5m'
        )

        # Initialize job status in Redis
        redis_conn.set(
            f'job_status:{job.id}',
            json.dumps({'status': 'queued', 'result': None})
        )

        return jsonify({'message': 'Preview job submitted', 'job_id': job.id}), 202

    except Exception as e:
        current_app.logger.error(f"Preview generation error: {e}")
        return jsonify({'error': 'Failed to start preview job'}), 500


# ----------------------------------------------------------------------
# Remove pages
# ----------------------------------------------------------------------
@main.route('/api/remove', methods=['POST'])
def start_remove_job():
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    try:
        file = request.files['pdf_file']
        pages_str = request.form.get('selected_pages')

        if not pages_str:
            return jsonify({'error': 'No pages selected'}), 400

        pages = [int(p.strip()) for p in pages_str.split(',') if p.strip().isdigit()]
        if not pages:
            return jsonify({'error': 'Invalid page selection'}), 400

        filename = f"{uuid.uuid4().hex}.pdf"
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        file.save(file_path)

        job_input = {
            'input_path': file_path,
            'pages_to_remove': pages,
            'upload_folder': current_app.config['UPLOAD_FOLDER']
        }

        job = q.enqueue(perform_remove_pages, job_input, job_timeout='10m')
        redis_conn.set(f'job_status:{job.id}', json.dumps({'status': 'queued', 'result': None}))

        return jsonify({'message': 'Remove pages job submitted', 'job_id': job.id}), 202

    except Exception as e:
        current_app.logger.error(f"Remove job error: {e}")
        return jsonify({'error': 'Failed to start removal job'}), 500

# ----------------------------------------------------------------------
# Job status
# ----------------------------------------------------------------------
@main.route('/api/job/status/<job_id>', methods=['GET'])
def get_job_status(job_id):
    try:
        job = Job.fetch(job_id, connection=redis_conn)
    except Exception:
        return jsonify({'status': 'unknown', 'result': None, 'progress': 0}), 404

    progress = job.meta.get('progress', 0)
    job_status = job.get_status()
    result = None

    if job_status == 'finished':
        job_result = job.result
        if job_result is not None:
            if isinstance(job_result, str):
                result = job_result
            elif isinstance(job_result, list):
                # ✅ handle list of dicts (your preview case)
                result = job_result
            elif isinstance(job_result, dict):
                result = (
                    job_result.get('output_filename')
                    or job_result.get('output_pdf')
                    or job_result.get('output_excel')
                )

        # If worker didn’t return result, check Redis for partial previews
        if not result:
            preview_data = redis_conn.get(f"preview:{job_id}")
            if preview_data:
                try:
                    preview_data = json.loads(preview_data)
                    if isinstance(preview_data, dict):
                        result = preview_data.get("pages")
                    else:
                        result = preview_data
                except json.JSONDecodeError:
                    result = None

    elif job_status == 'failed':
        result = job.result

    else:
        # ✅ While job is still running, return partial previews
        preview_data = redis_conn.get(f"preview:{job_id}")
        if preview_data:
            try:
                preview_data = json.loads(preview_data)
                if isinstance(preview_data, dict):
                    result = preview_data.get("pages")
                else:
                    result = preview_data
            except json.JSONDecodeError:
                result = None

    return jsonify({
        'status': job_status,
        'result': result,
        'progress': progress
    })



# ----------------------------------------------------------------------
# Download processed file
# ----------------------------------------------------------------------
@main.route('/api/job/download/<filename>', methods=['GET'])
def download_file(filename):
    upload_folder = current_app.config['UPLOAD_FOLDER']
    output_folder = current_app.config['OUTPUT_FOLDER']

    file_path = os.path.join(upload_folder, filename)
    directory = upload_folder

    if not os.path.exists(file_path):
        # Try output folder if not found in upload folder
        file_path = os.path.join(output_folder, filename)
        directory = output_folder
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404

    mime_type, _ = mimetypes.guess_type(file_path)

    return send_from_directory(
        directory=directory,
        path=filename,
        as_attachment=True,
        mimetype=mime_type
    )

# ----------------------------------------------------------------------
# Serve preview images
# ----------------------------------------------------------------------
@main.route('/previews/<filename>')
def serve_preview(filename):
    return send_from_directory(
        directory=current_app.config['PREVIEW_FOLDER'],
        path=filename
    )


# ----------------------------------------------------------------------
# Sitemap generator
# ----------------------------------------------------------------------
@main.route('/sitemap.xml')
def sitemap():
    DOMAIN = "https://taptopdf.com"
    pages = []

    ignored_prefixes = ('/admin', '/api', '/static', '/login', '/logout')

    for rule in current_app.url_map.iter_rules():
        if "GET" in rule.methods and len(rule.arguments) == 0:
            url_path = str(rule.rule)
            if any(url_path.startswith(prefix) for prefix in ignored_prefixes):
                continue
            if url_path == '/sitemap.xml':
                continue

            url = DOMAIN + url_path
            pages.append({
                "loc": url,
                "lastmod": datetime.now().date().isoformat()
            })

    sitemap_xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    sitemap_xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for page in pages:
        sitemap_xml.append('<url>')
        sitemap_xml.append(f'<loc>{page["loc"]}</loc>')
        sitemap_xml.append(f'<lastmod>{page["lastmod"]}</lastmod>')
        sitemap_xml.append('</url>')
    sitemap_xml.append('</urlset>')

    return Response("\n".join(sitemap_xml), mimetype='application/xml')


# ----------------------------------------------------------------------
# Contact form submission
# ----------------------------------------------------------------------
@main.route('/api/contact', methods=['POST'])
def contact_submit():
    data = request.json or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    subject = (data.get("subject") or "Contact Form").strip()
    message = (data.get("message") or "").strip()

    if not name or not email or not message:
        return jsonify({"error": "name, email, and message are required"}), 400

    job_input = {
        "name": name,
        "email": email,
        "subject": subject,
        "message": message,
    }

    job = q.enqueue("worker.perform_contact_email", job_input, job_timeout="2m")

    redis_conn.set(
        f"job_status:{job.id}",
        json.dumps({"status": "queued", "result": None})
    )

    return jsonify({
        "message": "Contact request received",
        "job_id": job.id
    }), 202


# ----------------------------------------------------------------------
# Extract pages
# ----------------------------------------------------------------------
@main.route('/api/extract', methods=['POST'])
def start_extract_job():
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    try:
        file = request.files['pdf_file']
        pages_str = request.form.get('selected_pages')

        if not pages_str:
            return jsonify({'error': 'No pages selected'}), 400

        # Parse pages to extract
        pages = [int(p.strip()) for p in pages_str.split(',') if p.strip().isdigit()]
        if not pages:
            return jsonify({'error': 'Invalid page selection'}), 400

        # Save uploaded file
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        filename = f"{uuid.uuid4().hex}.pdf"
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)

        # Prepare job input
        job_input = {
            'input_path': file_path,
            'pages_to_extract': pages,
            'upload_folder': upload_folder
        }

        # Enqueue extraction job
        job = q.enqueue(perform_extract_pages, job_input, job_timeout='10m')

        return jsonify({'message': 'Extract pages job submitted', 'job_id': job.id}), 202

    except Exception as e:
        current_app.logger.error(f"Extract job error: {e}")
        return jsonify({'error': 'Failed to start extraction job'}), 500

# ----------------------------------------------------------------------
# Organize pages (reorder, rotate)
# ----------------------------------------------------------------------

@main.route('/api/organize', methods=['POST'])
def start_organize_job():
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    try:
        file = request.files['pdf_file']
        order_str = request.form.get('order')
        rotations_str = request.form.get('rotations')

        if not order_str:
            return jsonify({'error': 'No page order provided'}), 400

        # Parse order and rotations
        order = [int(p.strip()) for p in order_str.split(',') if p.strip().isdigit()]
        rotations = json.loads(rotations_str) if rotations_str else {}

        # Save uploaded file
        filename = f"{uuid.uuid4().hex}.pdf"
        upload_folder = current_app.config['UPLOAD_FOLDER']
        file_path = os.path.join(upload_folder, filename)
        os.makedirs(upload_folder, exist_ok=True)
        file.save(file_path)

        job_input = {
            'input_path': file_path,
            'order': order,
            'rotations': rotations,
            'upload_folder': upload_folder
        }

        job = q.enqueue(perform_organize_pages, job_input, job_timeout='15m')
        redis_conn.set(f'job_status:{job.id}', json.dumps({'status': 'queued', 'result': None}))

        return jsonify({'message': 'Organize pages job submitted', 'job_id': job.id}), 202

    except Exception as e:
        current_app.logger.error(f"Organize job error: {e}")
        return jsonify({'error': 'Failed to start organize job'}), 500
    

# ----------------------------------------------------------------------
# Compress PDF
# ----------------------------------------------------------------------
@main.route('/api/compress', methods=['POST'])
def start_compress_job():
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    try:
        file = request.files['pdf_file']
        level = request.form.get('level', 'recommended').lower().strip()

        if level not in ['extreme', 'recommended', 'less']:
            return jsonify({'error': 'Invalid compression level'}), 400

        # Save the uploaded PDF
        filename = f"{uuid.uuid4().hex}.pdf"
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        file.save(file_path)

        gs_path = current_app.config.get('GHOSTSCRIPT_PATH', 'gs')  # default 'gs'

        job_input = {
            "input_path": file_path,
            "level": level,
            "upload_folder": current_app.config['UPLOAD_FOLDER'],  # pass folder explicitly
            "gs_path": gs_path
        }

        job = q.enqueue(perform_compress_pdf, job_input, job_timeout='10m')
        redis_conn.set(f"job_status:{job.id}", json.dumps({"status": "queued", "result": None}))

        return jsonify({"message": "Compression job submitted", "job_id": job.id}), 202

    except Exception as e:
        current_app.logger.exception("Failed to start compression job")
        return jsonify({'error': 'Compression job failed'}), 500

# ----------------------------------------------------------------------
# OCR PDF
# ----------------------------------------------------------------------
@main.route('/api/ocr', methods=['POST'])
def start_ocr_job():
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    try:
        file = request.files['pdf_file']

        # Save the uploaded PDF
        filename = f"{uuid.uuid4().hex}.pdf"
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        file.save(file_path)

        job_input = {
            "input_path": file_path,
            "upload_folder": current_app.config['UPLOAD_FOLDER'],
            "output_folder": current_app.config['OUTPUT_FOLDER']  # ✅ Pass output folder
        }

        job = q.enqueue(perform_ocr_pdf, job_input, job_timeout='10m')
        redis_conn.set(f"job_status:{job.id}", json.dumps({"status": "queued", "result": None}))

        return jsonify({"message": "OCR job submitted", "job_id": job.id}), 202

    except Exception as e:
        current_app.logger.exception("Failed to start OCR job")
        return jsonify({'error': 'OCR job failed'}), 500

# ----------------------------------------------------------------------
# Images → PDF
# ----------------------------------------------------------------------
@main.route('/api/images-to-pdf', methods=['POST'])
def start_images_to_pdf_job():
    if 'image_files' not in request.files:
        return jsonify({'error': 'No images uploaded'}), 400

    images = request.files.getlist('image_files')
    rotations = request.form.getlist('rotations[]')  # e.g. ['90', '180', '0']
    orientation = request.form.get('orientation', 'P')

    if len(images) != len(rotations):
        return jsonify({'error': 'Mismatch between number of images and rotations'}), 400

    image_data = []
    upload_folder = current_app.config['UPLOAD_FOLDER']

    os.makedirs(upload_folder, exist_ok=True)

    for image, rotation in zip(images, rotations):
        ext = os.path.splitext(image.filename)[1]
        filename = f"{uuid.uuid4().hex}{ext}"
        save_path = os.path.join(upload_folder, filename)
        image.save(save_path)

        image_data.append({
            "path": save_path,
            "rotation": int(rotation) if rotation.isdigit() else 0
        })

    output_pdf_filename = f"{uuid.uuid4().hex}.pdf"
    output_pdf_path = os.path.join(upload_folder, output_pdf_filename)

    job = q.enqueue(
        perform_images_to_pdf,
        image_data,
        output_pdf_path,
        orientation,
        job_timeout='10m'
    )

    redis_conn.set(f'job_status:{job.id}', json.dumps({'status': 'queued', 'result': None}))

    return jsonify({
        'message': 'Job submitted',
        'job_id': job.id,
        'output_pdf': output_pdf_filename
    }), 202


# ----------------------------------------------------------------------
# Word → PDF (synchronous, Ubuntu-friendly using LibreOffice)
# ----------------------------------------------------------------------


@main.route('/api/word-to-pdf', methods=['POST'])
def word_to_pdf():
    if 'word_file' not in request.files:
        return jsonify({'error': 'No Word file uploaded'}), 400

    word_file = request.files['word_file']

    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)

    # Save input Word file
    input_filename = f"{uuid.uuid4().hex}.docx"
    input_path = os.path.join(upload_folder, input_filename)
    word_file.save(input_path)

    # Prepare output PDF file
    output_filename = f"{uuid.uuid4().hex}.pdf"
    output_path = os.path.join(upload_folder, output_filename)

    # Enqueue worker job (LibreOffice will handle conversion)
    job = q.enqueue(
        perform_word_to_pdf,
        input_path,
        output_path,
        job_timeout='5m'
    )

    redis_conn.set(
        f'job_status:{job.id}',
        json.dumps({'status': 'queued', 'result': None})
    )

    return jsonify({
        'message': 'Job submitted',
        'job_id': job.id,
        'output_pdf': output_filename
    }), 202


# ----------------------------------------------------------------------
# PPT → PDF
# ----------------------------------------------------------------------
@main.route('/api/ppt-to-pdf', methods=['POST'])
def ppt_to_pdf():
    if 'ppt_file' not in request.files:
        return jsonify({'error': 'No PowerPoint file uploaded'}), 400

    ppt_file = request.files['ppt_file']

    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)

    filename = f"{uuid.uuid4().hex}.pptx"
    saved_path = os.path.join(upload_folder, filename)
    ppt_file.save(saved_path)

    output_pdf = f"{uuid.uuid4().hex}.pdf"
    output_pdf_path = os.path.join(upload_folder, output_pdf)

    job = q.enqueue(
        perform_ppt_to_pdf,
        saved_path,
        output_pdf_path,
        job_timeout='10m'
    )

    redis_conn.set(f'job_status:{job.id}', json.dumps({'status': 'queued', 'result': None}))

    return jsonify({'job_id': job.id, 'output_pdf': output_pdf}), 202


# ----------------------------------------------------------------------
# Excel → PDF
# ----------------------------------------------------------------------
@main.route('/api/excel-to-pdf', methods=['POST'])
def excel_to_pdf():
    if 'excel_file' not in request.files:
        return jsonify({'error': 'No Excel file uploaded'}), 400

    excel_file = request.files['excel_file']

    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)

    filename = f"{uuid.uuid4().hex}.xlsx"
    saved_path = os.path.join(upload_folder, filename)
    excel_file.save(saved_path)

    output_pdf = f"{uuid.uuid4().hex}.pdf"
    output_pdf_path = os.path.join(upload_folder, output_pdf)

    job = q.enqueue(
        perform_excel_to_pdf,
        saved_path,
        output_pdf_path,
        job_timeout='10m'
    )

    redis_conn.set(f'job_status:{job.id}', json.dumps({'status': 'queued', 'result': None}))

    return jsonify({'job_id': job.id, 'output_pdf': output_pdf}), 202


# ----------------------------------------------------------------------
# HTML → PDF
# ----------------------------------------------------------------------
@main.route('/api/html-to-pdf', methods=['POST'])
def html_to_pdf():
    html_content = request.form.get('html_content')
    html_file = request.files.get('html_file')

    if not html_content and not html_file:
        return jsonify({'error': 'No HTML content or file provided'}), 400

    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)

    output_pdf = f"{uuid.uuid4().hex}.pdf"
    out_path = os.path.join(upload_folder, output_pdf)

    if html_file:
        html_path = os.path.join(upload_folder, f"{uuid.uuid4().hex}.html")
        html_file.save(html_path)
        job = q.enqueue(perform_html_to_pdf, None, html_path, out_path, job_timeout="5m")
    else:
        job = q.enqueue(perform_html_to_pdf, html_content, None, out_path, job_timeout="5m")

    redis_conn.set(f'job_status:{job.id}', json.dumps({'status': 'queued', 'result': None}))

    return jsonify({'job_id': job.id, 'output_pdf': output_pdf}), 202


# ----------------------------------------------------------------------
# PDF → Images
# ----------------------------------------------------------------------
@main.route('/api/pdf-to-image', methods=['POST'])
def pdf_to_image():
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'No PDF file uploaded'}), 400

    pdf_file = request.files['pdf_file']
    filename = f"{uuid.uuid4().hex}.pdf"

    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)

    pdf_path = os.path.join(upload_folder, filename)
    pdf_file.save(pdf_path)

    output_folder = os.path.join(upload_folder, f"{uuid.uuid4().hex}_images")
    os.makedirs(output_folder, exist_ok=True)

    job = q.enqueue(
        perform_pdf_to_image,
        pdf_path,
        output_folder,
        job_timeout="10m"
    )

    redis_conn.set(f'job_status:{job.id}', json.dumps({'status': 'queued', 'result': None}))

    return jsonify({'job_id': job.id, 'output_folder': os.path.basename(output_folder)}), 202


# ----------------------------------------------------------------------
# PDF → Word
# ----------------------------------------------------------------------
@main.route('/api/pdf-to-word', methods=['POST'])
def pdf_to_word():
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'No PDF file uploaded'}), 400

    pdf_file = request.files['pdf_file']
    filename = f"{uuid.uuid4().hex}.pdf"

    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)

    saved_path = os.path.join(upload_folder, filename)
    pdf_file.save(saved_path)

    output_docx = f"{uuid.uuid4().hex}.docx"
    output_docx_path = os.path.join(upload_folder, output_docx)

    job = q.enqueue(
        perform_pdf_to_word,
        saved_path,
        output_docx_path,
        job_timeout='10m'
    )

    redis_conn.set(f'job_status:{job.id}', json.dumps({'status': 'queued', 'result': None}))

    return jsonify({'job_id': job.id, 'output_docx': output_docx}), 202


# ----------------------------------------------------------------------
# PDF → PPT
# ----------------------------------------------------------------------
@main.route('/api/pdf-to-ppt', methods=['POST'])
def pdf_to_ppt():
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'No PDF uploaded'}), 400

    pdf_file = request.files['pdf_file']
    if pdf_file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400

    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)

    pdf_filename = f"{uuid.uuid4().hex}.pdf"
    pdf_path = os.path.join(upload_folder, pdf_filename)
    pdf_file.save(pdf_path)

    ppt_filename = f"{uuid.uuid4().hex}.pptx"
    ppt_path = os.path.join(upload_folder, ppt_filename)

    job = q.enqueue(
        convert_pdf_to_pptx,
        pdf_path,
        ppt_path,
        job_timeout='10m'
    )

    redis_conn.set(f'job_status:{job.id}', json.dumps({'status': 'queued', 'result': None}))

    return jsonify({'job_id': job.id, 'output_ppt': ppt_filename}), 202


# ----------------------------------------------------------------------
# PDF → Excel
# ----------------------------------------------------------------------
@main.route('/api/pdf-to-excel', methods=['POST'])
def pdf_to_excel():
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'No PDF file uploaded'}), 400

    pdf_file = request.files['pdf_file']
    filename = f"{uuid.uuid4().hex}.pdf"

    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)

    pdf_path = os.path.join(upload_folder, filename)
    pdf_file.save(pdf_path)

    output_xlsx = f"{uuid.uuid4().hex}.xlsx"
    output_xlsx_path = os.path.join(upload_folder, output_xlsx)

    job = q.enqueue(
        perform_pdf_to_excel,
        pdf_path,
        output_xlsx_path,
        job_timeout="10m"
    )

    redis_conn.set(f'job_status:{job.id}', json.dumps({"status": "queued", "result": None}))

    return jsonify({
        "message": "PDF → Excel job submitted",
        "job_id": job.id,
        "output_excel": output_xlsx
    }), 202


# ----------------------------------------------------------------------
# PDF → PDF/A
# ----------------------------------------------------------------------
@main.route('/api/pdf-to-pdfa', methods=['POST'])
def pdf_to_pdfa():
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'No PDF file uploaded'}), 400

    pdf_file = request.files['pdf_file']
    filename = f"{uuid.uuid4().hex}.pdf"

    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)

    saved_path = os.path.join(upload_folder, filename)
    pdf_file.save(saved_path)

    # Read selection from form; default to 1b if missing/invalid
    pdfa_level = (request.form.get('pdfa_level') or '1b').lower()
    if pdfa_level not in {'1a','1b','2a','2b','3a','3b'}:
        pdfa_level = '1b'

    job_input = {
        "input_path": saved_path,
        "upload_folder": upload_folder,
        "pdfa_level": pdfa_level
    }

    job = q.enqueue(
        perform_pdf_to_pdfa,
        job_input,
        job_timeout='10m'
    )

    redis_conn.set(
        f"job_status:{job.id}",
        json.dumps({"status": "queued", "result": None})
    )

    return jsonify({'job_id': job.id}), 202


# ----------------------------------------------------------------------
# Add Page Numbers
# ----------------------------------------------------------------------
@main.route('/api/add-page-numbers', methods=['POST'])
def start_add_page_numbers_job():
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['pdf_file']
    position = request.form.get('position', 'bottom-center')

    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Uploaded file must be a PDF'}), 400

    if position not in [
        'top-left', 'top-center', 'top-right',
        'bottom-left', 'bottom-center', 'bottom-right'
    ]:
        return jsonify({'error': 'Invalid position for page numbers'}), 400

    try:
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)

        filename = f"{uuid.uuid4().hex}.pdf"
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)

        # Pass upload_folder explicitly to worker
        job_input = {
            'input_path': file_path,
            'position': position,
            'upload_folder': upload_folder
        }

        job = q.enqueue(perform_add_page_numbers, job_input, job_timeout='10m')
        redis_conn.set(f"job_status:{job.id}", json.dumps({"status": "queued", "result": None}))

        return jsonify({
            "message": "Add page numbers job submitted",
            "job_id": job.id,
            "output_filename": filename
        }), 202

    except Exception as e:
        current_app.logger.exception("Failed to start add-page-numbers job")
        return jsonify({'error': 'Job failed to start'}), 500

# ----------------------------------------------------------------------
# Preview First Page
# ----------------------------------------------------------------------
@main.route('/api/preview-first-page', methods=['POST'])
def preview_first_page():
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['pdf_file']
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'File must be a PDF'}), 400

    try:
        upload_folder = current_app.config['UPLOAD_FOLDER']
        preview_folder = current_app.config['PREVIEW_FOLDER']

        os.makedirs(upload_folder, exist_ok=True)
        os.makedirs(preview_folder, exist_ok=True)

        filename = f"{uuid.uuid4().hex}.pdf"
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)

        # Generate preview image from first page
        images = convert_from_path(file_path, first_page=1, last_page=1, fmt='jpeg')

        preview_filename = f"{filename}.jpg"
        preview_image_path = os.path.join(preview_folder, preview_filename)
        images[0].save(preview_image_path, 'JPEG')

        preview_url = f"/previews/{preview_filename}"
        return jsonify({'preview_url': preview_url})

    except Exception as e:
        current_app.logger.exception("Preview generation failed")
        return jsonify({'error': 'Failed to generate preview'}), 500


# ----------------------------------------------------------------------
# Rotate Pages
# ----------------------------------------------------------------------
@main.route('/api/rotate', methods=['POST'])
def start_rotate_job():
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    try:
        file = request.files['pdf_file']
        rotations_str = request.form.get('rotations')
        order_str = request.form.get('order')

        rotations = json.loads(rotations_str) if rotations_str else {}
        order = [int(i) for i in order_str.split(',')] if order_str else []

        # Pass the upload folder explicitly
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)

        filename = f"{uuid.uuid4().hex}.pdf"
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)

        job_input = {
            'input_path': file_path,
            'rotations': rotations,
            'order': order,
            'upload_folder': upload_folder  # pass explicitly
        }

        job = q.enqueue(perform_rotate_pages, job_input, job_timeout='10m')
        redis_conn.set(f'job_status:{job.id}', json.dumps({'status': 'queued', 'result': None}))

        return jsonify({
            'message': 'Rotate pages job submitted',
            'job_id': job.id,
            'output_filename': filename
        }), 202

    except Exception as e:
        current_app.logger.error(f"Rotate job error: {e}")
        return jsonify({'error': 'Failed to start rotate job'}), 500


# # ----------------------------------------------------------------------
# # Add Text Watermark
# # ----------------------------------------------------------------------
# from worker import perform_add_text_watermark
# @main.route('/api/add-text-watermark', methods=['POST'])
# def start_add_text_watermark_job():
#     if 'pdf_file' not in request.files:
#         return jsonify({'error': 'PDF file is required'}), 400

#     pdf_file = request.files['pdf_file']
#     text = request.form.get('text', 'Watermark')
#     position = request.form.get('position', 'center')
#     angle = float(request.form.get('angle', 0))
#     opacity = float(request.form.get('opacity', 0.3))

#     if not pdf_file.filename.lower().endswith('.pdf'):
#         return jsonify({'error': 'Uploaded file must be a PDF'}), 400

#     try:
#         upload_folder = current_app.config['UPLOAD_FOLDER']
#         os.makedirs(upload_folder, exist_ok=True)

#         filename = f"{uuid.uuid4().hex}.pdf"
#         file_path = os.path.join(upload_folder, filename)
#         pdf_file.save(file_path)

#         job_input = {
#             'input_path': file_path,
#             'text': text,
#             'position': position,
#             'angle': angle,
#             'opacity': opacity,
#             'upload_folder': upload_folder
#         }

#         job = q.enqueue(perform_add_text_watermark, job_input, job_timeout='10m')
#         redis_conn.set(f"job_status:{job.id}", json.dumps({"status": "queued", "result": None}))

#         return jsonify({
#             "message": "Text watermark job submitted",
#             "job_id": job.id,
#             "output_filename": filename
#         }), 202

#     except Exception as e:
#         current_app.logger.exception("Failed to start text watermark job")
#         return jsonify({'error': 'Job failed to start'}), 500


# ----------------------------------------------------------------------
# Crop PDF
# ----------------------------------------------------------------------
from worker import perform_crop_pdf_rect
@main.route('/api/crop-pdf-rect', methods=['POST'])
def start_crop_pdf_rect():
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    pdf_file = request.files['pdf_file']
    coords = request.form.get('coords')  # JSON: {x, y, width, height}
    
    if not pdf_file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Uploaded file must be a PDF'}), 400

    if not coords:
        return jsonify({'error': 'Crop rectangle not provided'}), 400

    coords = json.loads(coords)

    try:
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        filename = f"{uuid.uuid4().hex}.pdf"
        file_path = os.path.join(upload_folder, filename)
        pdf_file.save(file_path)

        job_input = {
            'input_path': file_path,
            'coords': coords,
            'upload_folder': upload_folder
        }

        job = q.enqueue(perform_crop_pdf_rect, job_input, job_timeout='10m')
        redis_conn.set(f"job_status:{job.id}", json.dumps({"status": "queued", "result": None}))

        return jsonify({"message": "Crop job submitted", "job_id": job.id, "output_filename": filename}), 202

    except Exception as e:
        current_app.logger.exception("Failed to start crop-pdf-rect job")
        return jsonify({'error': 'Job failed to start'}), 500


# routes.py
from worker import perform_edit_pdf_text

@main.route('/api/edit-pdf-text', methods=['POST'])
def start_edit_pdf_text():
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    pdf_file = request.files['pdf_file']
    edits_json = request.form.get('edits')  # JSON: [{page, old_text, new_text}, ...]

    if not pdf_file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Uploaded file must be a PDF'}), 400

    if not edits_json:
        return jsonify({'error': 'No edits provided'}), 400

    edits = json.loads(edits_json)

    try:
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        filename = f"{uuid.uuid4().hex}.pdf"
        file_path = os.path.join(upload_folder, filename)
        pdf_file.save(file_path)

        job_input = {
            'input_path': file_path,
            'edits': edits,
            'upload_folder': upload_folder
        }

        job = q.enqueue(perform_edit_pdf_text, job_input, job_timeout='10m')
        redis_conn.set(f"job_status:{job.id}", json.dumps({"status": "queued", "result": None}))

        return jsonify({"message": "Edit job submitted", "job_id": job.id, "output_filename": filename}), 202

    except Exception as e:
        current_app.logger.exception("Failed to start edit-pdf-text job")
        return jsonify({'error': 'Job failed to start'}), 500

# ----------------------------------------------------------------------
# Password Protect PDF
# ----------------------------------------------------------------------
from worker import perform_password_protect
@main.route('/api/protect-pdf', methods=['POST'])
def start_password_protect_job():
    if 'pdf_file' not in request.files or 'password' not in request.form:
        return jsonify({'error': 'PDF file and password are required'}), 400

    pdf_file = request.files['pdf_file']
    password = request.form.get('password')

    if not pdf_file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Uploaded file must be a PDF'}), 400

    try:
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)

        filename = f"{uuid.uuid4().hex}.pdf"
        file_path = os.path.join(upload_folder, filename)
        pdf_file.save(file_path)

        job_input = {
            'input_path': file_path,
            'password': password,
            'upload_folder': upload_folder
        }

        job = q.enqueue(perform_password_protect, job_input, job_timeout='10m')
        redis_conn.set(f"job_status:{job.id}", json.dumps({"status": "queued", "result": None}))

        return jsonify({
            "message": "PDF protection job submitted",
            "job_id": job.id,
            "output_filename": filename
        }), 202

    except Exception as e:
        current_app.logger.exception("Failed to start password protection job")
        return jsonify({'error': 'Job failed to start'}), 500


# ----------------------------------------------------------------------
# unlock Password Protected PDF
# ----------------------------------------------------------------------
from worker import perform_unlock_pdf  # You implement this
@main.route('/api/check-pdf-lock', methods=['POST'])
def check_pdf_lock():
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'PDF file is required'}), 400

    pdf_file = request.files['pdf_file']

    if not pdf_file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Uploaded file must be a PDF'}), 400

    try:
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)

        filename = f"{uuid.uuid4().hex}.pdf"
        file_path = os.path.join(upload_folder, filename)
        pdf_file.save(file_path)

        reader = PdfReader(file_path)
        if reader.is_encrypted:
            return jsonify({'message': 'File is password protected.', 'requires_password': True, 'temp_file': filename}), 200
        else:
            return jsonify({'message': 'File is not password protected.'}), 200

    except Exception as e:
        current_app.logger.exception("Error checking PDF lock")
        return jsonify({'error': 'Failed to check PDF'}), 500


@main.route('/api/unlock-pdf', methods=['POST'])
def start_unlock_pdf_job():
    password = request.form.get('password')
    temp_filename = request.form.get('temp_file')

    if not temp_filename or not password:
        return jsonify({'error': 'Password and temp_file are required'}), 400

    upload_folder = current_app.config['UPLOAD_FOLDER']
    file_path = os.path.join(upload_folder, temp_filename)

    if not os.path.exists(file_path):
        return jsonify({'error': 'Uploaded PDF not found'}), 404

    try:
        reader = PdfReader(file_path)
        decrypt_result = reader.decrypt(password)

        if not decrypt_result:
            return jsonify({'error': 'Incorrect password'}), 403

        job_input = {
            'input_path': file_path,
            'password': password,
            'upload_folder': upload_folder
        }

        job = q.enqueue(perform_unlock_pdf, job_input, job_timeout='10m')
        redis_conn.set(f"job_status:{job.id}", json.dumps({"status": "queued", "result": None}))

        return jsonify({
            "message": "PDF unlock job submitted",
            "job_id": job.id
        }), 202

    except Exception as e:
        current_app.logger.exception("Failed to start unlock PDF job")
        return jsonify({'error': 'Job failed to start'}), 500


# ----------------------------------------------------------------------
# edit  PDF
# ----------------------------------------------------------------------

from app.edit import apply_signatures


@main.route("/api/pdf/<filename>", methods=["GET"])
def preview_pdf(filename):
    upload_folder = current_app.config['UPLOAD_FOLDER']
    output_folder = current_app.config['OUTPUT_FOLDER']
    file_path = os.path.join(upload_folder, filename)
    directory = upload_folder
    if not os.path.exists(file_path):
        file_path = os.path.join(output_folder, filename)
        directory = output_folder
        if not os.path.exists(file_path):
            return jsonify({"error": "File not found"}), 404
    return send_from_directory(directory=directory, path=filename, as_attachment=True)

@main.route('/api/pdf/sign/merge', methods=['POST'])
def sign_pdf_merge():
    try:
        data = request.get_json()
        pdf_filename = data.get("pdf_filename")
        placements = data.get("placements", [])

        if not pdf_filename or not placements:
            return jsonify({"error": "Missing pdf_filename or placements"}), 400

        input_path = os.path.join(current_app.config["UPLOAD_FOLDER"], pdf_filename)
        if not os.path.exists(input_path):
            return jsonify({"error": "PDF file not found"}), 404

        output_folder = current_app.config["OUTPUT_FOLDER"]
        os.makedirs(output_folder, exist_ok=True)

        # Enqueue job
        job = q.enqueue(
            apply_signatures,
            input_path, output_folder, placements,
            job_timeout="5m"
        )

        # Set initial job status
        redis_conn.set(f"job_status:{job.id}", json.dumps({"status": "queued", "result": None}))

        return jsonify({"message": "Signature job submitted", "job_id": job.id}), 202

    except Exception as e:
        current_app.logger.exception(f"Failed to enqueue PDF signature job: {e}")
        return jsonify({"error": str(e)}), 500



# ----------------------------------------------------------------------
# edit  PDF
# ----------------------------------------------------------------------
from worker import apply_signatures


@main.route('/api/pdf/sign-merge', methods=['POST'])
def sign_pdf_mergee():
    try:
        data = request.get_json()
        pdf_filename = data.get("pdf_filename")
        placements = data.get("placements", [])
        if not pdf_filename or not placements:
            return jsonify({'error': 'Missing pdf_filename or placements'}), 400

        input_path = os.path.join(current_app.config['UPLOAD_FOLDER'], pdf_filename)
        if not os.path.exists(input_path):
            return jsonify({'error': 'PDF file not found'}), 404

        output_folder = current_app.config['OUTPUT_FOLDER']
        os.makedirs(output_folder, exist_ok=True)

        job = q.enqueue(
            apply_signatures,
            input_path, output_folder, placements,
            job_timeout='5m'
        )

        redis_conn.set(f'job_status:{job.id}', json.dumps({'status':'queued','result':None}))
        return jsonify({'message': 'Signature job submitted', 'job_id': job.id}), 202

    except Exception as e:
        current_app.logger.error(f"Error in sign_pdf_merge: {e}")
        return jsonify({'error': 'Failed to start signature job'}), 500


# ----------------------------------------------------------------------
# Redact PDF API
# ----------------------------------------------------------------------
from worker import redact_pdf_job

@main.route('/api/pdf/redact', methods=['POST'])
def start_redact_pdf():
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    pdf_file = request.files['pdf_file']
    if not pdf_file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Uploaded file must be a PDF'}), 400

    redactions = request.form.get('redactions')  # JSON array
    if not redactions:
        return jsonify({'error': 'Redaction rectangles not provided'}), 400

    redactions = json.loads(redactions)

    try:
        upload_folder = current_app.config['UPLOAD_FOLDER']
        output_folder = current_app.config['OUTPUT_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        os.makedirs(output_folder, exist_ok=True)

        filename = f"{uuid.uuid4().hex}.pdf"
        input_path = os.path.join(upload_folder, filename)
        pdf_file.save(input_path)

        job_input = {
            "input_path": input_path,
            "redactions": redactions,
            "output_folder": output_folder
        }

        job = q.enqueue(redact_pdf_job, job_input, job_timeout='10m')
        redis_conn.set(f"job_status:{job.id}", json.dumps({"status": "queued", "result": None}))

        return jsonify({
            "message": "Redaction job submitted",
            "job_id": job.id,
            "output_filename": filename
        }), 202

    except Exception as e:
        current_app.logger.exception("Failed to start redact PDF job")
        return jsonify({'error': 'Job failed to start'}), 500



# ----------------------------------------------------------------------
# Add Text Watermark API
# ----------------------------------------------------------------------
from app.watermark import perform_add_text_watermark

@main.route('/api/add-text-watermark', methods=['POST'])
def start_add_text_watermark_job():
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'PDF file is required'}), 400

    pdf_file = request.files['pdf_file']
    if not pdf_file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Uploaded file must be a PDF'}), 400

    # --- Extract form fields ---
    text = request.form.get('text', 'Watermark')
    # Do NOT cast to float or int here, let the worker handle it
    angle = request.form.get('angle', '45')
    opacity = request.form.get('opacity', '0.3')
    size = request.form.get('size', '28')
    position = request.form.get('position', 'center')
    x = request.form.get('x')
    y = request.form.get('y')
    page_option = request.form.get('page_option', 'all')
    specific_pages = request.form.get('specific_pages', '')

    # --- Safe parsing helpers ---
    def safe_float(val):
        if not val:
            return None
        try:
            return float(str(val).replace("px", "").strip())
        except ValueError:
            return None

    try:
        # --- Save uploaded file ---
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)

        filename = f"{uuid.uuid4().hex}.pdf"
        file_path = os.path.join(upload_folder, filename)
        pdf_file.save(file_path)

        # --- Prepare job input ---
        job_input = {
            'input_path': file_path,
            'text': text,
            'angle': angle,
            'opacity': opacity,
            'size': size,
            'position': position,
            'x': safe_float(x),
            'y': safe_float(y),
            'page_option': page_option,
            'specific_pages': specific_pages,
            'upload_folder': upload_folder
        }

        # --- Enqueue job ---
        job = q.enqueue(perform_add_text_watermark, job_input, job_timeout='10m')
        redis_conn.set(
            f"job_status:{job.id}",
            json.dumps({"status": "queued", "result": None})
        )

        return jsonify({
            "message": "Text watermark job submitted",
            "job_id": job.id,
            "output_filename": filename
        }), 202

    except Exception as e:
        current_app.logger.exception("Failed to start text watermark job")
        return jsonify({'error': 'Job failed to start'}), 500
