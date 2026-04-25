FROM python:3.11-slim

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt 

# torch CPU 전용 설치 (GPU 버전 제외 → 이미지 ~1GB 절감)
RUN pip install --no-cache-dir --force-reinstall \
    torch==2.4.1+cpu \
    --index-url https://download.pytorch.org/whl/cpu

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
