FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi \
    "uvicorn[standard]" \
    pydantic

COPY main.py .
COPY static/ static/

RUN mkdir -p /data

EXPOSE 8081

ENV MEMORY_API_KEY=palkia-memory-2026
ENV DB_PATH=/data/memory.db

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8081"]
