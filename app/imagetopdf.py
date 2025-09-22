# app/imagetopdf.py

import os
import tempfile
from PIL import Image
from fpdf import FPDF

def convert_image_to_pdf(image_data, output_pdf_path, orientation="P"):
    pdf = FPDF(orientation=orientation)

    for item in image_data:
        path = item["path"]
        rotation = item.get("rotation", 0)

        img = Image.open(path)

        if rotation:
            img = img.rotate(-rotation, expand=True)

        if img.mode != "RGB":
            img = img.convert("RGB")

        # Save rotated image to temp file
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            temp_path = tmp.name
            img.save(temp_path, format="JPEG")

        pdf.add_page()
        pdf.image(temp_path, x=10, y=10, w=190)
        os.unlink(temp_path)

    pdf.output(output_pdf_path)
    return os.path.basename(output_pdf_path)
