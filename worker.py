# worker.py

# --- Standard Library ---
import os
import uuid
import json
import logging
from io import BytesIO

# --- Third-Party ---
import fitz  # PyMuPDF
import redis
import subprocess
from redis import Redis
from rq import Worker, Queue, get_current_job
from flask import current_app
from flask_mail import Message
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import black, red, blue, green

# --- Local Imports ---
from app import create_app, mail
from app.split_logic import split_job
from app.merge_logic import handle_merge
from app.remove_logic import remove_pdf_pages
from app.extract_logic import extract_pdf_pages
from app.organize_logic import organize_pdf
from app.compress_logic import compress_pdf
from app.ocr_logic import ocr_pdf
from app.imagetopdf import convert_image_to_pdf
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Redis / Queue ---
redis_conn = Redis(host="localhost", port=6379, db=0)
q = Queue("default", connection=redis_conn)

# ----------------------------------------------------------------------
# Contact Email Job
# ----------------------------------------------------------------------
def perform_contact_email(job_input):
    job = get_current_job()
    try:
        app = create_app()
        with app.app_context():
            msg = Message(
                subject=f"[Contact] {job_input.get('subject')}",
                sender=job_input.get("email"),
                recipients=[current_app.config["MAIL_DEFAULT_SENDER"]],
                body=f"""
You have received a new contact form submission.

Name: {job_input.get("name")}
Email: {job_input.get("email")}
Subject: {job_input.get("subject")}

Message:
{job_input.get("message")}
"""
            )
            mail.send(msg)

        result = {"status": "completed", "result": "Contact email sent successfully"}
        redis_conn.set(f"job_status:{job.id}", json.dumps(result))
        return result
    except Exception as e:
        logger.exception("Failed to send contact email")
        result = {"status": "failed", "result": str(e)}
        redis_conn.set(f"job_status:{job.id}", json.dumps(result))
        raise

# ----------------------------------------------------------------------
# PDF Preview (convert to images)
# ----------------------------------------------------------------------
from concurrent.futures import ThreadPoolExecutor, as_completed

def convert_pdf_to_images(pdf_path, preview_folder, max_workers=4):
    """
    Convert PDF to PNG previews, save them, and return a structured list.
    """
    r = redis.Redis(host="localhost", port=6379, db=0)
    os.makedirs(preview_folder, exist_ok=True)
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    job = get_current_job()
    job_id = job.id
    saved_images = [None] * total_pages

    def process_page(page_num):
        page = doc.load_page(page_num)
        pix = page.get_pixmap(dpi=72)  # better quality than 32
        image_filename = f"page_{page_num + 1}.png"
        output_path = os.path.join(preview_folder, image_filename)
        pix.save(output_path)
        return page_num, image_filename

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_page, i): i for i in range(total_pages)}
        for count, future in enumerate(as_completed(futures), start=1):
            page_num, image_filename = future.result()
            saved_images[page_num] = {"page": page_num + 1, "filename": image_filename}

            # Push partial progress to Redis
            r.set(f"preview:{job_id}", json.dumps({
                "progress": int((count / total_pages) * 100),
                "pages": [img for img in saved_images if img]
            }))

            if job:
                job.meta["progress"] = int((count / total_pages) * 100)
                job.save_meta()

    return saved_images

from datetime import datetime

# ----------------------------------------------------------------------
# PDF merge Functions
# ----------------------------------------------------------------------
def perform_merge(file_data, output_folder):
    """
    Merge multiple PDFs page by page with progress updates for large files.
    output_folder: the folder to save merged PDF
    """
    job = get_current_job()
    job.meta['progress'] = 0
    job.save_meta()

    try:
        os.makedirs(output_folder, exist_ok=True)

        # Use professional, timestamped naming
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
        merged_filename = f"taptopdf_merged_{timestamp}.pdf"
        merged_filepath = os.path.join(output_folder, merged_filename)

        writer = PdfWriter()
        total_pages = sum(len(PdfReader(f['path']).pages) for f in file_data)
        current_page = 0

        for f in file_data:
            reader = PdfReader(f['path'])
            for page in reader.pages:
                writer.add_page(page)
                current_page += 1
                job.meta['progress'] = int((current_page / total_pages) * 100)
                job.save_meta()

        with open(merged_filepath, 'wb') as f_out:
            writer.write(f_out)

        job.meta['progress'] = 100
        job.meta['result'] = merged_filename
        job.save_meta()

        return merged_filename

    except Exception as e:
        job.meta['progress'] = 0
        job.meta['result'] = str(e)
        job.save_meta()
        raise



