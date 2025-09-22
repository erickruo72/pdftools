import os
import tempfile
import pdfkit

def perform_html_to_pdf(html_content=None, html_path=None, output_path=None):
    """
    Convert HTML content or file to PDF.
    Provide either html_content (string) or html_path (file path), plus output_path.
    """
    if html_content is None and html_path is None:
        raise ValueError("Provide html_content or html_path")
    pdfkit.from_string(html_content, output_path) if html_content else pdfkit.from_file(html_path, output_path)
    return os.path.basename(output_path)
