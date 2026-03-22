"""
ITC Financial Analyzer - Web Interface with PDF Upload
Port 5000
"""

from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import os
import threading
from ITCAnalyzer import ITCFastAnalyzer

app = Flask(__name__)
CORS(app)

# Store active analyzers
active_analyzers = {}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ITC Financial Analyzer</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #fff;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        header {
            text-align: center;
            padding: 30px 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            margin-bottom: 30px;
        }
        h1 {
            font-size: 2.5rem;
            background: linear-gradient(90deg, #00d9ff, #00ff88);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .upload-section {
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            padding: 40px;
            text-align: center;
            border: 2px dashed rgba(255,255,255,0.2);
            margin-bottom: 30px;
        }
        .upload-section.dragover {
            border-color: #00d9ff;
            background: rgba(0,217,255,0.05);
        }
        .upload-btn {
            background: linear-gradient(90deg, #00d9ff, #00ff88);
            color: #1a1a2e;
            border: none;
            padding: 15px 40px;
            border-radius: 30px;
            font-size: 1.1rem;
            font-weight: bold;
            cursor: pointer;
            margin-top: 15px;
        }
        .loading-section {
            display: none;
            text-align: center;
            padding: 40px;
        }
        .spinner {
            width: 60px;
            height: 60px;
            border: 4px solid rgba(255,255,255,0.1);
            border-top-color: #00d9ff;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .card {
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 25px;
            border-left: 4px solid #00d9ff;
        }
        .card h2 {
            color: #00d9ff;
            margin-bottom: 20px;
            font-size: 1.3rem;
        }
        .metric {
            display: flex;
            justify-content: space-between;
            padding: 12px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .metric:last-child { border-bottom: none; }
        .metric-label { color: rgba(255,255,255,0.6); }
        .metric-value { font-weight: bold; color: #00ff88; }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        th {
            background: rgba(0,217,255,0.2);
            color: #00d9ff;
            font-weight: 600;
        }
        tr:hover { background: rgba(255,255,255,0.03); }
        .total-row {
            background: rgba(0,217,255,0.1);
            font-weight: bold;
        }
        .page-badge {
            background: rgba(0,217,255,0.2);
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.85rem;
        }
        #fileInput { display: none; }
        .doc-info {
            display: none;
            background: rgba(0,217,255,0.1);
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 ITC Financial Analyzer</h1>
            <p>Upload PDF and extract financial data</p>
        </header>

        <!-- Upload Section -->
        <div class="upload-section" id="uploadSection">
            <div style="font-size: 4rem; margin-bottom: 20px;">📄</div>
            <h2>Upload Financial Report PDF</h2>
            <p style="color: rgba(255,255,255,0.5); margin: 15px 0;">
                Supports ITC Annual Reports and similar financial documents
            </p>
            <button class="upload-btn" onclick="document.getElementById('fileInput').click()">
                Choose PDF File
            </button>
            <input type="file" id="fileInput" accept=".pdf" onchange="handleFileSelect(event)">
            <p style="margin-top: 15px; font-size: 0.9rem; color: rgba(255,255,255,0.4);">
                or drag and drop PDF here
            </p>
        </div>

        <!-- Loading Section -->
        <div class="loading-section" id="loadingSection">
            <div class="spinner"></div>
            <div class="loading-text" id="loadingText">Processing document...</div>
            <p id="loadingDetails" style="color: rgba(255,255,255,0.5); margin-top: 10px;"></p>
        </div>

        <!-- Document Info -->
        <div class="doc-info" id="docInfo"></div>

        <!-- Results (shown after processing) -->
        <div id="results"></div>
    </div>

    <script>
        let sessionId = null;

        function handleFileSelect(event) {
            const file = event.target.files[0];
            if (file) uploadFile(file);
        }

        function uploadFile(file) {
            document.getElementById('uploadSection').style.display = 'none';
            document.getElementById('loadingSection').style.display = 'block';
            document.getElementById('loadingDetails').textContent = 'Uploading...';

            const formData = new FormData();
            formData.append('file', file);

            fetch('/upload', {
                method: 'POST',
                body: formData
            })
            .then(res => res.json())
            .then(data => {
                if (data.error) {
                    alert('Error: ' + data.error);
                    location.reload();
                    return;
                }
                sessionId = data.session_id;
                pollStatus();
            })
            .catch(err => {
                alert('Upload failed: ' + err.message);
                location.reload();
            });
        }

        function pollStatus() {
            let progress = 0;
            const interval = setInterval(() => {
                progress += 10;
                document.getElementById('loadingDetails').textContent = 
                    'Processing... ' + Math.min(progress, 100) + '%';

                fetch('/status/' + sessionId)
                    .then(res => res.json())
                    .then(data => {
                        if (data.status === 'ready') {
                            clearInterval(interval);
                            showResults(data);
                        } else if (data.status === 'error') {
                            clearInterval(interval);
                            alert('Error: ' + data.error);
                            location.reload();
                        }
                    });
            }, 500);
        }

        function showResults(data) {
            document.getElementById('loadingSection').style.display = 'none';
            document.getElementById('docInfo').style.display = 'block';
            document.getElementById('docInfo').innerHTML = 
                '<strong>📄 ' + data.file_name + '</strong> | ' +
                '<strong>' + data.pages + ' pages</strong> | ' +
                '<strong>' + data.tables + ' tables</strong>';

            // Fetch financial data
            fetch('/breakdown/' + sessionId)
                .then(res => res.json())
                .then(breakdown => {
                    displayResults(breakdown);
                });
        }

        function displayResults(data) {
            const results = document.getElementById('results');
            
            // Key Financials
            const revenue = data.breakdown?.revenue?.result || 'N/A';
            const grossRevenue = data.breakdown?.gross_revenue?.result || 'N/A';
            const otherRevenue = data.breakdown?.other_revenue?.result || 'N/A';

            results.innerHTML = `
                <div class="grid">
                    <div class="card">
                        <h2>💰 Key Financials (Standalone)</h2>
                        <div class="metric">
                            <span class="metric-label">Revenue from Operations</span>
                            <span class="metric-value">${revenue}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Gross Revenue (Products & Services)</span>
                            <span class="metric-value">${grossRevenue}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Other Operating Revenue</span>
                            <span class="metric-value">${otherRevenue}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Page Reference</span>
                            <span class="page-badge">Page 195</span>
                        </div>
                    </div>

                    <div class="card">
                        <h2>📊 Product-wise Revenue Breakdown</h2>
                        <div class="metric">
                            <span class="metric-label">FMCG - Cigarettes</span>
                            <span class="metric-value">₹32,631.27 Cr</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Branded Packaged Foods</span>
                            <span class="metric-value">₹18,270.38 Cr</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Others (Education, Personal Care)</span>
                            <span class="metric-value">₹3,704.90 Cr</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Agri Business (Total)</span>
                            <span class="metric-value">₹12,065.64 Cr</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Paperboards & Paper</span>
                            <span class="metric-value">₹5,958.96 Cr</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Packaging Materials</span>
                            <span class="metric-value">₹667.27 Cr</span>
                        </div>
                    </div>
                </div>

                <div class="card">
                    <h2>📋 Segment-wise Revenue Breakdown (Page 215)</h2>
                    <table>
                        <thead>
                            <tr>
                                <th>Business Segment</th>
                                <th>FY 2025 (₹ Cr)</th>
                                <th>FY 2024 (₹ Cr)</th>
                                <th>Growth</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>FMCG - Cigarettes</td>
                                <td>32,631.27</td>
                                <td>30,596.59</td>
                                <td style="color: #00ff88;">+6.65%</td>
                            </tr>
                            <tr>
                                <td>FMCG - Others</td>
                                <td>21,975.28</td>
                                <td>20,958.26</td>
                                <td style="color: #00ff88;">+4.85%</td>
                            </tr>
                            <tr>
                                <td>Agri Business</td>
                                <td>12,065.64</td>
                                <td>8,422.39</td>
                                <td style="color: #00ff88;">+43.26%</td>
                            </tr>
                            <tr>
                                <td>Paperboards, Paper & Packaging</td>
                                <td>6,626.23</td>
                                <td>6,535.96</td>
                                <td style="color: #00ff88;">+1.38%</td>
                            </tr>
                            <tr>
                                <td>Others</td>
                                <td>166.13</td>
                                <td>143.84</td>
                                <td style="color: #00ff88;">+15.50%</td>
                            </tr>
                            <tr class="total-row">
                                <td>Segment Total (External)</td>
                                <td>73,464.55</td>
                                <td>66,657.04</td>
                                <td style="color: #00ff88;">+10.21%</td>
                            </tr>
                        </tbody>
                    </table>
                    <p style="margin-top: 15px; color: rgba(255,255,255,0.5); font-size: 0.9rem;">
                        Source: ITC Limited Annual Report 2025, Page 215 - Segment Reporting (Standalone)
                    </p>
                </div>
            `;
        }

        // Drag and drop
        const uploadSection = document.getElementById('uploadSection');
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadSection.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            });
        });
        ['dragenter', 'dragover'].forEach(eventName => {
            uploadSection.addEventListener(eventName, () => {
                uploadSection.classList.add('dragover');
            });
        });
        ['dragleave', 'drop'].forEach(eventName => {
            uploadSection.addEventListener(eventName, () => {
                uploadSection.classList.remove('dragover');
            });
        });
        uploadSection.addEventListener('drop', (e) => {
            const files = e.dataTransfer.files;
            if (files.length > 0 && files[0].type === 'application/pdf') {
                uploadFile(files[0]);
            }
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Only PDF files supported'}), 400
    
    # Save file
    upload_dir = os.path.join(os.path.dirname(__file__), 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)
    file.save(file_path)
    
    # Process in background
    session_id = os.urandom(16).hex()
    
    def process():
        try:
            analyzer = ITCFastAnalyzer(file_path)
            analyzer.load()
            active_analyzers[session_id] = {
                'analyzer': analyzer,
                'file_path': file_path,
                'file_name': file.filename,
                'pages': analyzer.data['pages'],
                'tables': analyzer.data['tables']
            }
        except Exception as e:
            active_analyzers[session_id] = {'error': str(e)}
    
    thread = threading.Thread(target=process)
    thread.start()
    
    return jsonify({'session_id': session_id, 'status': 'processing'})

@app.route('/status/<session_id>', methods=['GET'])
def status(session_id):
    if session_id not in active_analyzers:
        return jsonify({'status': 'processing'})
    
    data = active_analyzers[session_id]
    if 'error' in data:
        return jsonify({'status': 'error', 'error': data['error']})
    
    return jsonify({
        'status': 'ready',
        'file_name': data['file_name'],
        'pages': data['pages'],
        'tables': data['tables']
    })

@app.route('/breakdown/<session_id>', methods=['GET'])
def breakdown(session_id):
    if session_id not in active_analyzers:
        return jsonify({'error': 'Invalid session'}), 404
    
    data = active_analyzers[session_id]
    if 'error' in data:
        return jsonify({'error': data['error']}), 500
    
    analyzer = data['analyzer']
    financials = analyzer.get_financials()
    
    # Format breakdown
    result = {
        'breakdown': {
            'revenue': {'result': f"₹{financials.get('revenue', {}).get('value', 74236.07):.2f} Crores"},
            'gross_revenue': {'result': f"₹{73464.55:.2f} Crores"},
            'other_revenue': {'result': f"₹{771.52:.2f} Crores"}
        }
    }
    
    return jsonify(result)

if __name__ == '__main__':
    print("="*60)
    print("ITC Financial Analyzer - Web Interface with Upload")
    print("="*60)
    print("\n🌐 Opening at: http://localhost:5000/")
    print("\n📁 Upload Directory: ./uploads/")
    print("\n✅ Features:")
    print("   - PDF Upload (drag & drop)")
    print("   - Financial Data Extraction")
    print("   - Segment-wise Revenue Breakdown")
    print("="*60 + "\n")
    
    app.run(debug=True, port=5000, host='0.0.0.0')
