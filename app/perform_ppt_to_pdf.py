import subprocess
import os

def perform_ppt_to_pdf(input_path, output_path):
    """
    Convert PPT/PPTX file to PDF using LibreOffice (soffice).
    Works on Linux servers with LibreOffice installed.
    """
    try:
        # Run LibreOffice in headless mode
        subprocess.run([
            "soffice",
            "--headless",
            "--convert-to", "pdf",
            "--outdir", os.path.dirname(output_path),
            input_path
        ], check=True)

        # LibreOffice outputs <filename>.pdf in output directory
        return os.path.basename(output_path)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"LibreOffice conversion failed: {e}")
