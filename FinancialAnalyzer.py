"""
Financial Document Analyzer
An intelligent PDF analysis agent for financial documents with deep search, 
table extraction, and reasoning capabilities using NVIDIA API.
"""

import os
import re
import json
import pdfplumber
from typing import Optional
import requests


# ============================================================================
# CONFIGURATION
# ============================================================================
API_KEY = os.getenv("NVIDIA_API_KEY", "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")
NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

# Financial term synonyms for intelligent search
FINANCIAL_SYNONYMS = {
    "revenue": ["revenue", "sales", "income", "turnover", "operating revenue", "net sales", "total revenue", "gross revenue"],
    "profit": ["profit", "earnings", "net income", "net profit", "bottom line", "pat", "profit attributable"],
    "ebitda": ["ebitda", "earnings before interest", "operating profit", "ebit"],
    "assets": ["assets", "total assets", "non-current assets", "current assets", "resources"],
    "liabilities": ["liabilities", "total liabilities", "debts", "borrowings", "obligations"],
    "equity": ["equity", "shareholders equity", "net worth", "owners equity", "share capital"],
    "cash flow": ["cash flow", "cash generated", "cash from operations", "operating cash flow"],
    "expenses": ["expenses", "expenditure", "costs", "operating expenses", "opex", "cost of sales"],
    "gross profit": ["gross profit", "gross margin", "gross income"],
    "operating profit": ["operating profit", "operating income", "ebit", "operating earnings"],
    "net profit": ["net profit", "net income", "profit for the year", "profit for the period", "bottom line"],
    "segment": ["segment", "division", "business segment", "reportable segment", "geographic segment"],
    "quarterly": ["quarterly", "q1", "q2", "q3", "q4", "three months", "quarter"],
    "annual": ["annual", "year", "fy", "financial year", "twelve months"],
}

# Table column variations
FINANCIAL_COLUMNS = {
    "amount": ["amount", "value", "figure", "total", "sum"],
    "percentage": ["%", "percent", "percentage", "margin", "growth"],
    "year": ["year", "fy", "fiscal", "period", "2024", "2025", "2026"],
    "change": ["change", "variation", "difference", "growth", "increase", "decrease"],
}


