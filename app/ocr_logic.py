import os
import json
import uuid
import fitz  # PyMuPDF
import pytesseract
from pdf2image import convert_from_path
from rq import get_current_job

pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'


def _single_ocr_pass(input_pdf_path, output_pdf_path, dpi=300, lang="eng"):
    """Run one OCR pass and produce a searchable PDF."""
    original_doc = fitz.open(input_pdf_path)
    images = convert_from_path(input_pdf_path, dpi=dpi)
    output_doc = fitz.open()

    for img, orig_page in zip(images, original_doc):
        rect = orig_page.rect
        page = output_doc.new_page(width=rect.width, height=rect.height)

        # Insert original visual page
        pix = orig_page.get_pixmap(dpi=dpi)
        page.insert_image(rect, stream=pix.tobytes("png"))

        # OCR just the image
        pdf_bytes = pytesseract.image_to_pdf_or_hocr(
            img,
            lang=lang,
            extension="pdf"
        )

        # Overlay OCR text layer
        ocr_pdf = fitz.open("pdf", pdf_bytes)
        page.show_pdf_page(rect, ocr_pdf, 0)

    output_doc.save(output_pdf_path, garbage=4, deflate=True)
    output_doc.close()
    original_doc.close()


def ocr_pdf(input_pdf_path, output_pdf_path, dpi=300, lang="eng"):
    """Run OCR twice to ensure full searchability."""
    try:
        # First pass
        temp_path = output_pdf_path + ".tmp.pdf"
        _single_ocr_pass(input_pdf_path, temp_path, dpi=dpi, lang=lang)

        # Second pass on result of first
        _single_ocr_pass(temp_path, output_pdf_path, dpi=dpi, lang=lang)

        # Clean up
        os.remove(temp_path)

        print(f"✅ Double-pass searchable PDF created: {output_pdf_path}")
        return output_pdf_path

    except Exception as e:
        print(f"❌ OCR failed: {e}")
        raise