def perform_remove_pages(job_input):
    job = get_current_job()
    try:
        output_filename = f"modified_{uuid.uuid4().hex}.pdf"
        upload_folder = job_input["upload_folder"]  # 👈 always passed now
        output_path = os.path.join(upload_folder, output_filename)

        remove_pdf_pages(
            input_path=job_input["input_path"],
            pages_to_remove=job_input.get("pages_to_remove", []),
            output_path=output_path,
            download=False,
        )

        job.connection.set(
            f"job_status:{job.id}",
            json.dumps({"status": "completed", "result": output_filename})
        )
        return output_filename
    except Exception as e:
        job.connection.set(
            f"job_status:{job.id}",
            json.dumps({"status": "failed", "result": str(e)})
        )
        raise

def perform_extract_pages(job_input):
    from app.extract_logic import extract_pdf_pages
    job = get_current_job()
    try:
        input_path = job_input['input_path']
        pages_to_extract = job_input['pages_to_extract']
        upload_folder = job_input['upload_folder']

        output_filename = f"extracted_{uuid.uuid4().hex}.pdf"
        output_path = os.path.join(upload_folder, output_filename)

        # Perform the extraction
        extract_pdf_pages(input_path, pages_to_extract, output_path)

        # Return the output filename as the job result
        return output_filename

    except Exception as e:
        # Raise the exception so RQ marks job as failed
        raise


def perform_organize_pages(job_input):
    job = get_current_job()
    try:
        input_path = job_input["input_path"]
        order = job_input["order"]
        rotations = {int(k): v for k, v in job_input.get("rotations", {}).items()}
        upload_folder = job_input['upload_folder']

        output_filename = f"organized_{uuid.uuid4().hex}.pdf"
        output_path = os.path.join(upload_folder, output_filename)
        os.makedirs(upload_folder, exist_ok=True)

        reader = PdfReader(input_path)
        writer = PdfWriter()

        for page_num in order:
            if 1 <= page_num <= len(reader.pages):
                page = reader.pages[page_num - 1]
                rotation_deg = rotations.get(page_num, 0)
                if rotation_deg:
                    page.rotate(rotation_deg)
                writer.add_page(page)

        with open(output_path, "wb") as f_out:
            writer.write(f_out)

        job.connection.set(f"job_status:{job.id}", json.dumps({
            "status": "finished",
            "result": output_filename
        }))
        return output_filename

    except Exception as e:
        job.connection.set(f"job_status:{job.id}", json.dumps({
            "status": "failed",
            "result": str(e)
        }))
        raise

def perform_compress_pdf(job_input):
    job = get_current_job()
    try:
        input_path = job_input["input_path"]
        level = job_input.get("level", "recommended")
        upload_folder = job_input['upload_folder']  # use the value from job_input
        gs_path = job_input.get("gs_path", "gs")

        quality_map = {
            "extreme": "screen",
            "recommended": "ebook",
            "less": "printer"
        }
        quality = quality_map.get(level, "ebook")

        output_filename = f"compressed_{uuid.uuid4().hex}.pdf"
        output_path = os.path.join(upload_folder, output_filename)

        compress_pdf(input_path, output_path, gs_path, quality=quality)

        job.connection.set(f"job_status:{job.id}", json.dumps({
            "status": "finished",
            "result": output_filename
        }))
        return output_filename

    except Exception as e:
        job.connection.set(f"job_status:{job.id}", json.dumps({
            "status": "failed",
            "result": str(e)
        }))
        raise


def perform_ocr_pdf(job_input):
    job = get_current_job()
    try:
        input_path = job_input["input_path"]
        output_folder = job_input["output_folder"]
        lang = job_input.get("lang", "eng")

        output_filename = f"ocr_{uuid.uuid4().hex}.pdf"
        output_path = os.path.join(output_folder, output_filename)

        os.makedirs(output_folder, exist_ok=True)

        # Run double-pass OCR
        ocr_pdf(input_path, output_path, lang=lang)

        # Report success
        job.connection.set(f"job_status:{job.id}", json.dumps({
            "status": "finished",
            "result": output_filename
        }))
        return output_filename

    except Exception as e:
        job.connection.set(f"job_status:{job.id}", json.dumps({
            "status": "failed",
            "result": str(e)
        }))
        raise



