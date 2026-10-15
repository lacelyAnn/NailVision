FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 HF_HOME=/models/hf MODEL_DIR=/models/sd15-inpainting
# CPU-only torch (the default wheel pulls ~2 GB of CUDA libraries)
RUN pip install --no-cache-dir torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY nv_utils.py server.py ./
# Weights (~2 GB) are downloaded on first generation into /models -> mount a persistent disk there
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT:-10000}"]
