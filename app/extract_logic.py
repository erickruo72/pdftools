# app/extract_logic.py

import os
import uuid
import logging
from PyPDF2 import PdfReader, PdfWriter

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def extract_pdf_pages(input_path, pages_to_extract, output_path):
    """
    Extract specific pages from a PDF and save as a new PDF.
    
    :param input_path: Path to the input PDF
    :param pages_to_extract: List of 1-based page numbers to extract
    :param output_path: Where to save the resulting extracted PDF
    """
    try:
        reader = PdfReader(input_path)
        writer = PdfWriter()

        total_pages = len(reader.pages)
        valid_pages = [p for p in pages_to_extract if 1 <= p <= total_pages]

        if not valid_pages:
            raise ValueError("No valid pages to extract.")

        for page_num in valid_pages:
            writer.add_page(reader.pages[page_num - 1])

        with open(output_path, "wb") as out_f:
            writer.write(out_f)

        logging.info(f"Extracted pages saved to {output_path}")
        return output_path
    except Exception as e:
        logging.error(f"Error extracting pages: {e}")
        raise