def perform_images_to_pdf(image_data, output_pdf_path, orientation="P"):
    return convert_image_to_pdf(image_data, output_pdf_path, orientation)

def perform_add_page_numbers(job_input):
    input_path = job_input["input_path"]
    position = job_input["position"]
    upload_folder = job_input["upload_folder"]  # Already passed; no current_app here

    reader = PdfReader(input_path)
    writer = PdfWriter()

    for i, page in enumerate(reader.pages):
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)

        # Determine coordinates based on position
        positions = {
            "top-left": (0.5 * inch, 10.75 * inch),
            "top-center": (4.25 * inch, 10.75 * inch),
            "top-right": (7.5 * inch, 10.75 * inch),
            "bottom-left": (0.5 * inch, 0.5 * inch),
            "bottom-center": (4.25 * inch, 0.5 * inch),
            "bottom-right": (7.5 * inch, 0.5 * inch),
        }
        x, y = positions.get(position, (4.25 * inch, 0.5 * inch))

        can.setFont("Helvetica", 10)
        can.drawString(x, y, f"{i + 1}")
        can.save()

        packet.seek(0)
        overlay_pdf = PdfReader(packet)
        page.merge_page(overlay_pdf.pages[0])
        writer.add_page(page)

    output_filename = f"numbered_{uuid.uuid4().hex}.pdf"
    output_path = os.path.join(upload_folder, output_filename)

    with open(output_path, "wb") as out_file:
        writer.write(out_file)

    return output_filename

def perform_rotate_pages(job_input):
    """
    Rotates and reorders PDF pages based on input.
    """
    input_path = job_input["input_path"]
    rotations = job_input.get("rotations", {})
    order = job_input.get("order", [])
    upload_folder = job_input.get("upload_folder")  # use the passed folder

    output_filename = f"{uuid.uuid4().hex}.pdf"
    output_path = os.path.join(upload_folder, output_filename)

    reader = PdfReader(input_path)
    writer = PdfWriter()

    num_pages = len(reader.pages)
    indices = order if order else list(range(num_pages))

    for idx in indices:
        page = reader.pages[idx]
        angle = rotations.get(str(idx), 0)
        if angle != 0:
            page.rotate(angle)
        writer.add_page(page)

    with open(output_path, "wb") as f:
        writer.write(f)

    return output_filename


def perform_word_to_pdf(input_path, output_path):
    job = get_current_job()
    try:
        # Use LibreOffice in headless mode to convert to PDF
        subprocess.run([
            "libreoffice",
            "--headless",
            "--convert-to", "pdf",
            "--outdir", os.path.dirname(output_path),
            input_path
        ], check=True)

        job.connection.set(
            f'job_status:{job.id}',
            json.dumps({'status': 'finished', 'result': os.path.basename(output_path)})
        )
        return os.path.basename(output_path)

    except Exception as e:
        job.connection.set(
            f'job_status:{job.id}',
            json.dumps({'status': 'failed', 'result': str(e)})
        )
        raise



def perform_add_text_watermark(job_input):
    input_path = job_input['input_path']
    text = job_input['text']
    position = job_input['position']
    angle = job_input.get('angle', 0)
    opacity = job_input.get('opacity', 0.3)
    upload_folder = job_input['upload_folder']

    reader = PdfReader(input_path)
    writer = PdfWriter()

    for page in reader.pages:
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=(page.mediabox.width, page.mediabox.height))

        # Determine position
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        if position == 'top-left':
            x, y = 50, height - 50
        elif position == 'top-center':
            x, y = width / 2, height - 50
        elif position == 'top-right':
            x, y = width - 50, height - 50
        elif position == 'bottom-left':
            x, y = 50, 50
        elif position == 'bottom-center':
            x, y = width / 2, 50
        elif position == 'bottom-right':
            x, y = width - 50, 50
        else:  # center
            x, y = width / 2, height / 2

        can.saveState()
        can.translate(x, y)
        can.rotate(angle)
        can.setFillAlpha(opacity)
        can.setFont("Helvetica", 40)
        can.drawCentredString(0, 0, text)
        can.restoreState()
        can.save()

        packet.seek(0)
        overlay_pdf = PdfReader(packet)
        page.merge_page(overlay_pdf.pages[0])
        writer.add_page(page)

    output_filename = f"watermarked_{uuid.uuid4().hex}.pdf"
    output_path = os.path.join(upload_folder, output_filename)

    with open(output_path, "wb") as out_file:
        writer.write(out_file)

    return output_filename


