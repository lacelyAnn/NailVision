FROM python:3.14-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
# Cloudflare does the inpainting, so no torch/diffusers here: fits Render's free 512 MB
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY nv_utils.py server.py ./
COPY generation ./generation
RUN useradd --create-home app
USER app
EXPOSE 10000
# One worker only: jobs live in this process's memory. exec lets Render's SIGTERM reach uvicorn.
CMD ["sh", "-c", "exec uvicorn server:app --host 0.0.0.0 --port ${PORT:-10000}"]
