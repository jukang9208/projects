# DART 공시 분류기 v2.5

DART(금융감독원 전자공시시스템) 공시를 자동 조회·분류하고, 재무제표와 실시간 주가 데이터를 함께 제공하는 FastAPI 서비스입니다.

## 버전 히스토리

| 버전 | 기능 |
|---|---|
| v1 | BERT 파인튜닝 기반 공시 3분류 (`/classify`) |
| v2 | 공시 분류 + DART 재무제표 + 실시간 주가 통합 분석 (`/analyze`) |
| v2.5 | DART 공시 자동 조회 + 보고서 유형 자동 분류 (`/disclosures`) |

## 분류 카테고리

| 카테고리 | 설명 |
|---|---|
| 감사보고서 | 감사 의견, 핵심 감사 사항, 내부 통제 관련 내용 |
| 사업보고서 | 사업 현황, 재무 요약, 리스크 요인 관련 내용 |
| 유상증자 | 발행 목적, 조달 금액, 주주 희석 관련 내용 |

## 프로젝트 구조

```
dart_classifier/
├── 01_data_collection.ipynb  # DART API 공시 본문 수집
├── 02_finetune.ipynb         # klue/bert-base 파인튜닝
├── main.py                   # FastAPI 앱 엔트리포인트
├── app/
│   ├── classify.py           # POST /classify
│   ├── rag.py                # POST /rag/*
│   ├── analyze.py            # POST /analyze (v2)
│   └── disclosures.py        # GET  /disclosures (v2.5)
├── core/
│   └── config.py             # 환경변수 및 설정
├── schemas/
│   └── classify.py           # Pydantic 스키마 전체
├── services/
│   ├── classifier.py         # BERT 추론
│   ├── embedder.py           # Gemini 임베딩
│   ├── rag.py                # Supabase 벡터 검색
│   ├── financial.py          # DART 재무제표 수집 및 캐시 (v2)
│   ├── market.py             # 실시간 주가 조회 (v2)
│   └── disclosure.py         # 공시 자동 조회 + 분류 (v2.5)
├── scripts/
│   └── upload_corps.py       # DART 기업코드 DB 업로드
├── db/
│   └── init_v2.sql           # dart_corps 테이블 생성 SQL
├── models/                   # ⚠️ 미포함 (아래 참고)
├── Dockerfile
└── requirements.txt
```

## 모델 파일 안내

`models/` 폴더는 용량 문제로 저장소에 포함되지 않습니다.

로컬 실행 시 `02_finetune.ipynb`를 직접 실행하여 모델을 생성하거나, 아래 경로에 수동으로 배치합니다.

```
models/
└── dart_classifier/
    ├── config.json
    ├── model.safetensors
    ├── tokenizer.json
    └── tokenizer_config.json
```

## 학습 데이터

- **수집 기간**: 2022년 ~ 2024년
- **수집 건수**: 1,080건 → 전처리 후 979건
- **카테고리별**: 감사보고서 360건 / 사업보고서 319건 / 유상증자 300건
- **출처**: DART Open API (`document.xml`)

## 모델

- **베이스 모델**: `klue/bert-base`
- **태스크**: Sequence Classification (3-class)
- **입력**: 공시 본문 텍스트 (최대 512 토큰)
- **출력**: 카테고리 레이블 + 신뢰도 점수

## API

### GET /disclosures (v2.5 핵심)

기업명만 입력하면 최근 1년간 공시 목록을 자동 조회하고 유형을 분류합니다.

정기공시(A) · 주요사항보고서(B) · 외부감사(F) 유형을 대상으로 조회하며, 보고서명 키워드 기반으로 3개 카테고리에 자동 매핑합니다.

**Request**
```
GET /disclosures?corp_name=삼성전자&count=5
```

**Response**
```json
{
  "corp_name": "삼성전자",
  "corp_code": "00126380",
  "stock_code": "005930",
  "total": 5,
  "items": [
    {
      "rcept_no": "20260310002820",
      "rept_nm": "사업보고서 (2025.12)",
      "rcept_dt": "20260310",
      "flr_nm": "삼성전자",
      "label": "사업보고서",
      "score": null,
      "text_preview": null
    }
  ]
}
```

