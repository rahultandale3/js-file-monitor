FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    jq \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create directories
RUN mkdir -p /storage/snapshots \
    /storage/diffs \
    /storage/database \
    /logs

# Make scripts executable
RUN chmod +x scripts/*.py scripts/*.sh

CMD ["python", "api/app.py"]
