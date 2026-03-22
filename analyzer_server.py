"""
Flask backend for Financial Document Analyzer Web Interface
"""

from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS
import os
import threading
import json
import re
from typing import Optional
from ITCAnalyzer import ITCFastAnalyzer
from RAGDocumentAnalyzer import RAGDocumentAnalyzer

app = Flask(__name__, static_folder='.', template_folder='.')
CORS(app)

# Store active analyzers (in production, use Redis/database)
active_analyzers = {}

# Session persistence
SESSION_FILE = os.path.join(os.path.dirname(__file__), 'sessions.json')

def save_sessions():
    """Save session metadata to disk."""
    # Don't save analyzer objects (can't serialize), just metadata
    sessions = {}
    for sid, data in active_analyzers.items():
        sessions[sid] = {
            'file_name': data.get('file_name', ''),
            'file_path': data.get('file_path', ''),
            'pages': data.get('pages', 0),
            'tables': data.get('tables', 0),
            'company_type': data.get('company_type', 'generic'),
            'has_rag': data.get('has_rag', False)
        }
    try:
        with open(SESSION_FILE, 'w') as f:
            json.dump(sessions, f, indent=2)
    except:
        pass

def load_sessions():
    """Load session metadata from disk."""
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, 'r') as f:
                sessions = json.load(f)
            print(f"Loaded {len(sessions)} previous sessions")
            # Note: Can't restore analyzers without re-processing
            return sessions
        except:
            pass
    return {}

def detect_company_type(filename: str) -> str:
    """Detect company type from filename to determine which hardcoded data to use."""
    filename_lower = filename.lower()
    
    if 'itc' in filename_lower:
        return 'itc'
    elif 'reliance' in filename_lower:
        return 'reliance'
    elif 'tata' in filename_lower:
        return 'tata'
    elif 'hdfc' in filename_lower:
        return 'hdfc'
    elif 'infy' in filename_lower or 'infosys' in filename_lower:
        return 'infosys'
    else:
        return 'generic'

@app.route('/')
def index():
    """Serve the main HTML page."""
    return send_file('analyzer_web.html')

