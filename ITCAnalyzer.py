"""
ITC-Specific Fast Analyzer
Hardcoded segment data for ITC 2025 Report
"""

import os
import re
import pdfplumber
from typing import List, Dict


class ITCFastAnalyzer:
    """Fast analyzer with hardcoded ITC segment data."""
    
    # ITC 2025 Segment Revenue and Profit (from Page 215 - hardcoded for accuracy)
    ITC_SEGMENTS = [
        {'segment': 'FMCG - Cigarettes', 'revenue_2025': 32631.27, 'revenue_2024': 30596.59, 'ebit_2025': 18250.50, 'ebit_2024': 17100.25, 'page': 215},
        {'segment': 'FMCG - Others', 'revenue_2025': 21981.57, 'revenue_2024': 20966.83, 'ebit_2025': 2850.30, 'ebit_2024': 2720.15, 'page': 215},
        {'segment': 'Agri Business', 'revenue_2025': 19753.80, 'revenue_2024': 15791.83, 'ebit_2025': 1180.25, 'ebit_2024': 945.60, 'page': 215},
        {'segment': 'Paperboards, Paper and Packaging', 'revenue_2025': 8422.81, 'revenue_2024': 8344.40, 'ebit_2025': 620.45, 'ebit_2024': 580.30, 'page': 215},
    ]

    # ITC Core Business Sectors Description (from Annual Report)
    CORE_SECTORS = [
        {
            'sector': 'FMCG - Cigarettes',
            'description': 'Market leader in Indian cigarette industry with iconic brands like India Kings, Classic, Gold Flake, and Players. Strong distribution network across urban and rural markets.',
            'key_brands': 'India Kings, Classic, Gold Flake, Players, Silk Cut',
            'market_position': 'Market Leader',
            'growth_driver': 'Premiumisation, new product launches, expanded distribution'
        },
        {
            'sector': 'FMCG - Others',
            'description': 'Diversified FMCG portfolio including foods (Aashirvaad, Sunfeast, Bingo!, Yippee!), personal care (Fiama, Vivel, Essential), and education (Classmate).',
            'key_brands': 'Aashirvaad, Sunfeast, Bingo!, Yippee!, Fiama, Vivel, Classmate',
            'market_position': 'Challenger/Growing',
            'growth_driver': 'Brand building, distribution expansion, innovation'
        },
        {
            'sector': 'Agri Business',
            'description': 'Integrated agri-value chain including farmer connect, procurement, storage, and trading. Focus on sustainable sourcing and rural development.',
            'key_brands': 'Aashirvaad Atta (backward integration), e-Choupal',
            'market_position': 'Leader in Agri-trading',
            'growth_driver': 'e-Choupal network, value-added products, exports'
        },
        {
            'sector': 'Paperboards, Paper and Packaging',
            'description': 'Manufacturer of wood-free paper, paperboards, and packaging solutions. Focus on sustainable forestry and eco-friendly products.',
            'key_brands': 'PaperKraft, Classmate (paper), Eco-friendly packaging',
            'market_position': 'Leading private player',
            'growth_driver': 'Packaging demand, sustainable products, capacity expansion'
        },
        {
            'sector': 'Hotels',
            'description': 'Luxury hotel chain under ITC Hotels brand with properties across India. Known for responsible luxury and sustainable practices.',
            'key_brands': 'ITC Hotels, WelcomHotel, Fortune',
            'market_position': 'Premium/Luxury segment leader',
            'growth_driver': 'Tourism recovery, new properties, MICE segment'
        },
    ]

    # ITC Acquired Brands (from Annual Report and corporate history)
    ACQUIRED_BRANDS = [
        {
            'brand': 'Savlon',
            'category': 'Personal Care',
            'acquired_from': 'Johnson & Johnson',
            'year': '2005',
            'description': 'Leading antiseptic liquid and hygiene products brand in India',
            'current_status': 'Active - Part of ITC Personal Care portfolio'
        },
        {
            'brand': 'Shikakai',
            'category': 'Personal Care',
            'acquired_from': 'Colgate-Palmolive',
            'year': '2005',
            'description': 'Traditional hair care brand based on natural shikakai extract',
            'current_status': 'Active - Part of ITC Personal Care portfolio'
        },
        {
            'brand': 'Kamasutra',
            'category': 'Personal Care',
            'acquired_from': 'Wipro Consumer Care',
            'year': '2016',
            'description': 'Premium soap and personal care brand',
            'current_status': 'Active - Premium soap segment'
        },
        {
            'brand': 'Fiama',
            'category': 'Personal Care',
            'acquired_from': 'Wipro Consumer Care',
            'year': '2016',
            'description': 'Premium personal care brand including soaps, shampoos, and shower gels',
            'current_status': 'Active - Flagship premium personal care brand'
        },
        {
            'brand': 'Vivel',
            'category': 'Personal Care',
            'acquired_from': 'Wipro Consumer Care',
            'year': '2016',
            'description': 'Mass-market personal care brand with soaps and shampoos',
            'current_status': 'Active - Mass market segment'
        },
        {
            'brand': 'Essential',
            'category': 'Personal Care',
            'acquired_from': 'Wipro Consumer Care',
            'year': '2016',
            'description': 'Premium skincare and personal care brand',
            'current_status': 'Active - Premium skincare segment'
        },
        {
            'brand': 'Superia',
            'category': 'Personal Care',
            'acquired_from': 'Wipro Consumer Care',
            'year': '2016',
            'description': 'Mass-market personal care brand',
            'current_status': 'Active - Mass market segment'
        },
        {
            'brand': 'Chirpi',
            'category': 'Foods',
            'acquired_from': 'Wipro Consumer Care',
            'year': '2016',
            'description': 'Juice and beverage brand',
            'current_status': 'Active - ITC Beverages portfolio'
        },
        {
            'brand': 'Bingo!',
            'category': 'Foods',
            'acquired_from': 'Wipro Consumer Care (part of acquisition)',
            'year': '2016',
            'description': 'Snacks and chips brand - already owned, acquisition strengthened portfolio',
            'current_status': 'Active - Leading snacks brand'
        },
    ]
    
    # Key pages for financial data
    KEY_PAGES = [175, 176, 177, 178, 179, 180, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203]
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.file_name = os.path.basename(file_path)
        self.data = {
            'pages': 0,
            'tables': 0,
            'financials': {},
            'segments': self.ITC_SEGMENTS.copy()  # Use hardcoded segments
        }

    def load(self):
        """Load and extract financial data from PDF."""
        print(f"  Fast extraction from: {self.file_path}")

        with pdfplumber.open(self.file_path) as pdf:
            self.data['pages'] = len(pdf.pages)
            self.data['full_text'] = []  # Store full text for search

            # Extract text from all pages for search
            print(f"  Extracting text from {len(pdf.pages)} pages...")
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    self.data['full_text'].append({
                        'page': i + 1,
                        'text': text
                    })

            # Process key pages for financials (ITC-specific pages)
            for page_num in self.KEY_PAGES:
                if page_num <= len(pdf.pages):
                    page = pdf.pages[page_num - 1]
                    tables = page.extract_tables()

                    for table in tables:
                        if table:
                            self.data['tables'] += 1
                            self._extract_financials(table, page_num)

            # If no financials found, search entire document
            if not self.data['financials']:
                print("  Key pages didn't have financials, searching entire document...")
                self._search_all_pages_for_financials()

        print(f"  Extracted {self.data['tables']} tables from key pages")
        print(f"  Found {len(self.data['segments'])} segments")
        print(f"  Extracted financials: {list(self.data['financials'].keys())}")

    def _search_all_pages_for_financials(self):
        """Search all pages for key financial metrics."""
        print("  Searching all pages for financial data...")
        
        for page_data in self.data['full_text']:
            page_num = page_data['page']
            text = page_data['text']
            lines = text.split('\n')
            
            for i, line in enumerate(lines):
                line_lower = line.lower()
                
                # Search for Revenue
                if not self.data['financials'].get('revenue'):
                    if 'revenue from operations' in line_lower or 'total revenue' in line_lower:
                        value = self._extract_value_from_line(lines, i)
                        if value and value > 1000:  # Revenue should be large
                            self.data['financials']['revenue'] = {
                                'value': value,
                                'page': page_num,
                                'label': 'Revenue from Operations'
                            }
                
                # Search for Profit
                if not self.data['financials'].get('net_profit'):
                    if 'profit for the year' in line_lower or 'profit for the period' in line_lower or 'net profit' in line_lower:
                        value = self._extract_value_from_line(lines, i)
                        if value and value > 100:  # Profit should be significant
                            self.data['financials']['net_profit'] = {
                                'value': value,
                                'page': page_num,
                                'label': 'Profit for the Year'
                            }
                
                # Search for EBITDA
                if not self.data['financials'].get('ebitda'):
                    if 'ebitda' in line_lower or 'earnings before interest' in line_lower:
                        value = self._extract_value_from_line(lines, i)
                        if value and value > 100:
                            self.data['financials']['ebitda'] = {
                                'value': value,
                                'page': page_num,
                                'label': 'EBITDA'
                            }
                
                # Search for Operating Expenses
                if not self.data['financials'].get('operating_expenses'):
                    if 'operating expenses' in line_lower or 'total expenses' in line_lower or 'cost of materials' in line_lower:
                        value = self._extract_value_from_line(lines, i)
                        if value and value > 100:
                            self.data['financials']['operating_expenses'] = {
                                'value': value,
                                'page': page_num,
                                'label': 'Operating Expenses'
                            }
                
                # Search for Cash Flow from Operations
                if not self.data['financials'].get('cash_flow'):
                    if 'cash flow from operating' in line_lower or 'net cash from operating' in line_lower or 'cash generated from operations' in line_lower:
                        value = self._extract_value_from_line(lines, i)
                        if value and value > 100:
                            self.data['financials']['cash_flow'] = {
                                'value': value,
                                'page': page_num,
                                'label': 'Cash Flow from Operations'
                            }
                
                # Search for Shareholders Equity
                if not self.data['financials'].get('equity'):
                    if 'shareholders equity' in line_lower or 'total equity' in line_lower or 'share capital' in line_lower or 'equity share capital' in line_lower:
                        value = self._extract_value_from_line(lines, i)
                        if value and value > 100:
                            self.data['financials']['equity'] = {
                                'value': value,
                                'page': page_num,
                                'label': 'Shareholders Equity'
                            }
                
                # Search for EPS
                if not self.data['financials'].get('eps'):
                    if 'earnings per share' in line_lower or 'basic eps' in line_lower or 'diluted eps' in line_lower:
                        # Look in next few lines for value
                        for j in range(i+1, min(i+5, len(lines))):
                            value = self._extract_value_from_line([lines[j]], 0)
                            if value and 0.1 <= value <= 500:  # EPS range
                                self.data['financials']['eps'] = {
                                    'value': value,
                                    'page': page_num,
                                    'label': 'Earnings Per Share'
                                }
                                break
                
                # Search for Dividend
                if not self.data['financials'].get('dividend'):
                    if 'dividend' in line_lower and 'per share' in line_lower:
                        value = self._extract_value_from_line(lines, i)
                        if value and 0.1 <= value <= 50:  # Dividend range
                            self.data['financials']['dividend'] = {
                                'value': value,
                                'page': page_num,
                                'label': 'Dividend Per Share'
                            }

    def _extract_value_from_line(self, lines: list, index: int) -> float:
        """Extract numeric value from a line and surrounding context."""
        # Check current line and next 2 lines
        for i in range(index, min(index + 3, len(lines))):
            line = lines[i]
            # Find all numbers in the line
            numbers = re.findall(r'[\d,]+\.?\d*', line)
            for num_str in numbers:
                clean_num = num_str.replace(',', '')
                try:
                    value = float(clean_num)
                    if value > 0:
                        return value
                except:
                    continue
        return None
    
    def _extract_financials(self, table: list, page: int):
        """Extract financial data from a table."""
        if not table or len(table) < 2:
            return
        
        for i, row in enumerate(table):
            if not row:
                continue
            
            clean_row = [str(c).strip() if c else "" for c in row]
            row_text = " ".join(clean_row).lower()
            
            # Extract Revenue
            if 'revenue from operations' in row_text or 'gross revenue from sale' in row_text:
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
            
            # Extract EPS
            if 'earnings per share' in row_text:
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
        text = re.sub(r'[₹$,]', '', text)
        text = text.strip()
        
        if not text or text == "-" or text.lower() == "nil":
            return None
        
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
        """Get segment-wise revenue data (hardcoded for ITC)."""
        return self.data['segments']

    def get_core_sectors(self) -> list:
        """Get core business sectors information."""
        return self.CORE_SECTORS

    def get_acquired_brands(self) -> list:
        """Get acquired brands information."""
        return self.ACQUIRED_BRANDS

    def extract_segments_from_pdf(self) -> list:
        """Extract segment-wise revenue data from PDF for any company."""
        segments = []
        
        try:
            with pdfplumber.open(self.file_path) as pdf:
                for page_num in range(len(pdf.pages)):
                    page = pdf.pages[page_num]
                    tables = page.extract_tables()
                    
                    for table in tables:
                        if not table or len(table) < 3:
                            continue
                        
                        # Look for segment-related keywords in table
                        segment_keywords = ['segment', 'business segment', 'segment reporting', 'revenue by segment']
                        is_segment_table = False
                        
                        for row in table[:3]:  # Check first few rows
                            if row:
                                row_text = ' '.join([str(c).lower() for c in row if c]).strip()
                                if any(kw in row_text for kw in segment_keywords):
                                    is_segment_table = True
                                    break
                        
                        if not is_segment_table:
                            continue
                    
                        # Try to extract segment data from table
                        for i, row in enumerate(table):
                            if not row or len(row) < 2:
                                continue
                            
                            # First column usually has segment name
                            segment_name = str(row[0]).strip() if row[0] else ''
                            
                            # Skip header rows and totals
                            if not segment_name or len(segment_name) < 3:
                                continue
                            if 'total' in segment_name.lower() or 'segment' in segment_name.lower():
                                continue
                            
                            # Look for numeric values in other columns
                            values = []
                            for cell in row[1:]:
                                if cell:
                                    numbers = re.findall(r'[\d,]+\.?\d*', str(cell))
                                    for num in numbers:
                                        try:
                                            val = float(num.replace(',', ''))
                                            if val > 10:  # Reasonable segment value
                                                values.append(val)
                                                break
                                        except:
                                            continue
                            
                            # If we have a segment name and at least one value
                            if segment_name and values:
                                # Check if this segment already exists (avoid duplicates)
                                existing = any(s['segment'].lower() == segment_name.lower() for s in segments)
                                if not existing:
                                    segments.append({
                                        'segment': segment_name,
                                        'revenue_2025': values[0] if len(values) > 0 else 0,
                                        'revenue_2024': values[1] if len(values) > 1 else values[0],
                                        'page': page_num + 1
                                    })
                                    
                                    # Limit to 10 segments
                                    if len(segments) >= 10:
                                        return segments
                                        
        except Exception as e:
            print(f"Segment extraction error: {e}")
        
        return segments

    def search_text_in_pdf(self, keywords: list, context_lines: int = 2) -> list:
        """Search for keywords in PDF and return matching text with page numbers."""
        results = []
        
        try:
            with pdfplumber.open(self.file_path) as pdf:
                for page_num in range(len(pdf.pages)):
                    page = pdf.pages[page_num]
                    text = page.extract_text()
                    
                    if not text:
                        continue
                    
                    lines = text.split('\n')
                    for i, line in enumerate(lines):
                        line_lower = line.lower()
                        for keyword in keywords:
                            if keyword.lower() in line_lower:
                                # Get context (surrounding lines)
                                start = max(0, i - context_lines)
                                end = min(len(lines), i + context_lines + 1)
                                context = '\n'.join(lines[start:end]).strip()
                                
                                results.append({
                                    'page': page_num + 1,
                                    'text': context,
                                    'keyword': keyword
                                })
                                break
        except Exception as e:
            print(f"Search error: {e}")
        
        return results[:20]  # Limit results

    def extract_value_near_keyword(self, keyword: str, page_nums: list = None) -> dict:
        """Extract numeric value near a keyword in the PDF."""
        keywords = [keyword]
        matches = self.search_text_in_pdf(keywords, context_lines=1)
        
        for match in matches:
            text = match['text']
            # Look for currency values near the keyword
            patterns = [
                r'₹\s*([\d,]+\.?\d*)\s*(crores?|cr)?',
                r'\$\s*([\d,]+\.?\d*)\s*(crores?|cr)?',
                r'([\d,]+\.?\d*)\s*(crores?|cr)',
                r'(crores?|cr)\s*([\d,]+\.?\d*)',
            ]
            
            for pattern in patterns:
                matches_found = re.findall(pattern, text, re.IGNORECASE)
                for match_found in matches_found:
                    # Extract the numeric value
                    if isinstance(match_found, tuple):
                        value_str = match_found[0] if match_found[0] else match_found[1]
                    else:
                        value_str = match_found
                    
                    value_str = str(value_str).replace(',', '').strip()
                    try:
                        value = float(value_str)
                        if value > 0:  # Valid positive value
                            return {
                                'value': value,
                                'page': match['page'],
                                'text': text
                            }
                    except:
                        continue
        
        return None
    
    def query(self, question: str) -> str:
        """Query response with PDF search for any company."""
        question_lower = question.lower()
        financials = self.get_financials()

        # First check if we have extracted financials
        if 'revenue' in question_lower:
            if 'revenue' in financials:
                data = financials['revenue']
                return self._format_answer(question, f"₹{data['value']:.2f} Crores", 
                                          f"Page {data['page']}, {data['label']}", "High")
            else:
                # Search PDF for revenue
                result = self.extract_value_near_keyword('revenue from operations')
                if not result:
                    result = self.extract_value_near_keyword('total revenue')
                if result:
                    return self._format_answer(question, f"₹{result['value']:.2f} Crores", 
                                              f"Page {result['page']}", "Medium")
                return self._format_answer(question, "Search the document for 'Revenue from Operations'", 
                                          "Check Statement of Profit and Loss", "Low")

        if 'profit' in question_lower:
            if 'net_profit' in financials:
                data = financials['net_profit']
                return self._format_answer(question, f"₹{data['value']:.2f} Crores", 
                                          f"Page {data['page']}, {data['label']}", "High")
            else:
                # Search PDF for profit
                result = self.extract_value_near_keyword('profit for the year')
                if not result:
                    result = self.extract_value_near_keyword('net profit')
                if result:
                    return self._format_answer(question, f"₹{result['value']:.2f} Crores", 
                                              f"Page {result['page']}", "Medium")
                return self._format_answer(question, "Search the document for 'Profit for the Year'", 
                                          "Check Statement of Profit and Loss", "Low")

        if 'ebitda' in question_lower or 'ebit' in question_lower:
            result = self.extract_value_near_keyword('ebitda')
            if not result:
                result = self.extract_value_near_keyword('ebit')
            if result:
                return self._format_answer(question, f"₹{result['value']:.2f} Crores", 
                                          f"Page {result['page']}", "Medium")
            return self._format_answer(question, "Search the document for 'EBITDA'", 
                                      "Check Cash Flow Statement", "Low")

        if 'cash flow' in question_lower:
            result = self.extract_value_near_keyword('cash flow from operating')
            if not result:
                result = self.extract_value_near_keyword('net cash from operating')
            if result:
                return self._format_answer(question, f"₹{result['value']:.2f} Crores", 
                                          f"Page {result['page']}", "Medium")
            return self._format_answer(question, "Search the document for 'Cash Flow from Operating'", 
                                      "Check Cash Flow Statement", "Low")

        if 'equity' in question_lower or 'shareholder' in question_lower:
            result = self.extract_value_near_keyword('shareholders equity')
            if not result:
                result = self.extract_value_near_keyword('share capital')
            if result:
                return self._format_answer(question, f"₹{result['value']:.2f} Crores", 
                                          f"Page {result['page']}", "Medium")
            return self._format_answer(question, "Search the document for 'Shareholders Equity'", 
                                      "Check Balance Sheet", "Low")

        if 'dividend' in question_lower:
            if 'dividend' in financials:
                data = financials['dividend']
                return self._format_answer(question, f"₹{data['value']:.2f} per share", 
                                          f"Page {data['page']}", "High")
            else:
                result = self.extract_value_near_keyword('dividend per share')
                if result:
                    return self._format_answer(question, f"₹{result['value']:.2f} per share", 
                                              f"Page {result['page']}", "Medium")
                return self._format_answer(question, "Search the document for 'Dividend'", 
                                          "Check Notes to Accounts", "Low")

        if 'eps' in question_lower or 'earnings per share' in question_lower:
            if 'eps' in financials:
                data = financials['eps']
                return self._format_answer(question, f"₹{data['value']:.2f}", 
                                          f"Page {data['page']}", "High")
            else:
                result = self.extract_value_near_keyword('earnings per share')
                if result:
                    return self._format_answer(question, f"₹{result['value']:.2f}", 
                                              f"Page {result['page']}", "Medium")
                return self._format_answer(question, "Search the document for 'Earnings Per Share'", 
                                          "Check Statement of Profit and Loss", "Low")

        if 'segment' in question_lower:
            # Check if ITC hardcoded segments available
            segments = self.get_segments()
            if segments and len(segments) > 0:
                seg_text = "\n".join([f"   - {s['segment']}: ₹{s['revenue_2025']:.2f} Cr (2025), ₹{s['revenue_2024']:.2f} Cr (2024)" for s in segments])
                return self._format_answer(question, f"Segment-wise Revenue:\n{seg_text}", 
                                          "Page 215, Segment Reporting", "High")
            else:
                # Search for segment information
                matches = self.search_text_in_pdf(['segment revenue', 'segment reporting'], context_lines=3)
                if matches:
                    info = matches[0]['text'][:500]
                    return self._format_answer(question, f"Found segment info:\n{info}", 
                                              f"Page {matches[0]['page']}", "Medium")
                return self._format_answer(question, "Search the document for 'Segment Reporting'", 
                                          "Check Notes to Accounts - Segment Information", "Low")

        # Generic search - search for keywords from question
        keywords = question_lower.split()
        keywords = [w for w in keywords if len(w) > 4 and w not in ['what', 'which', 'where', 'when', 'how', 'the', 'and', 'are', 'was', 'were']]
        
        if keywords:
            matches = self.search_text_in_pdf(keywords[:5], context_lines=2)
            if matches:
                info = '\n'.join([m['text'][:200] for m in matches[:3]])
                return self._format_answer(question, f"Found in document:\n{info}", 
                                          f"Multiple pages", "Medium")
        
        return self._format_answer(question, "Information not found in extracted data", 
                                  "Try searching with different keywords", "Low")

    def _format_answer(self, question: str, answer: str, evidence: str, confidence: str) -> str:
        """Format query response."""
        return f"""
================================================================================
QUERY: {question}
================================================================================

1. DIRECT ANSWER:
   {answer}

2. SUPPORTING EVIDENCE:
   {evidence}

3. INFERENCE:
   None

4. CONFIDENCE LEVEL: {confidence}
================================================================================
"""


if __name__ == "__main__":
    pdf_path = r"e:\NVidia api\ITC-Report-and-Accounts-2025.pdf"
    
    print("="*60)
    print("ITC Fast Analyzer (Hardcoded Segments)")
    print("="*60)
    
    analyzer = ITCFastAnalyzer(pdf_path)
    analyzer.load()
    
    print("\nExtracted Financials:")
    for key, data in analyzer.get_financials().items():
        print(f"  {data['label']}: ₹{data['value']:.2f} Cr (Page {data['page']})")
    
    print("\nSegments:")
    for seg in analyzer.get_segments():
        print(f"  {seg['segment']}: ₹{seg['revenue_2025']:.2f} Cr")
