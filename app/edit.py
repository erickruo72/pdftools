
import io
import os
import uuid
import json
import base64
from redis import Redis
from rq import get_current_job
from reportlab.pdfgen import canvas
from reportlab.lib.colors import black, red, green, blue
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from PyPDF2 import PdfReader, PdfWriter
import logging

logger = logging.getLogger(__name__)
redis_conn = Redis()

# Fonts path
FONTS_PATH = os.path.join("static", "fonts")
CUSTOM_FONTS = {
    "DancingScript": os.path.join(FONTS_PATH, "DancingScript-Regular.ttf"),
    "GreatVibes": os.path.join(FONTS_PATH, "GreatVibes-Regular.ttf"),
    "Pacifico": os.path.join(FONTS_PATH, "Pacifico-Regular.ttf"),
    "Satisfy": os.path.join(FONTS_PATH, "Satisfy-Regular.ttf"),
    "DejaVuSans": os.path.join(FONTS_PATH, "DejaVuSans.ttf"),  # used for shapes
}

# Register fonts
for name, path in CUSTOM_FONTS.items():
    if os.path.exists(path):
        pdfmetrics.registerFont(TTFont(name, path))


def apply_signatures(input_path, output_folder, placements):
    """
    Apply text, shapes, and images to PDF.
    """
    job = get_current_job()
    job_id = job.id if job else str(uuid.uuid4())

    try:
        reader = PdfReader(input_path)
        writer = PdfWriter()
        page_overlays = {}

        # --- Create overlay PDFs for each page ---
        for p in placements:
            page_num = int(p.get("page_number", 0))
            if page_num not in page_overlays:
                page = reader.pages[page_num]
                w, h = float(page.mediabox.width), float(page.mediabox.height)
                packet_path = os.path.join(output_folder, f"overlay_{uuid.uuid4().hex}.pdf")
                c = canvas.Canvas(packet_path, pagesize=(w, h))
                page_overlays[page_num] = {"canvas": c, "path": packet_path}

            overlay = page_overlays[page_num]
            c = overlay["canvas"]

            # Colors
            color_name = p.get("color", "black").lower()
            colors_map = {"black": black, "red": red, "green": green, "blue": blue}
            c.setFillColor(colors_map.get(color_name, black))

            # --- Text placement ---
            if p.get("type") == "text":
                font = p.get("font", "Helvetica")
                size_pt = int(p.get("size_pt", 18))
                font_name = font if font in CUSTOM_FONTS else "Helvetica"
                c.setFont(font_name, size_pt)

                # Adjust Y-coordinate for top-down to bottom-up baseline alignment
                x = float(p["x"])
                # The y value is the top of the text box. We subtract the font size to get the baseline.
                # Adding a small, fixed offset (2) fine-tunes the alignment to sit on the line.
                y = float(p["y"]) - size_pt - 1

                c.drawString(x, y, str(p.get("text", "")))

            # --- Shape placement (icons) ---
            elif p.get("type") == "shape":
                shape_map = {"check": "✔", "cross": "✖", "circle": "○", "square": "□"}
                symbol = shape_map.get(p.get("shapeType", "?"), "?")
                size_px = int(p.get("size_pt", 12))
                c.setFont("DejaVuSans", size_px)

                # Adjust Y-coordinate to align the shape symbol to the baseline
                x = float(p["x"])
                # Similar to text, we subtract the height and add a fine-tuning offset.
                y = float(p["y"]) - size_px - 1
                
                c.drawString(x, y, symbol)

            # --- Image placement ---
            elif p.get("type") == "image":
                img_b64 = str(p.get("imgSrc", "")).split(",")[-1]
                img_data = io.BytesIO(base64.b64decode(img_b64))
                img = ImageReader(img_data)
                width = float(p.get("width", 150))
                height = float(p.get("height", 150))

                # Images are placed from the bottom-left, so this is correct
                x = float(p["x"])
                y = float(p["y"]) - height
                
                c.drawImage(img, x, y, width=width, height=height)

        # --- Save overlays and merge with original pages ---
        for page_num, overlay in page_overlays.items():
            overlay["canvas"].save()
            overlay_reader = PdfReader(overlay["path"])
            overlay_page = overlay_reader.pages[0]
            reader.pages[page_num].merge_page(overlay_page)
            os.remove(overlay["path"])

        # --- Write final PDF ---
        os.makedirs(output_folder, exist_ok=True)
        output_filename = f"signed_{uuid.uuid4().hex}.pdf"
        output_path = os.path.join(output_folder, output_filename)

        for page in reader.pages:
            writer.add_page(page)

        with open(output_path, "wb") as f_out:
            writer.write(f_out)

        # --- Update job status ---
        redis_conn.set(f"job_status:{job_id}", json.dumps({"status": "finished", "result": output_filename}))
        logger.info(f"PDF generated successfully: {output_filename}")
        return output_filename

    except Exception as e:
        logger.exception("Error applying signatures")
        redis_conn.set(f"job_status:{job_id}", json.dumps({"status": "failed", "result": str(e)}))
        raise