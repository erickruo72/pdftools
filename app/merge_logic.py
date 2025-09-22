import os
import uuid
import pypdf
import logging
from datetime import timedelta
from werkzeug.utils import secure_filename
from flask import jsonify
from rq import get_current_job

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def allowed_file(filename, allowed_extensions):
    """Check if the uploaded file has a valid extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


# ----------------------------------------------------------------------
# Upload Handler
# ----------------------------------------------------------------------
def handle_upload(request, upload_folder, allowed_extensions):
    """
    Handles the initial PDF file upload from the client.
    Saves the files to a temporary location and returns their details.
    """
    uploaded_files = request.files.getlist("files")

    if not uploaded_files or not uploaded_files[0].filename:
        return jsonify({"error": "No files selected."}), 400

    uploaded_file_data = []

    for file in uploaded_files:
        if file and allowed_file(file.filename, allowed_extensions):
            # Generate a secure and unique filename
            unique_filename = f"{uuid.uuid4()}_{secure_filename(file.filename)}"
            file_path = os.path.join(upload_folder, unique_filename)
            file.save(file_path)

            try:
                reader = pypdf.PdfReader(file_path)
                page_count = len(reader.pages)
            except Exception as e:
                logging.error(f"Error reading PDF file {file.filename}: {e}")
                os.remove(file_path)  # Clean up invalid file
                return jsonify({"error": f"Invalid PDF file: {file.filename}"}), 400

            uploaded_file_data.append({
                "original_name": file.filename,
                "unique_name": unique_filename,
                "path": file_path,
                "pages": page_count
            })

    return jsonify({"message": "Files uploaded successfully", "files": uploaded_file_data})


# ----------------------------------------------------------------------
# Cleanup
# ----------------------------------------------------------------------
def delete_merged_file(file_path):
    """
    Background task to delete a merged file after a delay.
    """
    logging.info(f"Attempting to delete merged file at: {file_path}")
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            logging.info(f"Successfully deleted {file_path}.")
        except Exception as e:
            logging.error(f"Error deleting file {file_path}: {e}")
    else:
        logging.warning(f"File not found, could not delete: {file_path}")


# ----------------------------------------------------------------------
# Merge Handler
# ----------------------------------------------------------------------
def handle_merge(job_input):
    """
    Performs the PDF merging operation based on job input.
    This function runs in the worker process.
    """
    files_to_merge = job_input.get("files")
    upload_folder = job_input.get("upload_folder")

    if not files_to_merge:
        return "error: no files to merge"

    merged_writer = pypdf.PdfWriter()

    for file_info in files_to_merge:
        file_path = file_info["path"]
        try:
            reader = pypdf.PdfReader(file_path)
            for page in reader.pages:
                merged_writer.add_page(page)
        except Exception as e:
            logging.error(f"Error processing {file_path}: {e}")
            pass
        finally:
            # ✅ Clean up each uploaded file after merging
            if os.path.exists(file_path):
                os.remove(file_path)

    # Generate merged filename
    merged_filename = f"merged_{uuid.uuid4()}.pdf"
    merged_path = os.path.join(upload_folder, merged_filename)

    with open(merged_path, "wb") as output_stream:
        merged_writer.write(output_stream)

    # ✅ Schedule deletion in 5 minutes (if running inside worker job)
    try:
        current_job = get_current_job()
        if current_job:
            scheduler = current_job.connection
            scheduler.enqueue_in(
                timedelta(minutes=5),
                delete_merged_file,
                merged_path
            )
            logging.info(f"Scheduled deletion of {merged_path} in 5 minutes.")
        else:
            logging.warning("Could not get current job, file will not be scheduled for deletion.")
    except Exception as e:
        logging.error(f"Failed to schedule file deletion: {e}")

    return merged_filename


# ----------------------------------------------------------------------
# Preview Handler (stub for now)
# ----------------------------------------------------------------------
def handle_preview(request, upload_folder):
    """
    Processes a request to generate a preview image for a PDF.
    (To be implemented later with fitz/pdf2image)
    """
    pass
