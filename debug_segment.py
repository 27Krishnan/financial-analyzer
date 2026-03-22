"""Debug script to examine segment tables"""
import pdfplumber

pdf_path = r"e:\NVidia api\ITC-Report-and-Accounts-2025.pdf"

# Check pages 214, 215 for segment data (0-indexed)
pages_to_check = [214, 215]

with pdfplumber.open(pdf_path) as pdf:
    for page_num in pages_to_check:
        if page_num < len(pdf.pages):
            page = pdf.pages[page_num]
            tables = page.extract_tables()
            
            print(f"\n{'='*80}")
            print(f"PAGE {page_num + 1}")
            print(f"{'='*80}")
            
            if tables:
                print(f"\nTABLES FOUND: {len(tables)}")
                for idx, table in enumerate(tables):
                    print(f"\n--- Table {idx + 1} ---")
                    if table:
                        for row in table[:20]:
                            print(row)
                            
                            if row and len(row) > 0:
                                row_text = " ".join([str(c) for c in row]).lower()
                                if "fmcg" in row_text or "agri" in row_text or "paperboard" in row_text:
                                    print(f"  ^^^ SEGMENT ROW DETECTED!")
                                    values = []
                                    for cell in row[1:]:
                                        if cell:
                                            try:
                                                val = float(str(cell).replace(',', '').replace('–', '').replace('-', '').strip())
                                                values.append(val)
                                            except:
                                                pass
                                    print(f"  VALUES: {values}")
