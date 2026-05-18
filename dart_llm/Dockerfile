FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir sentencepiece

COPY app/ ./app/
COPY core/ ./core/
COPY schemas/ ./schemas/
COPY scripts/ ./scripts/
COPY main.py .

ENV LLM_MODEL_PATH=/app/model/merged
ENV PORT=8080

EXPOSE 8080

CMD ["sh", "-c", "python scripts/download_model.py && uvicorn main:app --host 0.0.0.0 --port 8080"]