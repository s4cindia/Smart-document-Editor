      # syntax=docker/dockerfile:1

############################
# Builder: install deps into a venv
############################
FROM python:3.12-slim AS builder

# System libs some wheels need at build/runtime (PyMuPDF, pdfplumber, pandas).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create an isolated virtualenv we can copy to the final image.
ENV VENV=/opt/venv
RUN python -m venv "$VENV"
ENV PATH="$VENV/bin:$PATH"

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir gunicorn

############################
# Runtime: slim final image
############################
FROM python:3.12-slim AS runtime

# Runtime shared libraries for the PDF / image stack.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

ENV VENV=/opt/venv
ENV PATH="$VENV/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy the prebuilt virtualenv from the builder stage.
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY . .

# Persisted, writable data lives under these dirs (mount as volumes).
# SDE_* env vars point the app at the mounted locations.
ENV SDE_DATA_DIR=/data \
    SDE_DB_PATH=/data/database/users.db
RUN mkdir -p /data/database uploads exports reports

# Run as an unprivileged user.
RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app /data
USER appuser

EXPOSE 5000

# app:app -> the `app` object created in app.py.
#
# IMPORTANT: exactly ONE worker. The app keeps the loaded dataset + undo/redo
# history in a single in-memory singleton (services/store.py), so multiple
# worker processes would each hold a different copy and corrupt the session.
# Scale concurrency with threads (the store is RLock-guarded), never workers.
# Long timeout because large Excel/PDF jobs can take a while.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", \
     "--workers", "1", "--threads", "8", "--timeout", "300", \
     "app:app"]
