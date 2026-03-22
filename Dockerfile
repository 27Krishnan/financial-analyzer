FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    poppler-utils \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy lite requirements (no heavy ML)
COPY requirements-lite.txt /app/requirements.txt

# Install packages (fast - ~2 minutes)
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
