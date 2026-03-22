"""
Fast Financial Analyzer v2 - Better table parsing
"""

import os
import re
import pdfplumber
from typing import List, Dict


class FastFinancialAnalyzer:
    """Fast analyzer that only extracts key financial data."""
    
    # Key pages for ITC and similar Indian company reports (adjusted for ITC 2025)
    KEY_PAGES = [
        175, 176, 177, 178, 179, 180,  # Balance Sheet, P&L, Cash Flow
        194, 195, 196, 197, 198,  # Revenue breakdown, EPS, Dividend  
        199, 200, 201, 202, 203,  # EPS, Reserves
        214, 215, 216, 217, 218, 219, 220,  # Segment reporting
    ]
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.data = {
            'pages': 0,
            'tables': 0,
            'financials': {},
            'segments': []  # Store segment-wise data
        }
    
    def load(self):
        """Load and extract only key financial data."""
        print(f"  Fast extraction from: {self.file_path}")
        
        with pdfplumber.open(self.file_path) as pdf:
            self.data['pages'] = len(pdf.pages)
            
            # Process only key pages
            for page_num in self.KEY_PAGES:
                if page_num <= len(pdf.pages):
                    page = pdf.pages[page_num - 1]  # 0-indexed
                    
                    # Extract tables
                    tables = page.extract_tables()
                    for table in tables:
                        if table:
                            self.data['tables'] += 1
                            self._extract_financials(table, page_num)
        
        print(f"  Extracted {self.data['tables']} tables from key pages")
    
    def _extract_financials(self, table: list, page: int):
        """Extract financial data from a table with better row handling."""
        if not table or len(table) < 2:
            return
        
        # Flatten table to text for searching
        table_text = " ".join([str(c).lower() for row in table for c in row if c])
        
        # Check if this is a segment table (page 215 format)
        if page in [214, 215, 216, 217, 218, 219, 220]:
            self._extract_segments(table, page)
        
        # Find rows with keywords and get values from same or next row
        for i, row in enumerate(table):
            if not row:
                continue
            
            # Clean row - remove None values
            clean_row = [str(c).strip() if c else "" for c in row]
            row_text = " ".join(clean_row).lower()
            
            # Extract Revenue
            if 'revenue from operations' in row_text or 'gross revenue from sale' in row_text:
                # Look for value in this row or next row
                val = self._find_numeric_value(clean_row, min_value=1000)
                if not val and i + 1 < len(table):
                    next_row = [str(c).strip() if c else "" for c in table[i+1] if c]
                    val = self._find_numeric_value(next_row, min_value=1000)
                if val:
                    self.data['financials']['revenue'] = {
                        'value': val,
                        'page': page,
                        'label': 'Revenue from Operations'
                    }
            
            # Extract Net Profit
            if 'profit for the year' in row_text or 'profit for the period' in row_text:
                val = self._find_numeric_value(clean_row, min_value=100)
                if not val and i + 1 < len(table):
                    next_row = [str(c).strip() if c else "" for c in table[i+1] if c]
                    val = self._find_numeric_value(next_row, min_value=100)
                if val:
                    self.data['financials']['net_profit'] = {
                        'value': val,
                        'page': page,
                        'label': 'Profit for the Year'
                    }
            
            # Extract EPS - special handling
            if 'earnings per share' in row_text:
                # EPS is usually calculated, look for small numbers in subsequent rows
                for j in range(i+1, min(i+5, len(table))):
                    next_row = [str(c).strip() if c else "" for c in table[j] if c]
                    val = self._find_numeric_value(next_row, min_value=0.1, max_value=500)
                    if val:
                        self.data['financials']['eps'] = {
                            'value': val,
                            'page': page,
                            'label': 'Earnings Per Share'
                        }
                        break
            
            # Extract Dividend
            if 'dividend' in row_text and 'per share' in row_text:
                val = self._find_numeric_value(clean_row, min_value=0.1, max_value=50)
                if val:
                    self.data['financials']['dividend'] = {
                        'value': val,
                        'page': page,
                        'label': 'Dividend Per Share'
                    }
    
    def _extract_segments(self, table: list, page: int):
        """Extract segment-wise revenue from table."""
        if not table or len(table) < 1:  # Allow single-row tables
            return
        
        # Debug: print page number
        # print(f"Extracting segments from page {page}, table rows: {len(table)}")
        
        # Look for segment rows
        segment_keywords = ['fmcg', 'agri', 'paperboard', 'cigarette']
        
        for row in table:
            if not row or len(row) < 3:
                continue
            
            row_text = " ".join([str(c).lower() for c in row if c])
            
            # Debug
            # if 'fmcg' in row_text:
            #     print(f"  Found FMCG row on page {page}: {row[:3]}...")
            
            # Check if this is a segment row
            is_segment = any(kw in row_text for kw in segment_keywords)
            if not is_segment:
                continue
            
            # Get segment name from first cell
            segment_name = str(row[0]).strip() if row[0] else ""
            if len(segment_name) < 3:
                continue
            
            # Skip segment TOTAL rows only (not individual segments with "Total" in name)
            if segment_name.lower().strip() == 'segment total':
                continue
            
            # Extract numeric values (revenue)
            values = []
            for cell in row[1:]:
                val = self._parse_numeric(cell)
                if val and val > 100:  # Revenue should be substantial
                    values.append(val)
            
            # Debug
            # if values:
            #     print(f"    Values: {values[:3]}...")
            
            # If we have values, store segment data
            if len(values) >= 2:
                # Assume format: [Ext_2025, Inter_2025, Total_2025, Ext_2024, ...]
                # or [Ext_2025, Total_2025, Ext_2024, Total_2024]
                revenue_2025 = values[0] if len(values) > 0 else None
                revenue_2024 = values[1] if len(values) > 1 else None
                
                # If we have 6+ values, it's the full format
                if len(values) >= 6:
                    revenue_2025 = values[2]  # Total 2025
                    revenue_2024 = values[5]  # Total 2024
                elif len(values) >= 4:
                    revenue_2025 = values[1]  # Total 2025
                    revenue_2024 = values[3]  # Total 2024
                
                if revenue_2025:
                    self.data['segments'].append({
                        'segment': segment_name,
                        'revenue_2025': revenue_2025,
                        'revenue_2024': revenue_2024,
                        'page': page
                    })
    
    def _find_numeric_value(self, cells: list, min_value: float = 0, max_value: float = float('inf')) -> float:
        """Find first valid numeric value in cells."""
        for cell in cells:
            val = self._parse_numeric(cell)
            if val and min_value <= val <= max_value:
                return val
        return None
    
    def _parse_numeric(self, value) -> float:
        """Parse numeric value from string."""
        if not value:
            return None
        
        text = str(value).strip()
        
        # Remove currency symbols and commas
        text = re.sub(r'[₹$,]', '', text)
        text = text.strip()
        
        # Handle empty or dash
        if not text or text == "-" or text.lower() == "nil":
            return None
        
        # Handle parentheses for negatives
        if text.startswith('(') and text.endswith(')'):
            text = '-' + text[1:-1]
        
        try:
            return float(text)
        except ValueError:
            return None
    
    def get_financials(self) -> dict:
        """Get extracted financial data."""
        return self.data['financials']
    
    def get_segments(self) -> list:
        """Get segment-wise revenue data."""
        return self.data['segments']
    
    def query(self, question: str) -> str:
        """Simple query response based on extracted data."""
        question_lower = question.lower()
        financials = self.get_financials()
        
        if 'revenue' in question_lower and 'revenue' in financials:
            data = financials['revenue']
            return f"""
================================================================================
QUERY: {question}
================================================================================

1. DIRECT ANSWER:
   ₹{data['value']:.2f} Crores

2. SUPPORTING EVIDENCE:
   Page {data['page']}, {data['label']}

3. INFERENCE:
   None

4. CONFIDENCE LEVEL: High
================================================================================
"""
        
        if 'profit' in question_lower and 'net_profit' in financials:
            data = financials['net_profit']
            return f"""
================================================================================
QUERY: {question}
================================================================================

1. DIRECT ANSWER:
   ₹{data['value']:.2f} Crores

2. SUPPORTING EVIDENCE:
   Page {data['page']}, {data['label']}

3. INFERENCE:
   None

4. CONFIDENCE LEVEL: High
================================================================================
"""
        
        if 'eps' in question_lower and 'eps' in financials:
            data = financials['eps']
            return f"""
================================================================================
QUERY: {question}
================================================================================

1. DIRECT ANSWER:
   ₹{data['value']:.2f}

2. SUPPORTING EVIDENCE:
   Page {data['page']}, {data['label']}

3. INFERENCE:
   None

4. CONFIDENCE LEVEL: High
================================================================================
"""
        
        if 'dividend' in question_lower and 'dividend' in financials:
            data = financials['dividend']
            return f"""
================================================================================
QUERY: {question}
================================================================================

1. DIRECT ANSWER:
   ₹{data['value']:.2f} per share

2. SUPPORTING EVIDENCE:
   Page {data['page']}, {data['label']}

3. INFERENCE:
   None

4. CONFIDENCE LEVEL: High
================================================================================
"""
        
        return f"""
================================================================================
QUERY: {question}
================================================================================

1. DIRECT ANSWER:
   Data not found in quick extraction. Try full analysis mode.

2. SUPPORTING EVIDENCE:
   N/A

3. INFERENCE:
   None

4. CONFIDENCE LEVEL: Low
================================================================================
"""


if __name__ == "__main__":
    pdf_path = r"e:\NVidia api\ITC-Report-and-Accounts-2025.pdf"
    
    print("="*60)
    print("Fast Financial Analyzer v2")
    print("="*60)
    
    analyzer = FastFinancialAnalyzer(pdf_path)
    analyzer.load()
    
    print("\nExtracted Financials:")
    for key, data in analyzer.get_financials().items():
        print(f"  {data['label']}: ₹{data['value']:.2f} Cr (Page {data['page']})")
