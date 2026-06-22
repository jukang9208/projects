# 파이썬 3.11 환경 사용
FROM python:3.11-slim

# 시스템 의존성 설치 (lxml, pandas 빌드용)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 설정
WORKDIR /app

# 라이브러리 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사 (static 폴더 포함)
COPY . .

# 실행 명령 (포트는 Cloud Run 기본 포트인 8080 사용)
ENV PORT=8080
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]