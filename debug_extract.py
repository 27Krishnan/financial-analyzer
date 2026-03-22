"""Debug segment extraction"""
import sys
sys.path.insert(0, r'e:\NVidia api')

from FinancialAnalyzer_v2 import FinancialAnalyzer

pdf_path = r"e:\NVidia api\ITC-Report-and-Accounts-2025.pdf"

analyzer = FinancialAnalyzer(pdf_path)
analyzer.load()

# Check tables on page 215
print("\n" + "="*60)
print("TABLES ON PAGE 215")
print("="*60)

count = 0
for table_info in analyzer.data["tables"]:
    if table_info["page"] == 215:
        count += 1
        table = table_info["data"]
        if table:
            first_row = table[0] if table else []
            row_text = " ".join([str(c) for c in first_row]).lower() if first_row else ""
            
            if any(seg in row_text for seg in ["fmcg", "agri", "paperboard"]):
                print(f"Table {table_info['table_index'] + 1}: {first_row}")
                
                # Test the parsing logic
                segment_name = str(first_row[0]).strip() if first_row else ""
                segment_name_lower = segment_name.lower()
                
                valid_segments = [
                    "fmcg - cigarettes", "fmcg - others", "fmcg - total",
                    "agri business", "paperboards", "paper and packaging",
                    "others"
                ]
                
                is_valid = any(seg in segment_name_lower for seg in valid_segments)
                print(f"  -> segment_name: '{segment_name}'")
                print(f"  -> is_valid: {is_valid}")

print(f"\nTotal tables on page 215: {count}")