def perform_crop_pdf_rect(job_input):
    input_path = job_input['input_path']
    coords = job_input['coords']  # {x, y, width, height} in points
    upload_folder = job_input['upload_folder']

    reader = PdfReader(input_path)
    writer = PdfWriter()

    for page in reader.pages:
        media_box = page.mediabox
        # Calculate new coordinates
        llx = float(media_box.lower_left[0]) + coords['x']
        lly = float(media_box.lower_left[1]) + coords['y']
        urx = llx + coords['width']
        ury = lly + coords['height']

        page.mediabox.lower_left = (llx, lly)
        page.mediabox.upper_right = (urx, ury)
        writer.add_page(page)

    output_filename = f"cropped_{uuid.uuid4().hex}.pdf"
    output_path = os.path.join(upload_folder, output_filename)

    with open(output_path, "wb") as f:
        writer.write(f)

    return output_filename

def perform_edit_pdf_text(job_input):
    input_path = job_input['input_path']
    edits = job_input['edits']  # List of {page, old_text, new_text}
    upload_folder = job_input['upload_folder']

    pdf_document = fitz.open(input_path)

    for edit in edits:
        page_number = edit['page']
        old_text = edit['old_text']
        new_text = edit['new_text']
        page = pdf_document[page_number]

        # Find instances of old text
        text_instances = page.search_for(old_text)

        for inst in text_instances:
            # Erase old text
            page.add_redact_annot(inst, fill=(1,1,1))
            page.apply_redactions()
            # Insert new text at top-left of bbox
            page.insert_text(inst[:2], new_text, fontsize=12, color=(0,0,0))

    # Save edited PDF
    output_filename = f"edited_{uuid.uuid4().hex}.pdf"
    output_path = os.path.join(upload_folder, output_filename)
    pdf_document.save(output_path)
    pdf_document.close()

    return {"output_path": output_path, "output_filename": output_filename}

# ----------------------------------------------------------------------
# Perform Protect PDF
# ----------------------------------------------------------------------

def perform_protect_pdf(job_input):
    input_path = job_input['input_path']
    password = job_input['password']
    upload_folder = job_input['upload_folder']

    output_path = input_path.replace('.pdf', '_protected.pdf')

    reader = PdfReader(input_path)
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    writer.encrypt(password)

    with open(output_path, 'wb') as f:
        writer.write(f)

    return {"output_path": output_path, "status": "completed"}


def perform_password_protect(job_input):
    input_path = job_input['input_path']
    password = job_input['password']
    
    try:
        reader = PdfReader(input_path)
        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        writer.encrypt(password)

        base, ext = os.path.splitext(os.path.basename(input_path))
        output_filename = f"{base}_protected{ext}"
        output_path = os.path.join(os.path.dirname(input_path), output_filename)

        with open(output_path, 'wb') as f:
            writer.write(f)

        # Clean up the original file
        os.remove(input_path)

        # Return the output filename
        return output_filename

    except Exception as e:
        print(f"Error during password protection: {e}")
        # Return None or a specific error message if the job fails
        return None

# ----------------------------------------------------------------------
# Unlock PDF
# ----------------------------------------------------------------------
def perform_unlock_pdf(job_input):
    input_path = job_input['input_path']
    password = job_input['password']
    upload_folder = job_input['upload_folder']

    output_filename = f"unlocked_{os.path.basename(input_path)}"
    output_path = os.path.join(upload_folder, output_filename)

    reader = PdfReader(input_path)
    if reader.decrypt(password):
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)

        with open(output_path, "wb") as f:
            writer.write(f)

        return {"output_filename": output_filename}
    else:
        raise Exception("Failed to decrypt PDF with the provided password.")


# ----------------------------------------------------------------------
# PDF Signing Worker
# ----------------------------------------------------------------------

