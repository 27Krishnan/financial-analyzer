"""Direct test of segment extraction"""
import sys
sys.path.insert(0, r'e:\NVidia api')

from FinancialAnalyzer_v2 import FinancialAnalyzer

pdf_path = r"e:\NVidia api\ITC-Report-and-Accounts-2025.pdf"

analyzer = FinancialAnalyzer(pdf_path)
analyzer.load()

# Check ALL tables on page 215
print("\n" + "="*60)
print("ALL TABLES ON PAGE 215")
print("="*60)

for table_info in analyzer.data["tables"]:
    if table_info["page"] == 215:
        print(f"\nTable {table_info['table_index'] + 1}:")
        table = table_info["data"]
        if table:
            for row in table[:5]:
                print(f"  {row}")

# Now manually test the parsing
print("\n" + "="*60)
print("MANUAL PARSING TEST")
print("="*60)

for table_info in analyzer.data["tables"]:
    if table_info["page"] == 215 and table_info["table_index"] in [1, 2, 3]:  # Tables 2, 3, 4 (0-indexed 1, 2, 3)
        table = table_info["data"]
        print(f"\nTable {table_info['table_index'] + 1}:")
        
        for row in table:
            if len(row) < 3:
                continue
            
            segment_name = str(row[0]).strip() if row else ""
            segment_name_lower = segment_name.lower()
            
            valid_segments = [
                "fmcg - cigarettes", "fmcg - others", "fmcg - total",
                "agri business", "paperboards", "paper and packaging",
                "others"
            ]
            
            is_valid = any(seg in segment_name_lower for seg in valid_segments)
            
            if is_valid:
                print(f"  MATCH: {segment_name}")
                
                # Extract values
                values = []
                for cell in row[1:]:
                    val = analyzer.financial_extractor._parse_numeric(cell)
                    if val is not None:
                        values.append(val)
                
                print(f"  VALUES: {values}")
