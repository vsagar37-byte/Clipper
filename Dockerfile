FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg nodejs fonts-dejavu-core fonts-noto-core fonts-noto-extra ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt
ARG INSTALL_WHISPER=true
RUN if [ "$INSTALL_WHISPER" = "true" ]; then pip install "faster-whisper>=1.1,<2"; fi
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/
RUN mkdir -p /app/data
ENV CLIPFORGE_DATA=/app/data MAX_UPLOAD_MB=200 MAX_DURATION_SECONDS=3600 WHISPER_MODEL=tiny
EXPOSE 10000
CMD ["sh","-c","exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1"]
