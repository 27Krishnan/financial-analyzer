"""
Enhanced Financial Document Analyzer
Improved table extraction for Indian financial reports (ITC, etc.)
"""

import os
import re
import json
import pdfplumber
from typing import Optional, List, Dict
import requests


# ============================================================================
# CONFIGURATION
# ============================================================================
API_KEY = os.getenv("NVIDIA_API_KEY", "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")
NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"


# ============================================================================
# INDIAN FINANCIAL TERMS - Enhanced
# ============================================================================
FINANCIAL_TERMS = {
    "revenue": [
        "revenue from operations", "gross revenue", "total revenue", "net sales",
        "revenue", "sales", "turnover", "operating revenue", "income from operations"
    ],
    "profit": [
        "profit for the year", "net profit", "profit for the period", "profit/(loss)",
        "profit after tax", "pat", "net income", "earnings", "bottom line"
    ],
    "ebitda": [
        "ebitda", "earnings before interest", "earnings before tax", "operating profit",
        "profit before tax", "pbt", "ebit"
    ],
    "expenses": [
        "expenses", "cost of materials", "operating expenses", "employee benefit",
        "finance costs", "depreciation", "total expenses"
    ],
    "assets": [
        "assets", "non-current assets", "current assets", "property plant",
        "intangible assets", "investments", "trade receivables", "cash and cash"
    ],
    "equity": [
        "equity", "share capital", "reserves", "surplus", "retained earnings",
        "other equity", "total equity", "shareholders funds"
    ],
    "liabilities": [
        "liabilities", "borrowings", "trade payables", "provisions", "deferred tax",
        "other financial liabilities"
    ],
    "cash_flow": [
        "cash flow", "cash generated", "operating activities", "investing activities",
        "financing activities", "net cash"
    ],
    "segment": [
        "segment", "business segment", "segment revenue", "segment result",
        "external", "internal", "unallocated", "corporate"
    ],
    "dividend": [
        "dividend", "dividend per share", "equity dividend", "interim dividend",
        "final dividend", "dividend distribution"
    ],
    "eps": [
        "earnings per share", "eps", "basic eps", "diluted eps"
    ]
}

# Indian business segments
BUSINESS_SEGMENTS = [
    "fmcg", "cigarette", "agri", "paperboard", "paper", "packaging",
    "hotel", "itc", "food", "personal care", "stationery", "education",
    "safety matches", "incense sticks", "agarbatti", "branded packs"
]