# Fonts path
FONTS_PATH = os.path.join("static", "fonts")
CUSTOM_FONTS = {
    "DancingScript": os.path.join(FONTS_PATH, "DancingScript-Regular.ttf"),
    "GreatVibes": os.path.join(FONTS_PATH, "GreatVibes-Regular.ttf"),
    "Pacifico": os.path.join(FONTS_PATH, "Pacifico-Regular.ttf"),
    "Satisfy": os.path.join(FONTS_PATH, "Satisfy-Regular.ttf"),
}

# Register fonts
for name, path in CUSTOM_FONTS.items():
    if os.path.exists(path):
        pdfmetrics.registerFont(TTFont(name, path))

def apply_signatures(input_path, output_folder, placements):
    """
    placements: list of dicts, each dict has:
    {
        page_number: int,
        x: float,
        y: float,
        text: str,
        font: str,
        color: str,
        size_pt: int
    }
    """
    try:
        reader = PdfReader(input_path)
        writer = PdfWriter()

        # Process each page separately
        page_overlays = {}
        for p in placements:
            page_num = int(p['page_number'])
            if page_num not in page_overlays:
                page = reader.pages[page_num]
                w, h = float(page.mediabox.width), float(page.mediabox.height)
                packet_path = os.path.join(output_folder, f"overlay_{uuid.uuid4().hex}.pdf")
                c = canvas.Canvas(packet_path, pagesize=(w, h))
                page_overlays[page_num] = {'canvas': c, 'path': packet_path}

            overlay = page_overlays[page_num]
            c = overlay['canvas']

            font = p.get('font', 'Helvetica')
            size_pt = int(p.get('size_pt', 18))
            color_name = p.get('color', 'black')
            colors = {"red": red, "black": black, "green": green, "blue": blue}

            if font in CUSTOM_FONTS:
                c.setFont(font, size_pt)
            else:
                c.setFont("Helvetica", size_pt)
            c.setFillColor(colors.get(color_name.lower(), black))

            c.drawString(float(p['x']), float(p['y']), p['text'])

        # Save overlays and merge into PDF
        for page_num, overlay in page_overlays.items():
            overlay['canvas'].save()
            overlay_reader = PdfReader(overlay['path'])
            overlay_page = overlay_reader.pages[0]
            reader.pages[page_num].merge_page(overlay_page)
            os.remove(overlay['path'])  # cleanup

        # Write final PDF
        output_filename = f"signed_{uuid.uuid4().hex}.pdf"
        output_path = os.path.join(output_folder, output_filename)

        # Add all pages to writer first
        for page in reader.pages:
            writer.add_page(page)

        # Then write to output
        output_filename = f"signed_{uuid.uuid4().hex}.pdf"
        output_path = os.path.join(output_folder, output_filename)
        with open(output_path, "wb") as f_out:
            writer.write(f_out)


       
        # Update job status in Redis
        job_id = get_current_job().id
        redis_conn.set(f'job_status:{job_id}', json.dumps({'status': 'finished', 'result': output_filename}))

        return output_filename

    except Exception as e:
        job_id = get_current_job().id
        redis_conn.set(f'job_status:{job_id}', json.dumps({'status': 'failed', 'result': str(e)}))
        raise
# ----------------------------------------------------------------------
# Corrected Redact PDF Worker
# ----------------------------------------------------------------------

