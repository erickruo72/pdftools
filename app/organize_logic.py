from PyPDF2 import PdfReader, PdfWriter
import os

def organize_pdf(input_path, pages_data, output_path):
    """
    Rearranges and rotates PDF pages.
    pages_data = {
        "order": [pageNums],        # e.g. [3,1,2]
        "rotations": {"1": 90}      # dict with keys as strings from JSON
    }
    """
    reader = PdfReader(input_path)
    writer = PdfWriter()

    order = pages_data.get("order", [])
    rotations = pages_data.get("rotations", {})

    for page_num in order:
        page = reader.pages[page_num - 1]  # frontend sends 1-based
        rotation = rotations.get(str(page_num), 0)
        if rotation:
            page.rotate(int(rotation))
        writer.add_page(page)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        writer.write(f)

    return output_path