> `score`는 BERT 직접 분류 시에만 반환됩니다. 보고서명 키워드 매핑의 경우 `null`입니다.

### POST /analyze (v2 핵심)

공시 본문 분류와 기업 재무 데이터를 통합 분석합니다.

재무제표는 Supabase에 캐시되며, 주가는 매 요청마다 실시간으로 조회합니다.

**Request**
```json
{
  "text": "당사는 시설투자 목적으로 보통주 500만 주를 유상증자 결정하였습니다...",
  "corp_name": "삼성전자",
  "year": 2023
}
```

**Response**
```json
{
  "classify": { "label": "유상증자", "score": 0.968 },
  "financial": {
    "corp_name": "삼성전자",
    "stock_code": "005930",
    "year": 2023,
    "revenue": 258935494000000,
    "operating_profit": 6566976000000,
    "net_income": 15487096000000,
    "total_assets": 455905746000000,
    "total_liabilities": 92228696000000,
    "total_equity": 363677050000000,
    "debt_ratio": 25.4,
    "close": 56000,
    "market_cap": 334480000000000,
    "high_52w": 88800,
    "low_52w": 49900,
    "listed": true,
    "source": "dart_api"
  },
  "insight": "[유상증자 · 신뢰도 97%] 삼성전자 2023년\n..."
}
```

### POST /classify

공시 본문 텍스트만 분류합니다.

**Request**
```json
{ "text": "당사는 시설투자 목적으로 보통주 500만 주를 유상증자 결정하였습니다..." }
```

**Response**
```json
{
  "result": { "label": "유상증자", "score": 0.9542 },
  "text_length": 47
}
```

### GET /health

서비스 상태 확인

## 데이터 아키텍처

```
[/disclosures] 기업명 입력
    └─ dart_corps (Supabase) → corp_code 조회 (상장사 우선 4단계)
        └─ DART list.json → 정기공시 / 주요사항 / 외부감사 목록
            └─ report_nm 키워드 매핑 → label (감사보고서 / 사업보고서 / 유상증자 / 기타)

[/analyze] 기업명 + 연도 + 공시 본문 입력
    └─ BERT → 공시 분류
    └─ dart_rag_documents (Supabase) → 재무제표 캐시
        └─ 미스: DART fnlttSinglAcntAll → CFS/OFS fallback → 저장
    └─ FinanceDataReader (KRX) → 실시간 주가
```

## Supabase 테이블

| 테이블 | 역할 |
|---|---|
| `dart_corps` | DART 전체 기업코드 (약 10만 건) |
| `dart_rag_documents` | 재무제표 요약 캐시 + pgvector 임베딩 |

기업코드 초기 업로드:
```bash
python scripts/upload_corps.py
```

## 환경 변수

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-key
GEMINI_API_KEY=your-gemini-api-key
DART_API_KEY=your-dart-open-api-key
```

## 로컬 실행

```bash
pip install torch==2.4.1+cpu --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

uvicorn main:app --reload
```

> 모델 파일(`models/dart_classifier/`)이 준비되어 있어야 합니다.

## 배포 (GCP Cloud Run)

```bash
cd dart_classifier
gcloud run deploy jukang-dartclassifier --source . --region asia-northeast1
```

Secret Manager 등록 필요: `SUPABASE_URL`, `SUPABASE_KEY`, `GEMINI_API_KEY`, `DART_API_KEY`

## 기술 스택

| 구분 | 기술 |
|---|---|
| ML | klue/bert-base, Hugging Face Transformers 5.x |
| Embedding | Gemini text-embedding-004 (768차원) |
| 공시 데이터 | DART Open API (list.json, fnlttSinglAcntAll) |
| 주가 데이터 | FinanceDataReader (KRX) |
| Backend | FastAPI, Uvicorn |
| Database | Supabase (PostgreSQL + pgvector) |
| Infra | GCP Cloud Run, Docker |
