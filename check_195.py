"""Check page 195 tables"""
import pdfplumber

pdf_path = r"e:\NVidia api\ITC-Report-and-Accounts-2025.pdf"

with pdfplumber.open(pdf_path) as pdf:
    page = pdf.pages[194]  # Page 195 (0-indexed)
    tables = page.extract_tables()
    
    print(f"Page 195: {len(tables)} tables found\n")
    
    for idx, table in enumerate(tables[:10]):
        if table:
            print(f"Table {idx + 1}:")
            for row in table[:15]:
                print(f"  {row}")
            print()
