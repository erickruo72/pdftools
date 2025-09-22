import os
from pdf2image import convert_from_path
from pptx import Presentation
from pptx.util import Inches

def convert_pdf_to_pptx(pdf_path, pptx_path=None, dpi=200):
    """
    Converts a PDF file into a PowerPoint presentation by turning each page into an image slide.

    Args:
        pdf_path (str): Path to the PDF file.
        pptx_path (str, optional): Output PPTX path. Defaults to same folder as PDF.
        dpi (int): Dots per inch for PDF to image conversion.

    Returns:
        str: The output PPTX file path.
    """
    images = convert_from_path(pdf_path, dpi=dpi)

    prs = Presentation()
    blank_slide_layout = prs.slide_layouts[6]  # Blank layout

    # Set slide size to match first image size
    first_image = images[0]
    prs.slide_width = Inches(first_image.width / dpi)
    prs.slide_height = Inches(first_image.height / dpi)

    for i, img in enumerate(images):
        slide = prs.slides.add_slide(blank_slide_layout)
        temp_img_path = f"_temp_slide_{i}.jpg"
        img.save(temp_img_path, 'JPEG')

        slide.shapes.add_picture(temp_img_path, Inches(0), Inches(0), width=prs.slide_width, height=prs.slide_height)

        os.remove(temp_img_path)

    if pptx_path is None:
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        pptx_path = os.path.join(os.path.dirname(pdf_path), f"{base_name}.pptx")


    prs.save(pptx_path)
    return os.path.basename(pptx_path)

