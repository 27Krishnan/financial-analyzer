"""Test segment extraction"""
import sys
sys.path.insert(0, r'e:\NVidia api')

from FinancialAnalyzer_v2 import FinancialAnalyzer

pdf_path = r"e:\NVidia api\ITC-Report-and-Accounts-2025.pdf"

analyzer = FinancialAnalyzer(pdf_path)
analyzer.load()

# Debug: Check what tables are on page 215
print("\n" + "="*60)
print("DEBUG: Tables on pages 214-220")
print("="*60)

for table_info in analyzer.data["tables"]:
    page = table_info["page"]
    if page in range(214, 221):
        table = table_info["data"]
        table_text = " ".join([str(c).lower() for row in table for c in row])
        
        print(f"\nPage {page}, Table {table_info['table_index'] + 1}:")
        print(f"  Text snippet: {table_text[:100]}...")
        
        # Check conditions
        is_segment_page = page in range(214, 225)
        has_fmcg_agri = "fmcg" in table_text and "agri" in table_text
        has_segment_external = "segment" in table_text and "external" in table_text
        has_paperboards = "paperboards" in table_text
        
        print(f"  is_segment_page: {is_segment_page}")
        print(f"  has_fmcg_agri: {has_fmcg_agri}")
        print(f"  has_segment_external: {has_segment_external}")
        print(f"  has_paperboards: {has_paperboards}")
        
        # Check first few rows
        if table:
            for i, row in enumerate(table[:5]):
                print(f"  Row {i}: {row}")

# Now try extraction
print("\n" + "="*60)
print("EXTRACTING SEGMENT REVENUE")
print("="*60)

segments = analyzer.financial_extractor.extract_segment_revenue()
print(f"\nFound {len(segments)} segments:")
for seg in segments:
    print(f"  {seg}")