# ============================================================================
# PDF EXTRACTOR
# ============================================================================
class PDFExtractor:
    """Extract text and tables from PDF documents."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.pages_data = []
        self.tables_data = []
        self.full_text = ""
        
    def extract(self) -> dict:
        """Extract all content from PDF."""
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"PDF not found: {self.file_path}")
            
        with pdfplumber.open(self.file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                # Extract text
                text = page.extract_text() or ""
                self.full_text += f"\n[PAGE {page_num}]\n{text}"
                
                self.pages_data.append({
                    "page": page_num,
                    "text": text,
                    "tables": []
                })
                
                # Extract tables
                tables = page.extract_tables()
                for table_idx, table in enumerate(tables):
                    if table:
                        table_data = self._parse_table(table)
                        self.tables_data.append({
                            "page": page_num,
                            "table_index": table_idx,
                            "data": table_data,
                            "raw": table
                        })
                        self.pages_data[-1]["tables"].append(table_data)
                        
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


# ============================================================================
# INTELLIGENT SEARCH
# ============================================================================
class IntelligentSearch:
    """Perform keyword and semantic search with synonym expansion."""
    
    def __init__(self, pages_data: list, tables_data: list):
        self.pages_data = pages_data
        self.tables_data = tables_data
        
    def search(self, query: str) -> list:
        """Search with keyword expansion."""
        results = []
        
        # Get expanded keywords
        keywords = self._expand_keywords(query)
        
        # Search in text
        for page in self.pages_data:
            matches = self._find_matches(page["text"], keywords)
            if matches:
                results.append({
                    "type": "text",
                    "page": page["page"],
                    "content": page["text"],
                    "matches": matches,
                    "relevance": len(matches)
                })
        
        # Search in tables
        for table_info in self.tables_data:
            table_text = self._table_to_text(table_info["data"])
            matches = self._find_matches(table_text, keywords)
            if matches:
                results.append({
                    "type": "table",
                    "page": table_info["page"],
                    "table_index": table_info["table_index"],
                    "content": table_info["data"],
                    "matches": matches,
                    "relevance": len(matches) * 2  # Tables weighted higher
                })
                
        # Sort by relevance
        results.sort(key=lambda x: x["relevance"], reverse=True)
        return results[:10]  # Top 10 results
    
    def _expand_keywords(self, query: str) -> list:
        """Expand query with synonyms."""
        keywords = [query.lower()]
        
        for term, synonyms in FINANCIAL_SYNONYMS.items():
            if term in query.lower():
                keywords.extend(synonyms)
                
        # Add regex patterns for numbers/currencies
        keywords.append(r'\$?[\d,]+\.?\d*')
        keywords.append(r'\d+%')
        
        return list(set(keywords))
    
    def _find_matches(self, text: str, keywords: list) -> list:
        """Find all keyword matches in text."""
        matches = []
        text_lower = text.lower()
        
        for keyword in keywords:
            try:
                if re.search(keyword, text_lower, re.IGNORECASE):
                    matches.append(keyword)
            except re.error:
                if keyword.lower() in text_lower:
                    matches.append(keyword)
                    
        return matches
    
    def _table_to_text(self, table: list) -> str:
        """Convert table to searchable text."""
        return " ".join([" ".join(row) for row in table])


# ============================================================================
# TABLE ANALYZER
# ============================================================================
class TableAnalyzer:
    """Analyze financial tables and extract structured data."""
    
    def __init__(self, tables_data: list):
        self.tables_data = tables_data
        
    def find_financial_table(self, keywords: list) -> Optional[dict]:
        """Find table containing financial data matching keywords."""
        for table_info in self.tables_data:
            table_text = " ".join([str(cell) for row in table_info["data"] for cell in row]).lower()
            
            match_count = sum(1 for kw in keywords if kw.lower() in table_text)
            if match_count >= 1:
                return {
                    "page": table_info["page"],
                    "data": table_info["data"],
                    "headers": table_info["data"][0] if table_info["data"] else [],
                    "rows": table_info["data"][1:] if len(table_info["data"]) > 1 else []
                }
        return None
    
    def extract_values(self, table: dict, target_field: str) -> list:
        """Extract values for a specific field from table."""
        values = []
        headers = [h.lower() if h else "" for h in table["headers"]]
        
        # Find target column
        target_idx = -1
        for idx, header in enumerate(headers):
            if target_field.lower() in header.lower():
                target_idx = idx
                break
                
        if target_idx >= 0:
            for row in table["rows"]:
                if target_idx < len(row):
                    try:
                        value = self._parse_number(row[target_idx])
                        if value is not None:
                            values.append({
                                "label": row[0] if row else "Unknown",
                                "value": value
                            })
                    except (ValueError, IndexError):
                        continue
                        
        return values
    
    def _parse_number(self, text: str) -> Optional[float]:
        """Parse numeric value from text."""
        if not text:
            return None
        # Remove currency symbols, commas, spaces
        cleaned = re.sub(r'[,$\s]', '', str(text))
        # Handle parentheses for negatives
        if cleaned.startswith('(') and cleaned.endswith(')'):
            cleaned = '-' + cleaned[1:-1]
        try:
            return float(cleaned)
        except ValueError:
            return None
    
    def aggregate(self, values: list, operation: str = "sum") -> float:
        """Aggregate values."""
        if not values:
            return 0.0
            
        nums = [v["value"] for v in values if v["value"] is not None]
        
        if operation == "sum":
            return sum(nums)
        elif operation == "avg":
            return sum(nums) / len(nums) if nums else 0.0
        elif operation == "max":
            return max(nums) if nums else 0.0
        elif operation == "min":
            return min(nums) if nums else 0.0
            
        return sum(nums)


# ============================================================================
# NVIDIA API INTEGRATION
# ============================================================================
class NVIDIAReasoner:
    """Use NVIDIA API for reasoning and inference."""
    
    def __init__(self, api_key: str = API_KEY):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
    def reason(self, query: str, context: str) -> dict:
        """Use LLM to reason about the query with given context."""
        prompt = f"""You are an expert financial analyst. Analyze the following information and answer the query.

QUERY: {query}

CONTEXT FROM DOCUMENT:
{context}

Provide your answer in this exact format:
1. Direct Answer: [Your direct answer]
2. Supporting Evidence: [Page numbers and sections]
3. Inference: [Any inferences made, or "None"]
4. Confidence Level: [High/Medium/Low]

