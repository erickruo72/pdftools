# app/perform_pdf_to_word.py

import os
from pdf2docx import Converter

def perform_pdf_to_word(pdf_path, output_docx_path):
    cv = Converter(pdf_path)
    cv.convert(output_docx_path, start=0, end=None)
    cv.close()

    return os.path.basename(output_docx_path)
