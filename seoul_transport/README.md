# 서울시 지하철 Lakehouse Pipeline

서울 열린데이터광장의 지하철 승하차 데이터를 수집하고,  
**Apache Spark + Delta Lake** 기반 메달리온 아키텍처로 변환한 뒤  
**FastAPI**로 서빙하는 End-to-End 데이터 엔지니어링 프로젝트입니다.

- 서울시 **전체 호선** 역별 **일별·시간대별** 승하차 데이터 자동 수집
- **메달리온 아키텍처** (Raw → Silver → Gold) · Delta Lake MERGE 증분 처리
- **Gold 테이블 8종** — 혼잡도·환승·시간대별 패턴 분석
- **GCP Cloud Run** 기반 API 서버 · **Cloud Run Jobs + Cloud Scheduler** 매일 자동 파이프라인

**Live Demo →** [jukang.tech](https://jukang.tech)

---

## Architecture

```
Seoul Open Data API
(CardSubwayStatsNew · CardSubwayTime)
        │
        ▼ Python requests
┌──────────────────────────────┐
│  Raw Layer  (GCS)            │
│  subway/YYYYMM/subway_YYYYMMDD.csv  ←  일별 승하차  │
│  subway_hourly/subway_hourly_YYYYMM.csv ← 시간대별  │
└──────────────┬───────────────┘
               │ PySpark
               ▼
┌──────────────────────────────┐
│  Silver Layer  (Delta Lake)  │
│  subway          (파티션: use_ymd)   │
│  subway_hourly   (파티션: use_mm)    │
└──────────────┬───────────────┘
               │ PySpark aggregation
               ▼
┌──────────────────────────────────────────┐
│  Gold Layer  (Delta Lake)                │
│  congestion_daily_avg    역별 평균 일 승하차  │
│  congestion_weekly       요일별 패턴         │
│  congestion_monthly      월별 집계           │
│  congestion_hourly_avg   시간대별 평균 승하차 │
│  congestion_peak_hours   역별 피크타임 TOP3  │
│  transfer_stations       환승역 목록          │
│  transfer_pattern        환승역 호선별 패턴   │
│  transfer_monthly        환승역 월별 집계     │
└──────────────┬───────────────────────────┘
               │
               ▼
     FastAPI (Cloud Run)
               │
               ▼
     Next.js Frontend (jukang.tech)
```

**파이프라인 스케줄**

```
Cloud Scheduler (매일 21:00 KST)
    └─▶ Cloud Run Jobs (jukang-transport-pipeline)
            └─▶ collect (서울 API → GCS Raw)   ← 당일 기준 3일 전 확정 데이터
            └─▶ raw_to_silver (Spark)
            └─▶ silver_to_gold_incremental (Delta MERGE)
```

---

## Tech Stack

| 역할 | 기술 |
|---|---|
| 데이터 수집 | Python · 서울 열린데이터광장 Open API |
| 배치 처리 | Apache Spark 3.5 (PySpark) · Delta Lake 4.x |
| 스토리지 | Google Cloud Storage (Delta Lake 저장소) |
| 증분 처리 | Delta Lake MERGE (중복 없는 일별 upsert) |
| API 서버 | FastAPI · Uvicorn |
| 자동 파이프라인 | GCP Cloud Run Jobs · Cloud Scheduler |
| 배포 | GCP Cloud Run · Docker · Cloud Build |
| 오케스트레이션 참고 | Apache Airflow DAG (`dags/`) |
| 로컬 개발 | Windows + Anaconda (Java 17 자동 감지) |

---

## 디렉토리 구조

```
seoul_transport_lakehouse/
├── core/
│   ├── config.py              # 환경변수 · GCS/로컬 경로 자동 전환
│   └── spark.py               # SparkSession 팩토리 (Windows/GCP 분기, Java 17)
│
├── ingestion/
│   └── subway_collector.py    # 일별·시간대별 데이터 수집 (GCS or 로컬 저장)
│
├── spark_jobs/
│   └── subway_transform.py    # Raw→Silver / Silver→Gold / hourly 변환 잡
│
├── services/
│   └── subway_service.py      # UsageService · TransferService · HourlyService
│
├── app/
│   └── subway_router.py       # FastAPI 라우터 (lazy SparkSession 초기화)
│
├── scripts/
│   ├── collect_range.py       # 날짜 범위 일괄 수집
│   ├── build_lakehouse.py     # 날짜 범위 Silver/Gold 빌드 (일별)
│   ├── build_hourly.py        # 월별 시간대 데이터 Silver/Gold 빌드
│   ├── deduplicate_silver.py  # Silver 중복 제거 유틸
│   └── run_pipeline_gcp.py    # Cloud Run Jobs 진입점 (KST 날짜 · 3일 지연)
│
├── dags/
│   └── transport_pipeline_dag.py  # Airflow DAG (로컬 스케줄링 참고용)
│
├── schemas/
│   └── subway.py              # Pydantic 응답 스키마
│
├── main.py                    # FastAPI 앱 진입점
├── Dockerfile                 # API 서버 이미지 (jukang-transport 서비스)
├── Dockerfile.pipeline        # 파이프라인 이미지 (Cloud Run Jobs)
├── docker-compose.yml         # 로컬 개발용
└── requirements.txt
```

---

## 데이터 소스

| API | 형식 | 갱신 주기 | 비고 |
|---|---|---|---|
| CardSubwayStatsNew | 일별 역별 승하차 | 매일 3일 전 데이터 (21시 GCS 스케줄 실행) | YYYYMMDD 파라미터 |
| CardSubwayTime | 월별 시간대별 승하차 | 매월 5일 전달 데이터 | YYYYMM 파라미터, 최대 1000건/요청 |

- **일별 데이터**: `USE_YMD`, `SBWY_ROUT_LN_NM`(호선), `SBWY_STNS_NM`(역명), `GTON_TNOPE`(승차), `GTOFF_TNOPE`(하차)
- **시간대별 데이터**: `USE_MM`, `SBWY_ROUT_LN_NM`, `STTN`(역명), `HR_4_GET_ON_NOPE`~`HR_23_GET_ON_NOPE` (4~23시 Wide 포맷 → Silver에서 Long 변환)

---

## Gold 테이블 스키마

### 일별 분석 (daily pipeline)

**congestion_daily_avg** — 역별 전체 기간 평균 일 승하차
```
line_num, subway_sta_nm, avg_ride, avg_alight, max_ride, max_alight, data_days
```

**congestion_weekly** — 역별·요일별 평균 (1=일, 7=토)
```
line_num, subway_sta_nm, day_of_week, is_weekend, avg_ride, avg_alight
```

**congestion_monthly** — 역별·월별 총 승하차
```
line_num, subway_sta_nm, year_month(yyyy-MM), total_ride, total_alight
```

**transfer_stations** — 2개 이상 호선이 지나는 환승역
```
subway_sta_nm, line_count
```

**transfer_pattern** — 환승역별·호선별 이용 패턴
```
subway_sta_nm, line_num, avg_ride, avg_alight, total_ride, total_alight, tp_cnt
```

**transfer_monthly** — 환승역별·월별 승차 합계
```
subway_sta_nm, year_month, total_ride
```

### 시간대별 분석 (hourly · 월별 갱신)

**congestion_hourly_avg** — 역·호선·시간대별 평균 월 누계 승하차
```
line_num, subway_sta_nm, hour(4~23), avg_ride, avg_alight, max_ride, data_months
```

**congestion_peak_hours** — 역별 승차 기준 피크타임 상위 3시간대
```
subway_sta_nm, hour, avg_ride
```

---

## API Endpoints

Base URL: `https://jukang-transport-38796498369.asia-northeast1.run.app/api/v1`

### 일별 승하차

| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/subway/usage/meta` | 수집 기간·역 수 메타 정보 |
| GET | `/subway/usage/daily` | 역별 평균 일 승하차 (`?station=강남&line=2호선`) |
| GET | `/subway/usage/ranking` | 승차량 TOP N (`?line=2호선&limit=10`) |
| GET | `/subway/usage/weekly?station=강남` | 요일별 승하차 패턴 |
| GET | `/subway/usage/monthly?station=강남` | 월별 승하차 추이 |
| GET | `/subway/usage/trend?station=강남` | 일별 시계열 (`?start_date=2026-03-01`) |

### 환승역

| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/subway/transfer/stations` | 전체 환승역 목록 (호선 수 기준 정렬) |
| GET | `/subway/transfer/pattern?station=신도림` | 환승역 호선별 이용 패턴 |
| GET | `/subway/transfer/busiest` | 환승역 TOP 10 (`?month=2026-03`) |

### 시간대별 혼잡도

| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/subway/usage/hourly?station=강남` | 24시간 시간대별 평균 승하차 |
| GET | `/subway/usage/hourly/peak?station=강남` | 피크타임 상위 3시간대 |
| GET | `/subway/usage/hourly/ranking?hour=8` | 특정 시각 혼잡 역 TOP N |
| GET | `/subway/usage/hourly/heatmap` | 시간대×역 히트맵 데이터 (`?line=2호선`) |

---

## 로컬 실행

### 1. 환경 변수 설정

`.env` 파일 생성. `GCS_BUCKET_NAME`을 비우면 `data/` 폴더 기준 로컬 모드로 동작합니다.

```env
SEOUL_API_KEY=your_seoul_api_key

# GCS 연동 (비워두면 로컬 모드)
GCS_BUCKET_NAME=
GCS_PROJECT_ID=
GOOGLE_APPLICATION_CREDENTIALS=path/to/key.json
```

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

> Windows + Anaconda 환경에서는 `core/spark.py`가 Anaconda 번들 Java 17을 자동 감지합니다.

### 3. 일별 데이터 수집 및 빌드

```bash
# 날짜 범위 수집
python scripts/collect_range.py 20260401 20260430

# Silver → Gold 빌드
python scripts/build_lakehouse.py 20260401 20260430
```

### 4. 시간대별 혼잡도 데이터 빌드

```bash
# 전체 (최근 2년치 자동)
python scripts/build_hourly.py

# 월 범위 지정
python scripts/build_hourly.py 202601 202604
```

### 5. API 서버 실행

```bash
uvicorn main:app --reload
# http://localhost:8000/docs
```

---

## GCP 배포

### API 서버 (Cloud Run Service)

```bash
gcloud run deploy jukang-transport \
  --source . \
  --region asia-northeast1
```

### 파이프라인 잡 (Cloud Run Jobs)

`Dockerfile.pipeline` 기준으로 이미지를 빌드해야 합니다.

```bash
# Cloud Build로 Dockerfile.pipeline 이미지 빌드
cat > /tmp/cb.yaml << 'EOF'
steps:
- name: gcr.io/cloud-builders/docker
  args: [build, -t, IMAGE_TAG, -f, Dockerfile.pipeline, .]
- name: gcr.io/cloud-builders/docker
  args: [push, IMAGE_TAG]
images: [IMAGE_TAG]
EOF

gcloud builds submit --config /tmp/cb.yaml \
  --substitutions _IMAGE_TAG=asia-northeast1-docker.pkg.dev/PROJECT/repo/jukang-pipeline:latest .

# Cloud Run Jobs 업데이트
gcloud run jobs update jukang-transport-pipeline \
  --image IMAGE_TAG \
  --region asia-northeast1
```

### 환경변수 (Cloud Run)

```
GCS_BUCKET_NAME   = jukang-transport
GCS_PROJECT_ID    = your-project-id
SEOUL_API_KEY     = your_key
```

---

## 증분 파이프라인 설계

Cloud Run Jobs는 매일 21:00 KST에 실행되며 **3일 전 날짜** 데이터를 처리합니다.  
(서울 API는 OA-12914 공식 명세 기준 3일 전 데이터가 확정 갱신됩니다.)

```
Cloud Scheduler → Cloud Run Job → run_pipeline_gcp.py
    1. collect(date)          # API → GCS Raw CSV
    2. raw_to_silver(date)    # CSV → Delta MERGE (중복 방지)
    3. silver_to_gold_incremental(date)  # 6개 Gold 테이블 MERGE 갱신
```

Delta MERGE 전략으로 재실행 시에도 데이터 중복이 발생하지 않습니다.

---

## EDA 노트북

| 파일 | 내용 |
|---|---|
| `01_eda.ipynb` | 기초 탐색 — 역별 승하차 분포, 결측치 확인 |
| `02_congestion_analysis.ipynb` | 혼잡도 분석 — 호선별·요일별·월별 패턴 |
| `03_transfer_analysis.ipynb` | 환승역 분석 — 환승 부담 지수, 호선별 이용 비중 |
| `04_hourly_analysis.ipynb` | 시간대별 분석 — 출퇴근 피크·호선 비교·역×시간 히트맵 |

---

## 데이터 출처

- **서울 열린데이터광장** — 서울시 지하철 호선별 역별 승하차 인원 정보  
  https://data.seoul.go.kr/dataList/OA-12914