Be accurate and mention if data is inferred or estimated."""

        payload = {
            "model": "meta/llama3-70b-instruct",
            "messages": [
                {"role": "system", "content": "You are an expert financial analyst specializing in document analysis."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 500
        }
        
        try:
            response = requests.post(NVIDIA_API_URL, headers=self.headers, json=payload)
            response.raise_for_status()
            data = response.json()
            answer = data["choices"][0]["message"]["content"]
            
            return self._parse_response(answer)
        except Exception as e:
            return {
                "answer": f"Error calling NVIDIA API: {str(e)}",
                "evidence": "N/A",
                "inference": "N/A",
                "confidence": "Low"
            }
    
    def _parse_response(self, text: str) -> dict:
        """Parse LLM response into structured format."""
        result = {
            "answer": "",
            "evidence": "",
            "inference": "",
            "confidence": "Medium"
        }
        
        lines = text.split('\n')
        for line in lines:
            lower = line.lower()
            if 'direct answer' in lower or line.startswith('1.'):
                result["answer"] = line.split(':', 1)[-1].strip() if ':' in line else line
            elif 'evidence' in lower or line.startswith('2.'):
                result["evidence"] = line.split(':', 1)[-1].strip() if ':' in line else line
            elif 'inference' in lower or line.startswith('3.'):
                result["inference"] = line.split(':', 1)[-1].strip() if ':' in line else line
            elif 'confidence' in lower or line.startswith('4.'):
                conf_text = line.split(':', 1)[-1].strip() if ':' in line else line
                if 'high' in conf_text.lower():
                    result["confidence"] = "High"
                elif 'low' in conf_text.lower():
                    result["confidence"] = "Low"
                else:
                    result["confidence"] = "Medium"
                    
        if not result["answer"]:
            result["answer"] = text
            
        return result


# ============================================================================
# FINANCIAL ANALYZER AGENT
# ============================================================================
class FinancialAnalyzer:
    """Main agent for financial document analysis."""
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.extractor = PDFExtractor(pdf_path)
        self.search_engine = None
        self.table_analyzer = None
        self.reasoner = NVIDIAReasoner()
        self.data = None
        
    def load(self):
        """Load and process the PDF document."""
        print(f"Loading document: {self.pdf_path}")
        self.data = self.extractor.extract()
        self.search_engine = IntelligentSearch(self.data["pages"], self.data["tables"])
        self.table_analyzer = TableAnalyzer(self.data["tables"])
        print(f"Loaded {len(self.data['pages'])} pages, {len(self.data['tables'])} tables")
        
    def query(self, question: str) -> str:
        """Process a query and return formatted answer."""
        if not self.data:
            return "Please load a document first using load()"
            
        print(f"\nAnalyzing: {question}")
        
        # Step 1: Search
        search_results = self.search_engine.search(question)
        
        # Step 2: Try table analysis for financial queries
        table_context = ""
        financial_terms = [term for term in FINANCIAL_SYNONYMS.keys() if term in question.lower()]
        
        if financial_terms and self.table_analyzer:
            for term in financial_terms:
                table = self.table_analyzer.find_financial_table(FINANCIAL_SYNONYMS[term])
                if table:
                    values = self.table_analyzer.extract_values(table, term)
                    if values:
                        total = self.table_analyzer.aggregate(values, "sum")
                        table_context += f"\nFound {term} table on page {table['page']}: {len(values)} values, sum={total}"
        
        # Step 3: Build context
        context = ""
        for result in search_results[:5]:
            if result["type"] == "text":
                context += f"\n[Page {result['page']}]: {result['content'][:500]}..."
            else:
                context += f"\n[Table on Page {result['page']}]: {str(result['content'])[:500]}..."
                
        context += table_context
        
        # Step 4: Reason with NVIDIA API
        if context.strip():
            result = self.reasoner.reason(question, context)
        else:
            result = {
                "answer": "Could not find relevant information in the document.",
                "evidence": "No matching content found",
                "inference": "None",
                "confidence": "Low"
            }
        
        # Step 5: Format output
        output = self._format_output(question, result)
        return output

    def get_segment_revenue(self) -> dict:
        """Extract segment-wise revenue breakdown."""
        if not self.data:
            return {"error": "No document loaded"}
        
        # Search for segment-related tables
        segment_keywords = ["segment", "business segment", "segment revenue", "segment wise", "division"]
        segment_tables = []
        
        for table_info in self.data["tables"]:
            table_text = " ".join([str(cell) for row in table_info["data"] for cell in row]).lower()
            
            # Check if table contains segment information
            if any(kw in table_text for kw in segment_keywords):
                segment_tables.append({
                    "page": table_info["page"],
                    "data": table_info["data"]
                })
        
        # Also search for tables with FMCG, Agri, etc.
        business_keywords = ["fmcg", "cigarette", "agri", "paperboard", "hotel", "itc"]
        for table_info in self.data["tables"]:
            table_text = " ".join([str(cell) for row in table_info["data"] for cell in row]).lower()
            
            if any(kw in table_text for kw in business_keywords):
                # Check if not already added
                if not any(t["page"] == table_info["page"] and t["data"] == table_info["data"] for t in segment_tables):
                    segment_tables.append({
                        "page": table_info["page"],
                        "data": table_info["data"]
                    })
        
        return {
            "tables_found": len(segment_tables),
            "tables": segment_tables[:10]  # Return top 10 tables
        }

    def extract_segment_table_as_dict(self, table_data: list) -> list:
        """Convert segment table to structured dictionary format."""
        segments = []
        
        if not table_data or len(table_data) < 2:
            return segments
        
        headers = [str(h).strip().lower() if h else "" for h in table_data[0]]
        
        # Find relevant columns
        segment_col = -1
        standalone_col = -1
        consolidated_col = -1
        
        for idx, header in enumerate(headers):
            if "segment" in header or "business" in header or "particulars" in header:
                segment_col = idx
            elif "standalone" in header:
                standalone_col = idx
            elif "consolidated" in header:
                consolidated_col = idx
        
        # If specific columns not found, try to infer
        if segment_col == -1:
            segment_col = 0  # Assume first column is segment name
        
        # Extract data rows
        for row in table_data[1:]:
            if len(row) <= segment_col:
                continue
                
            segment_name = str(row[segment_col]).strip()
            
            # Skip empty or header-like rows
            if not segment_name or segment_name.lower() in ["total", "subtotal", "note", "notes"]:
                continue
            
            # Try to extract numeric values
            standalone_val = None
            consolidated_val = None
            
            if standalone_col >= 0 and standalone_col < len(row):
                standalone_val = self._parse_numeric(row[standalone_col])
            
            if consolidated_col >= 0 and consolidated_col < len(row):
                consolidated_val = self._parse_numeric(row[consolidated_col])
            
            # If only one value column exists, use it for both
            if standalone_val and not consolidated_val and len(row) > standalone_col + 1:
                consolidated_val = self._parse_numeric(row[standalone_col + 1])
            
            if segment_name and (standalone_val or consolidated_val):
                segments.append({
                    "segment": segment_name,
                    "standalone": standalone_val,
                    "consolidated": consolidated_val
                })
        
        return segments

    def _parse_numeric(self, value) -> float:
        """Parse numeric value from string."""
        if not value:
            return None
        
        # Convert to string and clean
        text = str(value).strip()
        
        # Remove common characters
        text = re.sub(r'[₹,$,%,\s]', '', text)
        
        # Handle Indian numbering (crores, lakhs)
        multiplier = 1
        if "crore" in text.lower():
            text = re.sub(r'crore[s]?', '', text, flags=re.IGNORECASE)
            multiplier = 10000000
        elif "lakh" in text.lower():
            text = re.sub(r'lakh[s]?', '', text, flags=re.IGNORECASE)
            multiplier = 100000
        
        # Handle parentheses for negatives
        if text.startswith('(') and text.endswith(')'):
            text = '-' + text[1:-1]
        
        try:
            return float(text) * multiplier
        except ValueError:
            return None
    
    def _format_output(self, query: str, result: dict) -> str:
        """Format the final output."""
        output = f"""
{'='*70}
QUERY: {query}
{'='*70}

1. DIRECT ANSWER:
   {result.get('answer', 'N/A')}

2. SUPPORTING EVIDENCE:
   {result.get('evidence', 'N/A')}

3. INFERENCE:
   {result.get('inference', 'None')}

4. CONFIDENCE LEVEL: {result.get('confidence', 'Medium')}
{'='*70}
"""
        return output


# ============================================================================
# MAIN - INTERACTIVE MODE
# ============================================================================
def main():
    """Interactive mode for querying financial documents."""
    print("="*60)
    print("FINANCIAL DOCUMENT ANALYZER")
    print("Powered by NVIDIA API")
    print("="*60)
    
    pdf_path = input("\nEnter PDF file path: ").strip().strip('"')
    
    if not os.path.exists(pdf_path):
        print(f"Error: File not found at {pdf_path}")
        return
        
    analyzer = FinancialAnalyzer(pdf_path)
    analyzer.load()
    
    print("\nReady to query! (type 'exit' to quit)")
    
    while True:
        try:
            query = input("\nYou: ").strip()
            if query.lower() in ['exit', 'quit', 'q']:
                print("Goodbye!")
                break
            if not query:
                continue
                
            answer = analyzer.query(query)
            print(answer)
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {str(e)}")


if __name__ == "__main__":
    main()
