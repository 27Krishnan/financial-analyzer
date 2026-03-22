"""Debug script to examine specific pages in the PDF"""
import pdfplumber

pdf_path = r"e:\NVidia api\ITC-Report-and-Accounts-2025.pdf"

# Check pages 195, 215, 216, 217 for segment data
pages_to_check = [194, 195, 214, 215, 216, 217, 218, 219, 220]  # 0-indexed

with pdfplumber.open(pdf_path) as pdf:
    for page_num in pages_to_check:
        if page_num < len(pdf.pages):
            page = pdf.pages[page_num]
            text = page.extract_text()
            tables = page.extract_tables()
            
            print(f"\n{'='*80}")
            print(f"PAGE {page_num + 1}")
            print(f"{'='*80}")
            
            # Print text snippet
            if text:
                print(f"\nTEXT SNIPPET:\n{text[:1500]}...")
            
            # Print tables
            if tables:
                print(f"\nTABLES FOUND: {len(tables)}")
                for idx, table in enumerate(tables):
                    print(f"\n--- Table {idx + 1} ---")
                    if table:
                        for row in table[:15]:  # First 15 rows
                            print(row)
            print()