# ============================================================================
# PDF EXTRACTOR - Enhanced
# ============================================================================
class PDFExtractor:
    """Extract text and tables from PDF documents with better structure detection."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.pages_data = []
        self.tables_data = []
        self.full_text = ""
        
    def extract(self) -> dict:
        """Extract all content from PDF."""
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"PDF not found: {self.file_path}")
            
        print(f"  Extracting from {self.file_path}...")
        
        with pdfplumber.open(self.file_path) as pdf:
            total_pages = len(pdf.pages)
            
            for page_num, page in enumerate(pdf.pages, 1):
                print(f"  Processing page {page_num}/{total_pages}...")
                
                # Extract text
                text = page.extract_text() or ""
                self.full_text += f"\n[PAGE {page_num}]\n{text}"
                
                self.pages_data.append({
                    "page": page_num,
                    "text": text,
                    "tables": []
                })
                
                # Extract tables with better detection
                tables = page.extract_tables()
                for table_idx, table in enumerate(tables):
                    if table and len(table) >= 1:  # Keep single-row tables too (segment data)
                        table_data = self._parse_table(table)
                        
                        # Classify table type
                        table_type = self._classify_table(table_data, text)
                        
                        self.tables_data.append({
                            "page": page_num,
                            "table_index": table_idx,
                            "data": table_data,
                            "raw": table,
                            "type": table_type
                        })
                        self.pages_data[-1]["tables"].append(table_data)
                        
        print(f"  Extraction complete: {len(self.tables_data)} tables found")
        
        return {
            "text": self.full_text,
            "pages": self.pages_data,
            "tables": self.tables_data
        }
    
    def _parse_table(self, table: list) -> list:
        """Parse table into structured format."""
        parsed = []
        for row in table:
            if row:
                parsed.append([cell.strip() if cell else "" for cell in row])
        return parsed
    
    def _classify_table(self, table_data: list, page_text: str) -> str:
        """Classify table type based on content."""
        if not table_data:
            return "unknown"
        
        table_text = " ".join([str(cell).lower() for row in table_data for cell in row])
        page_text_lower = page_text.lower()
        
        # Check for segment-related keywords
        if any(seg in table_text for seg in BUSINESS_SEGMENTS):
            return "segment"
        
        # Check for financial statement types
        if "balance sheet" in page_text_lower or "statement of assets" in table_text:
            return "balance_sheet"
        
        if "profit and loss" in page_text_lower or "statement of profit" in table_text:
            return "profit_loss"
        
        if "cash flow" in page_text_lower:
            return "cash_flow"
        
        if "segment" in table_text or "external" in table_text or "internal" in table_text:
            return "segment_result"
        
        if "revenue" in table_text or "sales" in table_text:
            return "revenue"
        
        return "financial"


# ============================================================================
# FINANCIAL DATA EXTRACTOR - Enhanced
# ============================================================================
class FinancialDataExtractor:
    """Extract specific financial data from parsed tables."""
    
    def __init__(self, tables_data: list, pages_data: list):
        self.tables_data = tables_data
        self.pages_data = pages_data
        
    def extract_all_metrics(self) -> dict:
        """Extract all key financial metrics."""
        return {
            "revenue": self.extract_revenue(),
            "profit": self.extract_profit(),
            "segment_revenue": self.extract_segment_revenue(),
            "segment_profit": self.extract_segment_profit(),
            "balance_sheet": self.extract_balance_sheet(),
            "cash_flow": self.extract_cash_flow(),
            "eps_dividend": self.extract_eps_dividend()
        }
    
    def extract_revenue(self) -> dict:
        """Extract revenue data with Standalone and Consolidated."""
        result = {
            "standalone": None,
            "consolidated": None,
            "details": []
        }
        
        for table_info in self.tables_data:
            table = table_info["data"]
            page = table_info["page"]
            
            # Look for revenue tables
            for row_idx, row in enumerate(table):
                row_text = " ".join([str(c).lower() for c in row]).strip()
                
                # Check for revenue keywords
                if any(kw in row_text for kw in FINANCIAL_TERMS["revenue"]):
                    # Check if standalone or consolidated
                    is_standalone = "standalone" in row_text or (
                        page < 200 and "consolidated" not in row_text
                    )
                    is_consolidated = "consolidated" in row_text or (
                        page >= 200 and "standalone" not in row_text
                    )
                    
                    # Try to extract value from same row or next column
                    value = self._extract_numeric_value(row)
                    
                    if value:
                        detail = {
                            "page": page,
                            "row": row_idx,
                            "label": row[0] if row else "Unknown",
                            "value": value
                        }
                        
                        if is_standalone and not result["standalone"]:
                            result["standalone"] = value
                        elif is_consolidated and not result["consolidated"]:
                            result["consolidated"] = value
                        
                        result["details"].append(detail)
        
        return result
    
    def extract_segment_revenue(self) -> list:
        """Extract segment-wise revenue breakdown."""
        segments = []

        for table_info in self.tables_data:
            table = table_info["data"]
            page = table_info["page"]

            # Look for segment tables (pages 195 for product-wise, 214-225 for Segment Reporting)
            table_text = " ".join([str(c).lower() for row in table for c in row])

            # Check if this is a segment-related table
            is_segment_table = (
                page in [195, 196] or  # Product-wise revenue (Gross Revenue from sale of products)
                page in range(214, 225) or  # Segment reporting pages
                any(seg in table_text for seg in ["fmcg", "agri business", "paperboards"]) or
                ("segment" in table_text and "external" in table_text)
            )

            if is_segment_table and len(table) > 0:
                extracted = self._parse_segment_revenue_table(table, page)
                if extracted:
                    segments.extend(extracted)

        return segments

    def _parse_segment_revenue_table(self, table: list, page: int) -> list:
        """Parse segment revenue table from page 215 or page 195 format."""
        segments = []

        if not table or len(table) < 1:  # Allow single-row tables
            return segments

        for row in table:
            if len(row) < 2:
                continue

            row_text = " ".join([str(c) for c in row]).strip()
            row_text_lower = row_text.lower()

            # Check if row starts with a segment name (first cell)
            segment_name = str(row[0]).strip() if row else ""
            segment_name_lower = segment_name.lower()

            # Valid segment names
            valid_segments = [
                "fmcg - cigarettes", "fmcg - others", "fmcg - total",
                "agri business", "paperboards", "paper and packaging",
                "others", "branded packaged food", "unmanufactured tobacco"
            ]

            # Check if this row contains a valid segment
            is_valid = any(seg in segment_name_lower for seg in valid_segments)
            if not is_valid:
                continue

            # Skip if segment name is too short or looks like a header
            if len(segment_name) < 3 or segment_name.lower() in ["total", "segment", "external", "gross revenue"]:
                continue

            # Extract numeric values from the row
            values = []
            for cell in row[1:]:
                val = self._parse_numeric(cell)
                if val is not None:
                    values.append(val)

            # Handle page 195 format (product-wise revenue)
            # Format: [Product Name, FY2025, FY2024]
            if page in [195, 196] and len(values) >= 2:
                segments.append({
                    "segment": segment_name,
                    "standalone": values[0],  # FY 2025
                    "standalone_prior": values[1],  # FY 2024
                    "page": page
                })
                continue

            # Handle page 215 format (segment reporting with External/Inter-segment/Total)
            # We expect at least 2 values (2025 Total, 2024 Total)
            # Revenue format varies: 
            #   [Ext_25, Total_25, Ext_24, Total_24] - 4 values (when no inter-segment)
            #   [Ext_25, Inter_25, Total_25, Ext_24, Inter_24, Total_24] - 6 values
            if len(values) >= 2:
                # Distinguish Revenue from Assets/Liabilities tables
                # Revenue: External ≈ Total (small inter-segment)
                # Assets/Liabilities: Assets >> Liabilities
                is_revenue = False
                
                if len(values) >= 6:
                    # Revenue format: [Ext_25, Inter_25, Total_25, Ext_24, Inter_24, Total_24]
                    # For revenue, Total ≈ External + Inter-segment
                    # Check if values[2] (Total_25) is close to values[0] + values[1]
                    expected_total_25 = values[0] + values[1]
                    actual_total_25 = values[2]
                    if abs(expected_total_25 - actual_total_25) < actual_total_25 * 0.1:  # Within 10%
                        is_revenue = True
                elif len(values) >= 4:
                    # Simplified format: [Ext_25, Total_25, Ext_24, Total_24]
                    # For revenue, Total >= External
                    # For Assets/Liabilities, typically Assets > Liabilities
                    if values[1] >= values[0] * 0.9:  # Total is at least 90% of External
                        is_revenue = True
                
                if not is_revenue:
                    continue  # Skip non-revenue tables
                    
                if len(values) >= 6:
                    # Full format with inter-segment
                    total_2025 = values[2]  # Index 2 is Total 2025
                    total_2024 = values[5]  # Index 5 is Total 2024
                elif len(values) >= 4:
                    # Simplified format (no inter-segment)
                    total_2025 = values[1]  # Index 1 is Total 2025
                    total_2024 = values[3]  # Index 3 is Total 2024
                else:
                    # Fallback
                    total_2025 = values[0]
                    total_2024 = values[1] if len(values) > 1 else None

                segments.append({
                    "segment": segment_name,
                    "standalone": total_2025,  # 2025 Total
                    "standalone_prior": total_2024,  # 2024 Total
                    "page": page
                })

        return segments
    
    def _parse_segment_table(self, table: list, page: int) -> list:
        """Parse a segment revenue table."""
        segments = []
        
        if not table or len(table) < 2:
            return segments
        
        headers = [str(h).strip().lower() if h else "" for h in table[0]]
        
        # Identify columns
        segment_col = 0
        standalone_cols = []
        consolidated_cols = []
        external_col = -1
        internal_col = -1
        
        for idx, header in enumerate(headers):
            if "standalone" in header:
                standalone_cols.append(idx)
            elif "consolidated" in header:
                consolidated_cols.append(idx)
            elif "external" in header:
                external_col = idx
            elif "internal" in header:
                internal_col = idx
        
        # Process data rows
        for row in table[1:]:
            if len(row) <= segment_col:
                continue
            
            segment_name = str(row[segment_col]).strip()
            
            # Skip totals, notes, empty rows
            skip_keywords = ["total", "subtotal", "note", "notes", "see", "refer", ""]
            if segment_name.lower() in skip_keywords or not segment_name:
                continue
            
            # Check if it's a business segment
            is_segment = any(seg in segment_name.lower() for seg in BUSINESS_SEGMENTS)
            if not is_segment and len(segment_name) < 3:
                continue
            
            # Extract values
            standalone_val = None
            consolidated_val = None
            
            # Try to find numeric values in the row
            numeric_cols = []
            for idx, cell in enumerate(row):
                val = self._parse_numeric(cell)
                if val is not None:
                    numeric_cols.append((idx, val))
            
            # Assign values based on column positions
            if len(numeric_cols) >= 1:
                # First numeric is often standalone/current year
                standalone_val = numeric_cols[0][1]
                
                if len(numeric_cols) >= 2:
                    # Second numeric could be consolidated/previous year
                    consolidated_val = numeric_cols[1][1]
            
            if segment_name and (standalone_val or consolidated_val):
                segments.append({
                    "segment": segment_name,
                    "standalone": standalone_val,
                    "consolidated": consolidated_val,
                    "page": page,
                    "external": None,  # Could be extracted if external_col found
                    "internal": None
                })
        
        return segments
    
    def extract_profit(self) -> dict:
        """Extract profit data."""
        result = {
            "net_profit": None,
            "operating_profit": None,
            "profit_before_tax": None,
            "details": []
        }
        
        for table_info in self.tables_data:
            table = table_info["data"]
            page = table_info["page"]
            
            for row_idx, row in enumerate(table):
                row_text = " ".join([str(c).lower() for c in row]).strip()
                
                if any(kw in row_text for kw in FINANCIAL_TERMS["profit"]):
                    value = self._extract_numeric_value(row)
                    if value:
                        result["details"].append({
                            "page": page,
                            "label": row[0] if row else "Unknown",
                            "value": value
                        })
                        
                        if "net profit" in row_text and not result["net_profit"]:
                            result["net_profit"] = value
                        elif "operating profit" in row_text and not result["operating_profit"]:
                            result["operating_profit"] = value
        
        return result
    
    def extract_segment_profit(self) -> list:
        """Extract segment-wise profit/loss."""
        profits = []
        
        for table_info in self.tables_data:
            table = table_info["data"]
            page = table_info["page"]
            
            table_text = " ".join([str(c).lower() for row in table for c in row])
            
            # Look for segment result tables with profit/loss
            if ("segment result" in table_text or "segment profit" in table_text or
                any(seg in table_text for seg in BUSINESS_SEGMENTS)):
                
                for row in table:
                    row_text = " ".join([str(c).lower() for c in row])
                    
                    if any(kw in row_text for kw in ["profit", "loss", "result"]):
                        segment_name = row[0] if row else ""
                        
                        # Extract numeric values (could be positive or negative)
                        values = []
                        for cell in row[1:]:
                            val = self._parse_numeric(cell)
                            if val is not None:
                                values.append(val)
                        
                        if segment_name and values:
                            profits.append({
                                "segment": segment_name,
                                "profit_loss": values[0] if values else None,
                                "page": page
                            })
        
        return profits
    
    def extract_balance_sheet(self) -> dict:
        """Extract Balance Sheet data."""
        result = {
            "standalone": {"assets": {}, "liabilities": {}, "equity": {}},
            "consolidated": {"assets": {}, "liabilities": {}, "equity": {}},
            "pages": []
        }
        
        for table_info in self.tables_data:
            table = table_info["data"]
            page = table_info["page"]
            table_type = table_info.get("type", "")
            
            if table_type == "balance_sheet" or "balance sheet" in str(table).lower():
                # Determine standalone vs consolidated
                table_text = " ".join([str(c).lower() for row in table for c in row])
                is_consolidated = "consolidated" in table_text
                
                category = "consolidated" if is_consolidated else "standalone"
                
                # Extract line items
                for row in table:
                    if len(row) >= 2:
                        label = str(row[0]).strip().lower()
                        value = self._parse_numeric(row[-1])  # Last column usually has value
                        
                        if value:
                            # Categorize
                            if any(kw in label for kw in FINANCIAL_TERMS["assets"]):
                                result[category]["assets"][label] = value
                            elif any(kw in label for kw in FINANCIAL_TERMS["equity"]):
                                result[category]["equity"][label] = value
                            elif any(kw in label for kw in FINANCIAL_TERMS["liabilities"]):
                                result[category]["liabilities"][label] = value
                
                result["pages"].append(page)
        
        return result
    
    def extract_cash_flow(self) -> dict:
        """Extract Cash Flow data."""
        result = {
            "operating": None,
            "investing": None,
            "financing": None,
            "net_change": None
        }
        
        for table_info in self.tables_data:
            table = table_info["data"]
            table_text = " ".join([str(c).lower() for row in table for c in row])
            
            if "cash flow" in table_text:
                for row in table:
                    row_text = " ".join([str(c).lower() for c in row])
                    value = self._extract_numeric_value(row)
                    
                    if "operating" in row_text and value:
                        result["operating"] = value
                    elif "investing" in row_text and value:
                        result["investing"] = value
                    elif "financing" in row_text and value:
                        result["financing"] = value
                    elif "net cash" in row_text and value:
                        result["net_change"] = value
        
        return result
    
    def extract_eps_dividend(self) -> dict:
        """Extract EPS and Dividend data."""
        result = {
            "eps_basic": None,
            "eps_diluted": None,
            "dividend_per_share": None
        }
        
        for table_info in self.tables_data:
            table = table_info["data"]
            
            for row in table:
                row_text = " ".join([str(c).lower() for c in row])
                
                # Look for EPS
                if "basic" in row_text and "eps" in row_text:
                    value = self._extract_numeric_value(row)
                    if value:
                        result["eps_basic"] = value
                
                if "diluted" in row_text and "eps" in row_text:
                    value = self._extract_numeric_value(row)
                    if value:
                        result["eps_diluted"] = value
                
                # Look for dividend
                if "dividend" in row_text and "per share" in row_text:
                    value = self._extract_numeric_value(row)
                    if value:
                        result["dividend_per_share"] = value
        
        return result
    
    def _extract_numeric_value(self, row: list) -> Optional[float]:
        """Extract numeric value from a row."""
        for cell in row[1:]:  # Skip first column (usually label)
            value = self._parse_numeric(cell)
            if value is not None:
                return value
        return None
    
    def _parse_numeric(self, value) -> Optional[float]:
        """Parse numeric value from string, handling Indian format."""
        if not value:
            return None
        
        text = str(value).strip()
        
        # Remove currency symbols and commas
        text = re.sub(r'[₹$,]', '', text)
        text = text.strip()
        
        # Handle empty or dash
        if not text or text == "-" or text == "nil":
            return None
        
        # Handle parentheses for negatives
        if text.startswith('(') and text.endswith(')'):
            text = '-' + text[1:-1]
        
        # Handle Indian number format (sometimes uses , differently)
        # Remove spaces within numbers
        text = re.sub(r'(\d)\s+(\d)', r'\1\2', text)
        
        try:
            return float(text)
        except ValueError:
            return None


# ============================================================================
# MAIN ANALYZER
# ============================================================================
class FinancialAnalyzer:
    """Main analyzer with enhanced extraction."""
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.extractor = PDFExtractor(pdf_path)
        self.data = None
        self.financial_extractor = None
        
    def load(self):
        """Load and process the PDF document."""
        print(f"\n{'='*60}")
        print(f"Loading: {self.pdf_path}")
        print(f"{'='*60}\n")
        
        self.data = self.extractor.extract()
        self.financial_extractor = FinancialDataExtractor(
            self.data["tables"], 
            self.data["pages"]
        )
        
        print(f"\n✓ Loaded {len(self.data['pages'])} pages")
        print(f"✓ Extracted {len(self.data['tables'])} tables\n")
        
    def get_financial_summary(self) -> dict:
        """Get complete financial summary."""
        if not self.data:
            return {"error": "No document loaded"}
        
        return self.financial_extractor.extract_all_metrics()
    
    def get_segment_breakdown(self) -> dict:
        """Get segment-wise revenue and profit breakdown."""
        if not self.data:
            return {"error": "No document loaded"}
        
        segment_revenue = self.financial_extractor.extract_segment_revenue()
        segment_profit = self.financial_extractor.extract_segment_profit()
        
        # Calculate FMCG - Others from FMCG - Total minus FMCG - Cigarettes
        fmcg_total = None
        fmcg_cigarettes = None
        
        for seg in segment_revenue:
            if "fmcg - total" in seg["segment"].lower():
                fmcg_total = seg
            elif "fmcg - cigarettes" in seg["segment"].lower():
                fmcg_cigarettes = seg
        
        if fmcg_total and fmcg_cigarettes:
            fmcg_others = {
                "segment": "FMCG - Others",
                "standalone": fmcg_total["standalone"] - fmcg_cigarettes["standalone"],
                "standalone_prior": fmcg_total["standalone_prior"] - fmcg_cigarettes["standalone_prior"],
                "page": fmcg_total["page"],
                "calculated": True
            }
            segment_revenue.append(fmcg_others)
        
        return {
            "segment_revenue": segment_revenue,
            "segment_profit": segment_profit
        }
    
    def format_segment_table(self) -> str:
        """Format segment revenue as a nice table."""
        data = self.get_segment_breakdown()

        if not data.get("segment_revenue"):
            return "No segment data found"

        # Group by segment name (deduplicate)
        segments_dict = {}
        for seg in data["segment_revenue"]:
            name = seg["segment"]
            
            # Skip FMCG - Total since we show FMCG - Others separately
            if "fmcg - total" in name.lower():
                continue
                
            if name not in segments_dict:
                segments_dict[name] = {
                    "standalone_2025": seg.get("standalone"),
                    "standalone_2024": seg.get("standalone_prior")
                }
            else:
                # Use non-None values
                if seg.get("standalone") and not segments_dict[name]["standalone_2025"]:
                    segments_dict[name]["standalone_2025"] = seg["standalone"]
                if seg.get("standalone_prior") and not segments_dict[name]["standalone_2024"]:
                    segments_dict[name]["standalone_2024"] = seg["standalone_prior"]

        # Format as table
        output = "\n" + "="*90 + "\n"
        output += "SEGMENT-WISE GROSS REVENUE (FY 2024-25) - Standalone Financial Statements\n"
        output += "="*90 + "\n\n"

        output += f"{'Business Segment':<40} {'FY 2025 (₹ Cr)':>20} {'FY 2024 (₹ Cr)':>20}\n"
        output += "-"*90 + "\n"

        total_2025 = 0
        total_2024 = 0

        for name, values in segments_dict.items():
            val_2025 = values.get("standalone_2025")
            val_2024 = values.get("standalone_2024")

            # Values are already in crores from the PDF
            val_2025_str = f"{val_2025:>10.2f}" if val_2025 else "N/A"
            val_2024_str = f"{val_2024:>10.2f}" if val_2024 else "N/A"

            output += f"{name:<40} {val_2025_str:>20} {val_2024_str:>20}\n"

            if val_2025:
                total_2025 += val_2025
            if val_2024:
                total_2024 += val_2024

        output += "-"*90 + "\n"
        output += f"{'Segment Total (Gross)':<40} {total_2025:>20.2f} {total_2024:>20.2f}\n"
        output += "="*90 + "\n"

        return output


# ============================================================================
# TEST WITH ITC REPORT
# ============================================================================
if __name__ == "__main__":
    pdf_path = r"e:\NVidia api\ITC-Report-and-Accounts-2025.pdf"
    
    analyzer = FinancialAnalyzer(pdf_path)
    analyzer.load()
    
    # Get financial summary
    print("\n" + "="*60)
    print("FINANCIAL SUMMARY")
    print("="*60)
    
    summary = analyzer.get_financial_summary()
    
    print("\n📊 REVENUE:")
    rev = summary.get("revenue", {})
    print(f"   Standalone: {rev.get('standalone')}")
    print(f"   Consolidated: {rev.get('consolidated')}")
    
    print("\n💰 PROFIT:")
    profit = summary.get("profit", {})
    print(f"   Net Profit: {profit.get('net_profit')}")
    
    print("\n📋 SEGMENT REVENUE:")
    print(analyzer.format_segment_table())
    
    print("\n💵 SEGMENT PROFIT:")
    seg_profit = summary.get("segment_profit", [])
    for item in seg_profit[:10]:
        print(f"   {item.get('segment')}: {item.get('profit_loss')}")
