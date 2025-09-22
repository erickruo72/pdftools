import pandas as pd
import pdfplumber
import os
import xlsxwriter

def perform_pdf_to_excel(pdf_path, output_xlsx_path):
    """
    Extracts tables from a PDF and saves them to a structured, formatted Excel file
    with auto-fit columns and wrapped text.

    Args:
        pdf_path (str): The path to the input PDF file.
        output_xlsx_path (str): The path to the output Excel file.
    """
    all_data = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        all_data.extend(table)
    except Exception as e:
        print(f"Error extracting tables from PDF: {e}")
        return None

    if not all_data:
        print("No tables found in the PDF. Using fallback method.")
        # Fallback if no tables are found, but this time we still format the output
        rows = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    for line in text.split("\n"):
                        if ":" in line:
                            key, value = line.split(":", 1)
                            rows.append([key.strip(), value.strip()])
                        else:
                            rows.append([line.strip(), ""])
        if not rows:
            print("No text data found in the PDF.")
            return None
        df = pd.DataFrame(rows, columns=["Field", "Value"])
    else:
        df = pd.DataFrame(all_data)
        # Drop rows that are completely empty
        df.dropna(how='all', inplace=True)
        # Handle cases where the first row is a header
        if df.iloc[0].notna().any():
            df.columns = df.iloc[0]
            df = df[1:].reset_index(drop=True)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_xlsx_path), exist_ok=True)

    try:
        # Create a Pandas Excel writer using XlsxWriter as the engine.
        writer = pd.ExcelWriter(output_xlsx_path, engine='xlsxwriter')
        df.to_excel(writer, sheet_name='Sheet1', index=False, header=True)
        
        # Get the xlsxwriter workbook and worksheet objects
        workbook = writer.book
        worksheet = writer.sheets['Sheet1']

        # Add a cell format for text wrapping
        wrap_format = workbook.add_format({'text_wrap': True, 'valign': 'top'})

        # Apply the format to all columns and set autofit
        for i, col in enumerate(df.columns):
            max_len = max(df[col].astype(str).str.len().max(), len(str(col))) + 2
            worksheet.set_column(i, i, max_len, wrap_format)
            
        # Manually set a generous default row height for wrapped text
        # This is a good way to ensure the rows will accommodate the content
        worksheet.set_default_row(15) 

        # Close the Pandas Excel writer and save the Excel file.
        writer.close()
    
    except Exception as e:
        print(f"Error saving to Excel file with formatting: {e}")
        return None

    return output_xlsx_path