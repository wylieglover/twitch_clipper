FROM python:3.11-slim

# Install system dependencies including CUDA support
RUN apt-get update && apt-get install -y \
    ffmpeg \
    streamlink \
    wget \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install Python deps
COPY requirements.txt .

RUN pip install --upgrade pip

# Install PyTorch with CPU support (CUDA not available on Cloud Run)
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# Install other requirements
RUN pip install --no-cache-dir -r requirements.txt

RUN python3 -c "import whisper; whisper.load_model('turbo')"

# Copy application code
COPY . .

# Cloud Run expects PORT env variable
ENV PORT=8080
EXPOSE 8080

# Start the FastAPI server
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8080"]