"""Quick test for segment tables"""
import pdfplumber

pdf_path = r"e:\NVidia api\ITC-Report-and-Accounts-2025.pdf"

with pdfplumber.open(pdf_path) as pdf:
    page = pdf.pages[214]  # Page 215 (0-indexed)
    tables = page.extract_tables()
    
    print(f"Page 215: {len(tables)} tables found\n")
    
    for idx, table in enumerate(tables[:25]):
        if table and len(table) >= 1:
            first_row = table[0] if table else []
            row_text = " ".join([str(c) for c in first_row]).lower() if first_row else ""
            
            if any(seg in row_text for seg in ["fmcg", "agri", "paperboard"]):
                print(f"Table {idx + 1}: {first_row}")
