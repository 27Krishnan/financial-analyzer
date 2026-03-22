"""Debug - check what tables contain"""
import pdfplumber

pdf_path = r"e:\NVidia api\ITC-Report-and-Accounts-2025.pdf"

# Check specific pages
pages_to_check = [195, 198, 200]

with pdfplumber.open(pdf_path) as pdf:
    for page_num in pages_to_check:
        page = pdf.pages[page_num - 1]
        tables = page.extract_tables()
        
        print(f"\n{'='*60}")
        print(f"PAGE {page_num}")
        print(f"{'='*60}")
        
        for idx, table in enumerate(tables[:5]):
            if table:
                print(f"\nTable {idx + 1}:")
                for row in table[:10]:
                    if row:
                        # Check if row has relevant keywords
                        row_text = " ".join([str(c).lower() for c in row if c])
                        if any(kw in row_text for kw in ['revenue', 'profit', 'earnings', 'dividend', 'eps']):
                            print(f"  ✓ {row}")
                        else:
                            print(f"    {row}")
