FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir yt-dlp==2026.10.21
WORKDIR /app
COPY proxy.py entrypoint.py ./
USER 65532:65532
ENTRYPOINT ["python", "/app/entrypoint.py"]
