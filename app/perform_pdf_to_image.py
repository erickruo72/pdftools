# app/perform_pdf_to_image.py

import os
import fitz  # PyMuPDF
import zipfile

def perform_pdf_to_image(input_path, output_dir):
    doc = fitz.open(input_path)
    for i, page in enumerate(doc):
        pix = page.get_pixmap()
        image_filename = f"{os.path.splitext(os.path.basename(input_path))[0]}_page_{i + 1}.png"
        image_path = os.path.join(output_dir, image_filename)
        pix.save(image_path)

    # Create ZIP file from all PNGs
    zip_path = f"{output_dir}.zip"
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for filename in os.listdir(output_dir):
            file_path = os.path.join(output_dir, filename)
            zipf.write(file_path, arcname=filename)

    return os.path.basename(zip_path)  # Only return zip filename
