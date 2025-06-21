# syntax=docker/dockerfile:1.4

ARG PYTHON_VERSION=3.12.4
FROM python:${PYTHON_VERSION}-slim as base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Manila

WORKDIR /app

# Install system dependencies in one go to reduce layers and avoid extra update steps
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libxml2 \
    libxslt1.1 \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libjpeg-dev \
    libpng-dev \
    libwebp-dev \
    fonts-liberation \
    fonts-freefont-ttf \
    tzdata \
    curl \
    default-libmysqlclient-dev \
    gcc \
    pkg-config \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Use pip cache if possible (Railway might ignore it, but doesn't hurt locally)
COPY requirements.txt .
RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Pre-load SentenceTransformer model during build
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# Create non-root user
ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/nonexistent" \
    --shell "/sbin/nologin" \
    --no-create-home \
    --uid "${UID}" \
    appuser

USER appuser

# Add app code (as late as possible to benefit from layer caching of dependencies)
COPY . .

EXPOSE 8000
CMD ["gunicorn", "between_ims.wsgi:application", "--bind=0.0.0.0:8000", "--timeout=300"]
