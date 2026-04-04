FROM python:3.11-slim

WORKDIR /app

RUN apt-get update -qq && apt-get install -y -qq libpq-dev gcc && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    fastapi \
    "uvicorn[standard]" \
    pydantic \
    psycopg2-binary \
    pgvector \
    fastembed

# Pre-download the embedding model so startup is instant
RUN python -c "from fastembed import TextEmbedding; list(TextEmbedding('BAAI/bge-small-en-v1.5').embed(['warmup']))"

COPY . .

EXPOSE 8081

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8081"]
