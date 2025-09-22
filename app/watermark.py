from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import Color
import io, os, uuid

def perform_add_text_watermark(job_input):
    input_path = job_input['input_path']
    text = job_input['text']

    try:
        angle = -float(job_input.get('angle', '45'))
    except (ValueError, TypeError):
        angle = -45.0

    try:
        opacity = float(job_input.get('opacity', '0.3'))
    except (ValueError, TypeError):
        opacity = 0.3

    try:
        size = float(job_input.get('size', '28'))
    except (ValueError, TypeError):
        size = 28.0

    position = job_input.get('position', 'center')

    try:
        x = float(job_input.get('x'))
    except (ValueError, TypeError):
        x = None

    try:
        y = float(job_input.get('y'))
    except (ValueError, TypeError):
        y = None

    try:
        canvas_width = float(job_input.get('canvas_width'))
    except (ValueError, TypeError):
        canvas_width = None

    try:
        canvas_height = float(job_input.get('canvas_height'))
    except (ValueError, TypeError):
        canvas_height = None

    page_option = job_input.get('page_option', 'all')
    specific_pages = job_input.get('specific_pages', '')
    upload_folder = job_input['upload_folder']

    reader = PdfReader(input_path)
    writer = PdfWriter()
    total_pages = len(reader.pages)

    if page_option == "all":
        target_pages = range(total_pages)
    elif page_option == "specific":
        try:
            pages = [int(p.strip()) for p in specific_pages.split(',') if p.strip()]
            target_pages = [p - 1 for p in pages if 1 <= p <= total_pages]
        except (ValueError, AttributeError):
            target_pages = range(total_pages)
    elif page_option == "exclude_first":
        target_pages = range(1, total_pages)
    elif page_option == "exclude_last":
        target_pages = range(0, total_pages - 1)
    else:
        target_pages = range(total_pages)

    def create_watermark(page_width, page_height):
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=(page_width, page_height))
        can.setFont("Helvetica", size)

        # Set watermark fill color: gray with alpha
        gray = Color(0.3, 0.3, 0.3, alpha=opacity)
        can.setFillColor(gray)

        if position == "custom" and x is not None and y is not None and canvas_width and canvas_height:
            tx = min(max((x / canvas_width) * page_width, 0), page_width)
            ty = min(max((1 - y / canvas_height) * page_height, 0), page_height)
        else:
            tx, ty = page_width / 2, page_height / 2

        can.saveState()
        can.translate(tx, ty)
        can.rotate(angle)
        can.drawCentredString(0, 0, text)
        can.restoreState()
        can.save()

        packet.seek(0)
        return PdfReader(packet).pages[0]

    for i, page in enumerate(reader.pages):
        if i in target_pages:
            page_width = float(page.mediabox.width)
            page_height = float(page.mediabox.height)
            watermark = create_watermark(page_width, page_height)
            page.merge_page(watermark)
        writer.add_page(page)

    output_filename = f"watermarked_{uuid.uuid4().hex}.pdf"
    output_path = os.path.join(upload_folder, output_filename)
    with open(output_path, "wb") as f:
        writer.write(f)

    return output_filename
