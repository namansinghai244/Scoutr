FROM python:3.12-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render exposes service env vars as Docker build args. Keep secrets in the
# builder stage so they are not persisted into the final runtime image.
ARG KAGGLE_USERNAME
ARG KAGGLE_KEY
ARG KAGGLE_API_TOKEN
ARG EMBEDDING_MODEL_NAME=all-MiniLM-L6-v2
ARG EMBEDDING_MODEL_DIR=data/models/all-MiniLM-L6-v2

ENV KAGGLE_USERNAME=${KAGGLE_USERNAME}
ENV KAGGLE_KEY=${KAGGLE_KEY}
ENV KAGGLE_API_TOKEN=${KAGGLE_API_TOKEN}
ENV EMBEDDING_MODEL_NAME=${EMBEDDING_MODEL_NAME}
ENV EMBEDDING_MODEL_DIR=${EMBEDDING_MODEL_DIR}

RUN python scripts/download_datasets.py \
    && python scripts/ingest_products.py \
    && python scripts/build_embeddings.py --max-products 200000 --min-rating 3.5 \
    && rm -rf data/datasets


FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY --from=builder /usr/local /usr/local
COPY . .
COPY --from=builder /app/data /app/data

EXPOSE 10000

CMD ["/bin/sh", "-c", "gunicorn main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-10000}"]
