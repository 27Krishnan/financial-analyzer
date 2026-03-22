"""Test extraction function directly"""
import sys
sys.path.insert(0, r'e:\NVidia api')

from FinancialAnalyzer_v2 import FinancialAnalyzer

pdf_path = r"e:\NVidia api\ITC-Report-and-Accounts-2025.pdf"

analyzer = FinancialAnalyzer(pdf_path)
analyzer.load()

# Manually test the extraction
print("\n" + "="*60)
print("MANUAL EXTRACTION TEST")
print("="*60)

segments = []
for table_info in analyzer.data["tables"]:
    table = table_info["data"]
    page = table_info["page"]
    table_text = " ".join([str(c).lower() for row in table for c in row])
    
    # Check if this is a segment-related table
    is_segment_table = (
        page in range(214, 225) or
        any(seg in table_text for seg in ["fmcg", "agri business", "paperboards"]) or
        ("segment" in table_text and "external" in table_text)
    )
    
    if is_segment_table and len(table) > 0:
        # Call the parsing function
        extracted = analyzer.financial_extractor._parse_segment_revenue_table(table, page)
        if extracted:
            print(f"Page {page}, Table {table_info['table_index']+1}: Found {len(extracted)} segments")
            for seg in extracted:
                print(f"  - {seg}")
            segments.extend(extracted)

print(f"\nTotal segments found: {len(segments)}")
