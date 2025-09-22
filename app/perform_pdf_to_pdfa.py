import os
import uuid
import subprocess
import json
from rq import get_current_job

def perform_pdf_to_pdfa(job_input):
    job = get_current_job()

    try:
        input_path = job_input["input_path"]
        upload_folder = job_input.get("upload_folder", os.path.dirname(input_path))
        output_filename = f"{uuid.uuid4().hex}_pdfa.pdf"
        output_path = os.path.join(upload_folder, output_filename)

        # Ensure the output folder exists
        os.makedirs(upload_folder, exist_ok=True)

        # Path to Ghostscript executable and PDF/A-2b profile
        gs_exe = r"C:\gs10.05.1\bin\gswin64c.exe"
        pdfa_profile = r"C:\gs10.05.1\lib\PDFA_def.ps"

        if not os.path.exists(gs_exe):
            raise FileNotFoundError(f"Ghostscript executable not found at: {gs_exe}")
        if not os.path.exists(pdfa_profile):
            raise FileNotFoundError(f"PDF/A profile not found at: {pdfa_profile}")

        # Ghostscript command to convert to PDF/A-2b
        gs_cmd = [
            gs_exe,
            "-dPDFA=2",  # Set PDF/A-2b mode
            "-dCompatibilityLevel=1.7",  # Compatibility level (PDF 1.7)
            "-dEmbedAllFonts=true",  # Embed all fonts in the document
            "-dBATCH",  # Exit after processing
            "-dNOPAUSE",  # No pause between pages
            "-sDEVICE=pdfwrite",  # Output format is PDF
            "-dColorImageResolution=300",  # Resolution for color images
            "-dGrayImageResolution=300",  # Resolution for grayscale images
            "-dMonoImageResolution=300",  # Resolution for monochrome images
            f"-sOutputFile={output_path}",  # Output file path
            pdfa_profile,  # PDF/A profile
            input_path  # Input file path
        ]

        # Run Ghostscript to convert to PDF/A-2b
        subprocess.run(gs_cmd, check=True, capture_output=True, text=True)

        # Validate the converted PDF with veraPDF
        verapdf_exe = r"C:\Users\Erick Ruo\verapdf\verapdf.bat"
        validation_log = os.path.join(upload_folder, "validation.log")

        validate_cmd = [
            verapdf_exe,
            "--format", "text",  # Output in text format
            "--fail-fast",  # Stop at first failure
            output_path  # Path to the converted PDF
        ]

        validation = subprocess.run(
            validate_cmd,
            capture_output=True,
            text=True,
            check=False
        )

        # Log the validation output
        with open(validation_log, "w", encoding="utf-8") as f:
            f.write("=== veraPDF Validation Output ===\n")
            f.write(validation.stdout + "\n" + validation.stderr)

        # Check if the PDF passed validation
        if "PASS" in validation.stdout.upper():
            job.connection.set(f"job_status:{job.id}", json.dumps({
                "status": "finished",
                "result": output_filename,
                "message": "PDF/A-2B conversion and validation successful."
            }))
            return output_filename
        else:
            job.connection.set(f"job_status:{job.id}", json.dumps({
                "status": "finished",
                "result": output_filename,
                "warning": "Conversion completed, but validation failed. See logs."
            }))
            return output_filename

    except Exception as e:
        job.connection.set(f"job_status:{job.id}", json.dumps({
            "status": "failed",
            "result": str(e)
        }))
        raise

