FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git jq && rm -rf /var/lib/apt/lists/*

# ★ /app/backend を作業ディレクトリに
WORKDIR /app/backend

# ★ 依存ファイルだけ先にコピー（キャッシュ有効化）
COPY backend/pyproject.toml ./pyproject.toml
COPY backend/requirements.txt ./requirements.txt

# ★ ここで requirements を入れる（requirements に -e . があっても /app/backend を指す）
RUN pip install --upgrade pip && pip install -r requirements.txt

# ★ 残りのソースをコピー
COPY backend .
COPY indexer /app/indexer
COPY scripts /app/scripts

# requirements に -e . が無い場合だけ有効化
# RUN pip install --no-cache-dir -e .

CMD ["uvicorn", "texgrep.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
