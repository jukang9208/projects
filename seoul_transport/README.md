# 서울시 지하철 승하차 분석 · Lakehouse Pipeline

서울 열린데이터광장의 지하철 승하차 데이터를 수집하고,  
**Apache Spark + Delta Lake** 기반 메달리온 아키텍처로 변환한 뒤  
**FastAPI**로 서빙하는 데이터 엔지니어링 프로젝트입니다.

**Live demo →** [jukang.tech/projects/seoul_transport](https://jukang.tech/projects/seoul_transport)

---

## Architecture

```
Seoul Open Data API
        │
        ▼
  [Ingestion]  subway_collector.py
        │  Raw CSV (일별)
        ▼
  [Raw Layer]  GCS gs://jukang-transport/raw/subway/YYYYMM/subway_YYYYMMDD.csv
        │
        ▼  Spark
  [Silver Layer]  Delta Table (파티션: use_ymd)
        │
        ▼  Spark aggregation
  [Gold Layer]  Delta Tables
        │  ├─ congestion_daily_avg   (역별 평균 일 승하차)
        │  ├─ congestion_weekly      (역별·요일별 평균)
        │  ├─ congestion_monthly     (역별·월별 집계)
        │  ├─ transfer_stations      (환승역 목록)
        │  └─ transfer_pattern       (환승역별·호선별 이용 패턴)
        │
        ▼
  [FastAPI]  Cloud Run
        │
        ▼
  [Next.js Frontend]  jukang.tech
```

---

## Tech Stack

| 역할 | 기술 |
|---|---|
| 데이터 수집 | Python requests · 서울 열린데이터광장 API |
| 배치 처리 | Apache Spark (PySpark) · Delta Lake |
| 스토리지 | Google Cloud Storage (Delta Lake 저장소) |
| 오케스트레이션 | Apache Airflow DAG (로컬 스케줄링 참고용) |
| API 서버 | FastAPI · Uvicorn |
| 배포 | GCP Cloud Run · Docker |
| 프론트엔드 | Next.js · react-plotly.js |

---

## 디렉토리 구조

```
seoul_transport/
├── core/
│   ├── config.py          # 환경변수 설정 (GCS/로컬 경로 자동 전환)
│   └── spark.py           # SparkSession 생성 (Windows/Linux 분기, GCS 커넥터)
├── ingestion/
│   └── subway_collector.py  # 서울 API → Raw CSV 저장 (로컬 or GCS)
├── spark_jobs/
│   └── subway_transform.py  # Raw→Silver / Silver→Gold 변환 잡
├── services/
│   └── subway_service.py    # Gold 테이블 읽기 서비스 레이어
├── app/
│   └── subway_router.py     # FastAPI 라우터 (lazy SparkSession init)
├── scripts/
│   ├── collect_range.py     # 날짜 범위 일괄 수집
│   ├── build_lakehouse.py   # 날짜 범위 Silver/Gold 빌드
│   └── run_pipeline_gcp.py  # Cloud Run Jobs 진입점
├── dags/
│   └── transport_pipeline_dag.py  # Airflow DAG 정의
├── schemas/
│   └── subway.py            # Pydantic 응답 스키마
├── main.py                  # FastAPI 앱 진입점
├── Dockerfile               # API 서버 이미지
├── Dockerfile.pipeline      # 파이프라인 잡 이미지
└── requirements.txt
```

---

## 로컬 실행

### 1. 환경 변수 설정

`.env` 파일을 생성합니다. `GCS_BUCKET_NAME`을 비워두면 `data/` 폴더 기준 로컬 모드로 동작합니다.

```env
SEOUL_API_KEY=your_seoul_api_key

# GCS 연동 (비워두면 로컬 모드)
GCS_BUCKET_NAME=
GCS_PROJECT_ID=
GOOGLE_APPLICATION_CREDENTIALS=
```

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

### 3. 데이터 수집 (특정 날짜 범위)

```bash
python scripts/collect_range.py 20260401 20260430
```

### 4. Lakehouse 빌드 (Silver → Gold)

```bash
python scripts/build_lakehouse.py 20260401 20260430
```

### 5. API 서버 실행

```bash
uvicorn main:app --reload
```

---

## GCS 연동 모드

`.env`에 GCS 정보를 추가하면 Raw/Silver/Gold 모두 GCS에 저장됩니다.

```env
GCS_BUCKET_NAME=jukang-transport
GCS_PROJECT_ID=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
```

경로 전환은 `core/config.py`의 `effective_*_path` 프로퍼티가 자동으로 처리합니다.

```
로컬: data/raw/subway/...
GCS:  gs://jukang-transport/raw/subway/...
```

---

## GCP Cloud Run 배포

```bash
# API 서버 배포
gcloud run deploy jukang-transport \
  --source . \
  --region asia-northeast1 \
  --memory 2Gi \
  --set-env-vars GCS_BUCKET_NAME=jukang-transport,GCS_PROJECT_ID=your-project

# 파이프라인 잡 배포 (Cloud Run Jobs)
gcloud run jobs deploy jukang-transport-pipeline \
  --image gcr.io/your-project/transport-pipeline \
  --region asia-northeast1
```

SparkSession은 첫 API 호출 시 초기화되므로(lazy init) Cloud Run의 cold start 제한에 걸리지 않습니다.

---

## API Endpoints

| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/usage/ranking` | 역별 누적 승차량 TOP N |
| GET | `/usage/weekly?station=강남` | 특정 역의 요일별 평균 승하차 |
| GET | `/transfer/busiest` | 환승역 승차량 TOP 10 |

---

## Airflow DAG

`dags/transport_pipeline_dag.py`에 매일 오전 6시 실행되는 DAG가 정의되어 있습니다.

```
collect_subway  →  transform_subway
(서울 API 수집)    (Spark Raw→Silver→Gold)
```

`context["ds_nodash"]`로 실행 날짜를 `YYYYMMDD` 형식으로 자동 전달받아 해당 날짜 데이터를 처리합니다.

---

## Gold 테이블 스키마

**congestion_daily_avg** — 역별 평균 일 승하차
```
line_num, subway_sta_nm, avg_ride, avg_alight, max_ride, max_alight, data_days
```

**congestion_weekly** — 역별 요일별 평균
```
line_num, subway_sta_nm, day_of_week (1=일~7=토), is_weekend, avg_ride, avg_alight
```

**congestion_monthly** — 역별 월별 집계
```
line_num, subway_sta_nm, year_month, total_ride, total_alight
```

**transfer_stations** — 환승역 목록
```
subway_sta_nm, line_count
```

**transfer_pattern** — 환승역별 호선별 이용 패턴
```
subway_sta_nm, line_num, avg_ride, avg_alight, total_ride, total_alight
```

---

## 데이터 출처

- **서울 열린데이터광장** — 서울시 지하철 호선별 역별 승하차 인원  
  https://data.seoul.go.kr