def redact_pdf_job(job_input):
    job = get_current_job()
    job_id = job.id if job else str(uuid.uuid4())

    input_path = job_input["input_path"]
    redactions = job_input.get("redactions", [])
    output_folder = job_input.get("output_folder", "output_pdfs")

    try:
        os.makedirs(output_folder, exist_ok=True)

        reader = PdfReader(input_path)
        writer = PdfWriter()
        page_overlays = {}
        
        # We need to get the original page size to do the conversion correctly
        # We can do this in the loop, but it's more efficient to have a map of page sizes
        page_sizes = {}
        for i, page in enumerate(reader.pages):
            page_sizes[i] = (float(page.mediabox.width), float(page.mediabox.height))

        # Create overlay PDF for each page with redactions
        for r in redactions:
            page_num = int(r.get("page_number", 0))
            if page_num not in page_sizes:
                continue

            w, h = page_sizes[page_num]

            if page_num not in page_overlays:
                overlay_path = os.path.join(output_folder, f"overlay_{uuid.uuid4().hex}.pdf")
                c = canvas.Canvas(overlay_path, pagesize=(w, h))
                page_overlays[page_num] = {"canvas": c, "path": overlay_path}

            overlay = page_overlays[page_num]
            c = overlay["canvas"]

            # The frontend now sends the unscaled, top-left coordinates.
            x_unscaled = float(r["x"])
            y_unscaled_top = float(r["y"])
            width_unscaled = float(r["width"])
            height_unscaled = float(r["height"])
            
            # 1. Invert the Y-coordinate to be relative to the bottom of the page
            pdf_y_bottom = h - y_unscaled_top - height_unscaled
            
            # Draw black rectangle for redaction
            c.setFillColor(black)
            c.rect(x_unscaled, pdf_y_bottom, width_unscaled, height_unscaled, fill=True, stroke=False)
            
        # Save overlays and merge
        for page_num, overlay in page_overlays.items():
            overlay["canvas"].save()
            overlay_reader = PdfReader(overlay["path"])
            overlay_page = overlay_reader.pages[0]
            reader.pages[page_num].merge_page(overlay_page)
            os.remove(overlay["path"])

        # Write final redacted PDF
        output_filename = f"redacted_{uuid.uuid4().hex}.pdf"
        output_path = os.path.join(output_folder, output_filename)
        for page in reader.pages:
            writer.add_page(page)
        with open(output_path, "wb") as f_out:
            writer.write(f_out)

        # Update job status
        redis_conn.set(f"job_status:{job_id}", json.dumps({"status": "finished", "result": output_filename}))
        return output_filename

    except Exception as e:
        redis_conn.set(f"job_status:{job_id}", json.dumps({"status": "failed", "result": str(e)}))
        raise






# import os
# from PyPDF2 import PdfReader, PdfWriter
# import json
# import shutil
# from redis import Redis
# import zipfile
# from rq import get_current_job
# from datetime import datetime

# redis_conn = Redis()

# def perform_split(file_path, split_option, output_folder, start_page=None, end_page=None):
#     job = get_current_job()
#     job.meta['progress'] = 0
#     job.save_meta()

#     try:
#         # Immediately set progress to a small non-zero value to give instant user feedback
#         job.meta['progress'] = 1
#         job.save_meta()

#         reader = PdfReader(file_path)
#         total_pages = len(reader.pages)
        
#         # Use a professional, timestamped naming convention
#         timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
        
#         # A temporary directory for intermediary files, which will be cleaned up
#         temp_dir = os.path.join(output_folder, f"temp_{job.id}")
#         os.makedirs(temp_dir, exist_ok=True)

#         result_filename = None

#         if split_option == 'all':
#             # Split into individual pages and save to a temporary directory
#             for i in range(total_pages):
#                 writer = PdfWriter()
#                 writer.add_page(reader.pages[i])
#                 output_path = os.path.join(temp_dir, f'page_{i + 1}.pdf')
#                 with open(output_path, "wb") as output_pdf:
#                     writer.write(output_pdf)

#                 # Calculate and update progress
#                 progress = int(((i + 1) / total_pages) * 100)
#                 job.meta['progress'] = progress
#                 job.save_meta()

#             # Zip the output files directly to the output folder
#             zip_filename = f"taptopdf_split_{timestamp}.zip"
#             zip_path = os.path.join(output_folder, zip_filename)
#             with zipfile.ZipFile(zip_path, 'w') as zf:
#                 for root, _, files in os.walk(temp_dir):
#                     for file in files:
#                         # Zip the file but only with its basename, not full path
#                         zf.write(os.path.join(root, file), os.path.basename(file))
            
#             # The result is the final filename, which will be found in the output folder
#             result_filename = zip_filename
#             shutil.rmtree(temp_dir) # Clean up the temporary directory

#         elif split_option == 'range':
#             writer = PdfWriter()
#             pages_to_process = end_page - start_page + 1
#             for i in range(start_page - 1, end_page):
#                 writer.add_page(reader.pages[i])
                
#                 # Calculate and update progress
#                 progress = int(((i - (start_page - 1) + 1) / pages_to_process) * 100)
#                 job.meta['progress'] = progress
#                 job.save_meta()

#             # The result is a single PDF, so we save it directly to the output folder
#             output_filename = f"taptopdf_split_range_{timestamp}.pdf"
#             output_path = os.path.join(output_folder, output_filename)
#             with open(output_path, "wb") as output_pdf:
#                 writer.write(output_pdf)
                
