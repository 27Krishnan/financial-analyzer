FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements-lite.txt requirements.txt

# Install packages (faster, no ML models)
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY analyzer_server.py .
COPY analyzer_web.html .
COPY ITCAnalyzer.py .
COPY RAGDocumentAnalyzer.py .

# Create uploads directory
RUN mkdir -p uploads

# Expose port
EXPOSE 8080

# Set environment variables
ENV PORT=8080
ENV HOST=0.0.0.0

# Run the application
CMD ["python", "analyzer_server.py"]
