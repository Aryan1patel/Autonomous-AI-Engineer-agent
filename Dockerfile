FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8501

WORKDIR /app

# Install system dependencies (lsof is required by the API test runner to manage port 9000)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    lsof \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Ensure generated directory exists with write permissions
RUN mkdir -p /app/generated

EXPOSE 8501 9000

# Run Streamlit on the dynamic PORT provided by host (or 8501 by default)
CMD ["sh", "-c", "streamlit run engineer_app.py --server.port=${PORT:-8501} --server.address=0.0.0.0"]
