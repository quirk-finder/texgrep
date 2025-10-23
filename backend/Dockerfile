FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt

COPY backend /app/backend
COPY indexer /app/indexer
COPY scripts /app/scripts

WORKDIR /app/backend

RUN pip install --no-cache-dir -e .

CMD ["uvicorn", "texgrep.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
