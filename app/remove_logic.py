import os
from PyPDF2 import PdfReader, PdfWriter

def remove_pdf_pages(input_path, pages_to_remove, output_path, download=True):
    """
    Remove specified pages from a PDF and save to output_path.

    Parameters:
    - input_path: str - path to input PDF
    - pages_to_remove: list of int - 1-based page numbers to remove
    - output_path: str - path to save modified PDF
    - download: bool - if True, return output_path for download; else just save
    """

    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Input PDF not found: {input_path}")

    reader = PdfReader(input_path)
    writer = PdfWriter()

    total_pages = len(reader.pages)
    pages_to_remove_set = set(pages_to_remove)

    # Validate pages to remove
    for p in pages_to_remove_set:
        if p < 1 or p > total_pages:
            raise ValueError(f"Page number {p} out of bounds (1-{total_pages})")

    # Add pages except those to remove
    for i in range(total_pages):
        if (i + 1) not in pages_to_remove_set:
            writer.add_page(reader.pages[i])

    # Save the modified PDF
    with open(output_path, "wb") as out_pdf:
        writer.write(out_pdf)

    return output_path
