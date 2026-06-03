# Eloify web interface. The committed braille headshots ship in the image, so no
# photo volume is needed — only Google Sheets credentials (see docker-compose.yml).
FROM python:3.12-slim

WORKDIR /app

# Install deps first (cached) using just the project metadata, then the source.
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir ".[web]"

EXPOSE 8000

# --workers 1 keeps the in-process TTL cache in web/data.py coherent.
CMD ["uvicorn", "eloify.web.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
