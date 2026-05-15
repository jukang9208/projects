FROM python:3.11-slim

WORKDIR /app

# llama-cpp-python CPU 빌드에 필요한 패키지
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY core/ ./core/

# GGUF 모델은 빌드 시점에 포함하거나, GCS/HF에서 다운로드
# 환경변수로 경로 지정
ENV GGUF_MODEL_PATH=/app/model/model-q4_k_m.gguf
ENV PORT=8080

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
