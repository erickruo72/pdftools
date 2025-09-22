# app/perform_excel_to_pdf.py
import os
import subprocess

def perform_excel_to_pdf(input_path, output_path):
    try:
        # Run LibreOffice in headless mode to convert Excel to PDF
        subprocess.run([
            "libreoffice",
            "--headless",
            "--convert-to", "pdf",
            "--outdir", os.path.dirname(output_path),
            input_path
        ], check=True)

        return os.path.basename(output_path)

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Excel to PDF conversion failed: {e}")