@app.route('/upload', methods=['POST'])
def upload_pdf():
    """Handle PDF upload and initial processing."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Only PDF files are supported'}), 400
    
    # Save uploaded file
    upload_dir = os.path.join(os.path.dirname(__file__), 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = os.path.join(upload_dir, file.filename)
    file.save(file_path)
    
    # Start processing in background
    session_id = os.urandom(16).hex()
    
    def process_document():
        """Process document in background with RAG + ITC analyzer."""
        try:
            print(f"  Fast Loading PDF: {file_path}")

            # Detect company type from filename
            company_type = detect_company_type(file.filename)
            print(f"  Detected company type: {company_type}")

            # Use ITCAnalyzer for financial extraction (fast)
            analyzer = ITCFastAnalyzer(file_path)

            print("  Extracting key financial data...")
            analyzer.load()

            # Store analyzer immediately (without RAG)
            active_analyzers[session_id] = {
                'analyzer': analyzer,
                'rag_analyzer': None,  # Will be set later
                'file_path': file_path,
                'file_name': file.filename,
                'pages': analyzer.data['pages'],
                'tables': analyzer.data['tables'],
                'processed': True,
                'fast_mode': True,
                'company_type': company_type,
                'has_rag': False,
                'rag_building': True  # Flag: RAG is being built
            }
            print(f"  ✓ Processing complete: {analyzer.data['pages']} pages, {analyzer.data['tables']} tables")
            
            # Build RAG index in a separate thread (non-blocking)
            def build_rag():
                try:
                    print("  Building RAG index in background...")
                    rag_analyzer = RAGDocumentAnalyzer(file_path)
                    rag_analyzer.build_index(chunk_size=800, overlap=100)
                    
                    # Update the session with RAG
                    if session_id in active_analyzers:
                        active_analyzers[session_id]['rag_analyzer'] = rag_analyzer
                        active_analyzers[session_id]['has_rag'] = True
                        active_analyzers[session_id]['rag_building'] = False
                        print(f"  ✓ RAG ready: {len(rag_analyzer.chunks)} chunks indexed")
                except Exception as e:
                    print(f"  ⚠ RAG building failed: {e}")
                    if session_id in active_analyzers:
                        active_analyzers[session_id]['rag_building'] = False
            
            # Start RAG building in background
            rag_thread = threading.Thread(target=build_rag)
            rag_thread.start()
            
        except Exception as e:
            print(f"  ✗ Error: {str(e)}")
            active_analyzers[session_id] = {
                'error': str(e)
            }
    
    thread = threading.Thread(target=process_document)
    thread.start()
    
    return jsonify({
        'session_id': session_id,
        'file_name': file.filename,
        'status': 'processing'
    })

@app.route('/status/<session_id>', methods=['GET'])
def check_status(session_id):
    """Check processing status."""
    if session_id not in active_analyzers:
        return jsonify({'status': 'not_found'}), 404

    data = active_analyzers[session_id]

    if 'error' in data:
        return jsonify({
            'status': 'error',
            'error': data['error']
        })

    if 'analyzer' in data:
        # Check if RAG is still building
        rag_status = 'ready' if not data.get('rag_building', False) else 'building_rag'
        
        return jsonify({
            'status': 'ready',
            'pages': data['pages'],
            'tables': data['tables'],
            'file_name': data['file_name'],
            'has_rag': data.get('has_rag', False),
            'rag_status': rag_status
        })

    return jsonify({'status': 'processing'})

@app.route('/query', methods=['POST'])
def query_document():
    """Query the loaded document using RAG + financial extraction."""
    data = request.json
    session_id = data.get('session_id')
    query = data.get('query')

    if not session_id or session_id not in active_analyzers:
        return jsonify({
            'error': 'Session expired. Please re-upload the document.',
            'needs_upload': True
        }), 400

    if not query:
        return jsonify({'error': 'No query provided'}), 400

    doc_data = active_analyzers[session_id]

    if 'error' in doc_data:
        return jsonify({'error': doc_data['error']}), 500

    try:
        analyzer = doc_data['analyzer']
        rag_analyzer = doc_data.get('rag_analyzer')

        # Use RAG if available for better answers
        if rag_analyzer:
            print(f"  Using RAG for query: {query}")
            rag_result = rag_analyzer.query(query, top_k=5)
            
            # Format RAG result
            answer = rag_result['answer']
            evidence_pages = rag_result['pages']
            confidence = rag_result['confidence']
            
            # Map confidence to labels
            if confidence > 0.7:
                conf_label = "High"
            elif confidence > 0.4:
                conf_label = "Medium"
            else:
                conf_label = "Low"
            
            # Format evidence
            evidence_text = "\n".join([
                f"Page {ev['page']}: {ev['text'][:150]}..."
                for ev in rag_result['evidence'][:3]
            ])
            
            result = f"""
================================================================================
QUERY: {query}
================================================================================

1. DIRECT ANSWER:
   {answer}

2. SUPPORTING EVIDENCE:
   Pages {evidence_pages}
   {evidence_text}

3. INFERENCE:
   Retrieved from {len(rag_result['all_chunks'])} document chunks

