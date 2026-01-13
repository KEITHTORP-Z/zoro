FROM python:3.10-slim

# Install system deps
RUN apt-get update && \
    apt-get install -y curl ffmpeg nodejs npm && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["bash", "-c", "uvicorn react:app --host 0.0.0.0 --port ${PORT:-8000}"]
