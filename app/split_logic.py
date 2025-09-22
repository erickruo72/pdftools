import os
import zipfile
import shutil
import tempfile
import uuid
from PyPDF2 import PdfReader, PdfWriter

def split_job(file_path, option, sp, ep):
    """
    Splits a PDF file based on the given option.
    Returns the filename of the resulting file (single PDF or ZIP).
    """
    try:
        reader = PdfReader(file_path)
        total_pages = len(reader.pages)
        output_folder = os.path.dirname(file_path)
        base_name = os.path.splitext(os.path.basename(file_path))[0]

        # Handle "all" pages split
        if option == 'all':
            temp_dir = tempfile.mkdtemp()
            try:
                # Split all pages into a temporary directory
                for i, page in enumerate(reader.pages):
                    writer = PdfWriter()
                    writer.add_page(page)
                    output_filename = os.path.join(temp_dir, f"{base_name}_page_{i + 1}.pdf")
                    with open(output_filename, "wb") as f:
                        writer.write(f)

                # Then, create a single ZIP file from the temporary folder
                zip_filename = f"{base_name}_split_{uuid.uuid4().hex}.zip"
                zip_path = os.path.join(output_folder, zip_filename)

                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for f_name in sorted(os.listdir(temp_dir)):
                        f_path = os.path.join(temp_dir, f_name)
                        zipf.write(f_path, arcname=f_name)
                
                return zip_filename
            finally:
                shutil.rmtree(temp_dir)
        
        # Handle "range" pages split
        elif option == 'range':
            sp_int, ep_int = int(sp), int(ep)
            if sp_int < 1 or ep_int > total_pages or sp_int > ep_int:
                raise ValueError("Page range is out of bounds or invalid.")

            writer = PdfWriter()
            # PyPDF2 pages are 0-indexed, so we subtract 1 from user input
            for page_num in range(sp_int - 1, ep_int):
                writer.add_page(reader.pages[page_num])
            
            output_filename = f"{base_name}_pages_{sp_int}_to_{ep_int}_{uuid.uuid4().hex}.pdf"
            output_path = os.path.join(output_folder, output_filename)
            
            with open(output_path, 'wb') as f:
                writer.write(f)
            
            return output_filename

    except (ValueError, IndexError) as e:
        return f"Error: Invalid page range. Details: {e}"
    except Exception as e:
        return f"An unexpected error occurred during splitting: {str(e)}"
    finally:
        # Clean up the original uploaded file
        if os.path.exists(file_path):
            os.remove(file_path)