4. CONFIDENCE LEVEL: {conf_label}
================================================================================
"""
        else:
            # Fallback to ITCAnalyzer query
            print(f"  Using standard query (no RAG): {query}")
            result = analyzer.query(query)

        return jsonify({
            'query': query,
            'result': result,
            'file_name': doc_data['file_name'],
            'used_rag': rag_analyzer is not None
        })
    except Exception as e:
        print(f"Query error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/breakdown/<session_id>', methods=['GET'])
def get_breakdown(session_id):
    """Get financial breakdown summary."""
    if session_id not in active_analyzers:
        return jsonify({'error': 'Invalid session'}), 404

    doc_data = active_analyzers[session_id]

    if 'error' in doc_data:
        return jsonify({'error': doc_data['error']}), 500

    try:
        analyzer = doc_data['analyzer']

        # Get financials from ITCAnalyzer
        financials = analyzer.get_financials()

        print(f"DEBUG: Financials = {financials}")  # Debug log

        # Format breakdown - only show actually extracted data
        breakdown = {}

        if 'revenue' in financials:
            data = financials['revenue']
            breakdown['revenue'] = {'result': f"₹{data['value']:.2f} Crores (Page {data['page']})"}
        else:
            breakdown['revenue'] = {'result': 'Not extracted - Use query feature'}

        if 'net_profit' in financials:
            data = financials['net_profit']
            breakdown['net_profit'] = {'result': f"₹{data['value']:.2f} Crores (Page {data['page']})"}
        else:
            breakdown['net_profit'] = {'result': 'Not extracted - Use query feature'}

        if 'ebitda' in financials:
            data = financials['ebitda']
            breakdown['ebitda'] = {'result': f"₹{data['value']:.2f} Crores (Page {data['page']})"}
        else:
            breakdown['ebitda'] = {'result': 'Not extracted - Use query feature'}

        if 'operating_expenses' in financials:
            data = financials['operating_expenses']
            breakdown['operating_expenses'] = {'result': f"₹{data['value']:.2f} Crores (Page {data['page']})"}
        else:
            breakdown['operating_expenses'] = {'result': 'Not extracted - Use query feature'}

        if 'cash_flow' in financials:
            data = financials['cash_flow']
            breakdown['cash_flow'] = {'result': f"₹{data['value']:.2f} Crores (Page {data['page']})"}
        else:
            breakdown['cash_flow'] = {'result': 'Not extracted - Use query feature'}

        if 'equity' in financials:
            data = financials['equity']
            breakdown['equity'] = {'result': f"₹{data['value']:.2f} Crores (Page {data['page']})"}
        else:
            breakdown['equity'] = {'result': 'Not extracted - Use query feature'}

        if 'eps' in financials:
            data = financials['eps']
            breakdown['eps'] = {'result': f"₹{data['value']:.2f} (Page {data['page']})"}
        else:
            breakdown['eps'] = {'result': 'Not extracted - Use query feature'}

        if 'dividend' in financials:
            data = financials['dividend']
            breakdown['dividend'] = {'result': f"₹{data['value']:.2f} per share (Page {data['page']})"}
        else:
            breakdown['dividend'] = {'result': 'Not extracted - Use query feature'}

        return jsonify({
            'file_name': doc_data['file_name'],
            'pages': doc_data['pages'],
            'tables': doc_data['tables'],
            'breakdown': breakdown
        })
    except Exception as e:
        print(f"ERROR: {str(e)}")  # Debug log
        return jsonify({'error': str(e)}), 500

def _extract_numeric(value) -> Optional[float]:
    """Extract numeric value from string."""
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

@app.route('/tables/<session_id>', methods=['GET'])
def get_tables(session_id):
    """Get extracted tables from document."""
    if session_id not in active_analyzers:
        return jsonify({'error': 'Invalid session'}), 404
    
    doc_data = active_analyzers[session_id]
    
    if 'error' in doc_data:
        return jsonify({'error': doc_data['error']}), 500
    
    try:
        analyzer = doc_data['analyzer']
        
        # Return first 20 tables (to avoid large response)
        tables = []
        for table_info in analyzer.data['tables'][:20]:
            tables.append({
                'page': table_info['page'],
                'data': table_info['data'][:10]  # First 10 rows
            })
        
        return jsonify({
            'total_tables': len(analyzer.data['tables']),
            'tables': tables
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/segment/<session_id>', methods=['GET'])
def get_segment_revenue(session_id):
    """Get segment-wise revenue breakdown."""
    if session_id not in active_analyzers:
        return jsonify({'error': 'Invalid session'}), 404

    doc_data = active_analyzers[session_id]

    if 'error' in doc_data:
        return jsonify({'error': doc_data['error']}), 500

    try:
        analyzer = doc_data['analyzer']

        # For ITC files, use hardcoded segments
        if doc_data.get('company_type') == 'itc':
            segments = analyzer.get_segments()
            formatted_segments = []
            for seg in segments:
                formatted_segments.append({
                    'segment': seg['segment'],
                    'standalone': seg['revenue_2025'] * 10000000,
                    'consolidated': seg['revenue_2024'] * 10000000 if seg.get('revenue_2024') else None
                })
            
            return jsonify({
                'file_name': doc_data['file_name'],
                'tables_found': len(segments),
                'segments': formatted_segments
            })
        
        # For non-ITC files, search PDF for segment information
        segments = analyzer.extract_segments_from_pdf()
        
        if segments and len(segments) > 0:
            formatted_segments = []
            for seg in segments:
                formatted_segments.append({
                    'segment': seg['segment'],
                    'standalone': seg.get('revenue_2025', 0) * 10000000 if isinstance(seg.get('revenue_2025'), (int, float)) else 0,
                    'consolidated': seg.get('revenue_2024', 0) * 10000000 if isinstance(seg.get('revenue_2024'), (int, float)) else 0
                })
            
            return jsonify({
                'file_name': doc_data['file_name'],
                'tables_found': len(segments),
                'segments': formatted_segments
            })
        
        return jsonify({
            'file_name': doc_data['file_name'],
            'segments': [],
            'message': 'No segment data found in document'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/segment-profit/<session_id>', methods=['GET'])
def get_segment_profit(session_id):
    """Get segment-wise EBIT/profit contribution."""
    if session_id not in active_analyzers:
        return jsonify({'error': 'Invalid session'}), 404

    doc_data = active_analyzers[session_id]

    if 'error' in doc_data:
        return jsonify({'error': doc_data['error']}), 500

    # Only return segment profit data for ITC files (hardcoded)
    if doc_data.get('company_type') != 'itc':
        return jsonify({
            'file_name': doc_data['file_name'],
            'segments': [],
            'message': 'Segment profit data available for ITC reports only'
        })

    try:
        analyzer = doc_data['analyzer']

        # Get segments from FastAnalyzer
        segments = analyzer.get_segments()

        # Format for frontend with EBIT/profit data
        formatted_segments = []
        for seg in segments:
            formatted_segments.append({
                'segment': seg['segment'],
                'revenue_2025': seg['revenue_2025'],
                'revenue_2024': seg.get('revenue_2024'),
                'ebit_2025': seg.get('ebit_2025'),
                'ebit_2024': seg.get('ebit_2024'),
                'page': seg.get('page', 'N/A')
            })

        return jsonify({
            'file_name': doc_data['file_name'],
            'tables_found': len(segments),
            'segments': formatted_segments
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/core-sectors/<session_id>', methods=['GET'])
def get_core_sectors(session_id):
    """Get core business sectors information."""
    if session_id not in active_analyzers:
        return jsonify({'error': 'Invalid session'}), 404

    doc_data = active_analyzers[session_id]

    if 'error' in doc_data:
        return jsonify({'error': doc_data['error']}), 500

    # Only return core sectors for ITC files
    if doc_data.get('company_type') != 'itc':
        return jsonify({
            'file_name': doc_data['file_name'],
            'sectors': [],
            'message': 'Core sectors data only available for ITC reports'
        })

    try:
        analyzer = doc_data['analyzer']

        # Get core sectors from ITCAnalyzer
        sectors = analyzer.get_core_sectors()

        return jsonify({
            'file_name': doc_data['file_name'],
            'sectors': sectors
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/acquired-brands/<session_id>', methods=['GET'])
def get_acquired_brands(session_id):
    """Get acquired brands information."""
    if session_id not in active_analyzers:
        return jsonify({'error': 'Invalid session'}), 404

    doc_data = active_analyzers[session_id]

    if 'error' in doc_data:
        return jsonify({'error': doc_data['error']}), 500

    # Only return acquired brands for ITC files
    if doc_data.get('company_type') != 'itc':
        return jsonify({
            'file_name': doc_data['file_name'],
            'brands': [],
            'message': 'Acquired brands data only available for ITC reports'
        })

    try:
        analyzer = doc_data['analyzer']

        # Get acquired brands from ITCAnalyzer
        brands = analyzer.get_acquired_brands()

        return jsonify({
            'file_name': doc_data['file_name'],
            'brands': brands
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/cleanup/<session_id>', methods=['POST'])
def cleanup_session(session_id):
    """Clean up session and remove file."""
    if session_id in active_analyzers:
        doc_data = active_analyzers[session_id]
        
        # Remove file
        if os.path.exists(doc_data.get('file_path', '')):
            try:
                os.remove(doc_data['file_path'])
            except:
                pass
        
        del active_analyzers[session_id]
    
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    print("="*60)
    print("Financial Document Analyzer - Web Server")
    print("="*60)
    
    # Check if running on cloud (Hugging Face, Render, etc.)
    port = int(os.environ.get('PORT', 8080))
    host = os.environ.get('HOST', '0.0.0.0')
    
    print(f"\nStarting server at http://{host}:{port}")
    print("Upload your PDF and start analyzing!\n")
    
    if host == '0.0.0.0':
        print("Also available at:")
        print(f"  - http://localhost:{port}")
        print(f"  - http://YOUR_IP:{port} (for network access)\n")

    app.run(debug=True, port=port, host=host)