#             # The result is the final filename, which will be found in the output folder
#             result_filename = output_filename

#         # Set the final status with the correct filename
#         job.connection.set(f"job_status:{job.id}", json.dumps({"status": "finished", "result": result_filename, "progress": 100}))
#         return result_filename
        
#     except Exception as e:
#         job.connection.set(f"job_status:{job.id}", json.dumps({"status": "failed", "result": str(e), "progress": 100}))
#         # Ensure temporary directory is cleaned up on error as well
#         if 'temp_dir' in locals() and os.path.exists(temp_dir):
#             shutil.rmtree(temp_dir)
#         raise




import os
from PyPDF2 import PdfReader, PdfWriter
import json
import shutil
from redis import Redis
import zipfile
from rq import get_current_job
from datetime import datetime
import time

redis_conn = Redis()

def perform_split(file_path, split_option, output_folder, start_page=None, end_page=None):
    job = get_current_job()
    job.meta['progress'] = 0
    job.save_meta()

    try:
        # Immediately set progress to a small non-zero value to give instant user feedback
        job.meta['progress'] = 1
        job.save_meta()

        reader = PdfReader(file_path)
        total_pages = len(reader.pages)

        # Simulate progress updates for small files
        if total_pages <= 10:  # For small files (e.g., 10 or fewer pages)
            for i in range(1, 101):  # Update progress from 1% to 100%
                job.meta['progress'] = i
                job.save_meta()
                time.sleep(0.05)  # Simulate work in small intervals

        # Use a professional, timestamped naming convention
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
        
        # A temporary directory for intermediary files, which will be cleaned up
        temp_dir = os.path.join(output_folder, f"temp_{job.id}")
        os.makedirs(temp_dir, exist_ok=True)

        result_filename = None

        if split_option == 'all':
            # Split into individual pages and save to a temporary directory
            for i in range(total_pages):
                writer = PdfWriter()
                writer.add_page(reader.pages[i])
                output_path = os.path.join(temp_dir, f'page_{i + 1}.pdf')
                with open(output_path, "wb") as output_pdf:
                    writer.write(output_pdf)

                # Calculate and update progress incrementally (e.g., after every page)
                progress = int(((i + 1) / total_pages) * 100)
                job.meta['progress'] = progress
                job.save_meta()

            # Zip the output files directly to the output folder
            zip_filename = f"taptopdf_split_{timestamp}.zip"
            zip_path = os.path.join(output_folder, zip_filename)
            with zipfile.ZipFile(zip_path, 'w') as zf:
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        # Zip the file but only with its basename, not full path
                        zf.write(os.path.join(root, file), os.path.basename(file))
            
            # The result is the final filename, which will be found in the output folder
            result_filename = zip_filename
            shutil.rmtree(temp_dir) # Clean up the temporary directory

        elif split_option == 'range':
            writer = PdfWriter()
            pages_to_process = end_page - start_page + 1
            for i in range(start_page - 1, end_page):
                writer.add_page(reader.pages[i])
                
                # Calculate and update progress incrementally
                progress = int(((i - (start_page - 1) + 1) / pages_to_process) * 100)
                job.meta['progress'] = progress
                job.save_meta()

            # The result is a single PDF, so we save it directly to the output folder
            output_filename = f"taptopdf_split_range_{timestamp}.pdf"
            output_path = os.path.join(output_folder, output_filename)
            with open(output_path, "wb") as output_pdf:
                writer.write(output_pdf)
                
            # The result is the final filename, which will be found in the output folder
            result_filename = output_filename

        # Set the final status with the correct filename
        job.connection.set(f"job_status:{job.id}", json.dumps({"status": "finished", "result": result_filename, "progress": 100}))
        return result_filename
        
    except Exception as e:
        job.connection.set(f"job_status:{job.id}", json.dumps({"status": "failed", "result": str(e), "progress": 100}))
        # Ensure temporary directory is cleaned up on error as well
        if 'temp_dir' in locals() and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        raise


# ----------------------------------------------------------------------
# Worker Entrypoint
# ----------------------------------------------------------------------
if __name__ == "__main__":
    conn = Redis(host="localhost", port=6379, db=0)
    queue = Queue("default", connection=conn)

    logging.info("🚀 Worker started, listening on queue: default")
    worker = Worker([queue], connection=conn)
    worker.work(with_scheduler=True)