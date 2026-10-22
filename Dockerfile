# Multi-stage / lightweight Python build
FROM python:3.11-slim

# Set environment flags
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000 \
    MOCK_LLM=1

WORKDIR /app

# Install system dependencies if required
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy application files
COPY . .

# Expose default port
EXPOSE 5000

# Run with production WSGI server
CMD ["gunicorn", "app:create_app()", "--bind", "0.0.0.0:5000", "--workers", "1", "--timeout", "120"]
