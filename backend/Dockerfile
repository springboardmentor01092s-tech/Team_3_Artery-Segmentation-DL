FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Separate backend and ML Python environments
RUN python -m venv /opt/backend-venv \
    && python -m venv /opt/ml-venv

ENV PATH="/opt/backend-venv/bin:$PATH"

WORKDIR /app

# Install backend dependencies
COPY backend/requirements.txt /tmp/backend-requirements.txt
RUN /opt/backend-venv/bin/pip install --upgrade pip \
    && /opt/backend-venv/bin/pip install -r /tmp/backend-requirements.txt

# Install pinned CPU-only ML inference dependencies
COPY ml/requirements-inference.txt /tmp/ml-requirements.txt
RUN /opt/ml-venv/bin/pip install --upgrade pip \
    && /opt/ml-venv/bin/pip install -r /tmp/ml-requirements.txt

# Copy application source code (checkpoints and storage are excluded)
COPY backend/ /app/backend/
COPY ml/ /app/ml/

WORKDIR /app/backend

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
