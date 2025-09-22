import os
import tempfile
from pdf2image import convert_from_path
from zipfile import ZipFile
from pathlib import Path

def convert_pdf_to_images(pdf_path, output_folder):
    images = convert_from_path(pdf_path)
    image_paths = []

    for i, img in enumerate(images):
        img_path = os.path.join(output_folder, f"page_{i+1}.png")
        img.save(img_path, "PNG")
        image_paths.append(img_path)

    return image_paths

def create_zip_from_images(image_paths, zip_path):
    with ZipFile(zip_path, 'w') as zipf:
        for img_path in image_paths:
            arcname = os.path.basename(img_path)
            zipf.write(img_path, arcname=arcname)
