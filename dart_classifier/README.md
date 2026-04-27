# DART 공시 분류기 v3

DART(금융감독원 전자공시시스템) 공시를 자동 조회·분류하고, 뉴스 감성분석과 재무제표·실시간 주가 데이터를 통합 제공하는 FastAPI 서비스입니다.

## 버전 히스토리

| 버전 | 핵심 기능 | 한계 및 개선 계기 |
|---|---|---|
| v1 | klue/bert-base 파인튜닝, 공시 본문 3분류 (`/classify`) | 분류 레이블만 나와 "왜?"에 대한 답이 없음 |
| v2 | DART 재무제표 + 실시간 주가 통합 (`/analyze`) | 공시 본문을 사용자가 직접 복붙해야 하는 UX 문제 |
| v2.5 | DART 공시 자동 조회 + 보고서명 키워드 분류 (`/disclosures`) | 공시 정보만으로는 현재 시장 반응을 알 수 없음 |
| v3 | 뉴스 감성분석(KR-FinBERT) 추가, 기업 종합 조회 (`/company`) | - |

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
├── 03_sentiment_test.ipynb   # KR-FinBERT 감성분석 검증 (v3)
├── main.py                   # FastAPI 앱 엔트리포인트
├── app/
│   ├── classify.py           # POST /classify
│   ├── rag.py                # POST /rag/*
│   ├── analyze.py            # POST /analyze (v2)
│   ├── disclosures.py        # GET  /disclosures (v2.5)
│   └── company.py            # GET  /company (v3)
├── core/
│   └── config.py             # 환경변수 및 설정
├── schemas/
│   └── classify.py           # Pydantic 스키마 전체
├── services/
│   ├── classifier.py         # BERT 추론 (공시 분류)
│   ├── embedder.py           # Gemini 임베딩
│   ├── rag.py                # Supabase 벡터 검색
│   ├── financial.py          # DART 재무제표 수집 및 캐시
│   ├── market.py             # 실시간 주가 조회
│   ├── disclosure.py         # 공시 자동 조회 + 분류
│   ├── news.py               # 네이버 뉴스 API 조회 (v3)
│   └── sentiment.py          # KR-FinBERT 감성분석 (v3)
├── scripts/
│   └── upload_corps.py       # DART 기업코드 DB 업로드
├── db/
│   └── init_v2.sql           # dart_corps 테이블 생성 SQL
├── models/                   # ⚠️ 미포함 (아래 참고)
├── Dockerfile
└── requirements.txt
```

## 코드 구조 설명

### 기업코드 조회 — `services/financial.py` `lookup_corp_code()`

기업명으로 DART corp_code를 찾는 4단계 fallback 구조입니다.

```
정확한 이름 + 상장사 우선
    → 정확한 이름 (비상장 포함)
        → 부분 일치 + 상장사 우선
            → 부분 일치 (비상장 포함)
```

"카카오"처럼 동명 법인이 여럿 존재할 때 상장사를 우선 선택하기 위한 설계입니다. `stock_code IS NOT NULL` 조건이 상장사 필터 역할을 합니다.

### 재무제표 수집 — `services/financial.py` `fetch_financial_from_dart()`

DART `fnlttSinglAcntAll` API는 `reprt_code`(보고서 종류)와 `fs_div`(재무제표 종류) 조합에 따라 데이터 존재 여부가 회사마다 다릅니다. 8개 조합을 순서대로 시도하다 성공하면 중단합니다.

```
reprt_code: 사업보고서(11011) → 반기(11012) → 1분기(11013) → 3분기(11014)
fs_div:     CFS(연결재무제표) → OFS(별도재무제표)
```

8개 전부 실패하면 `None` 반환 — 비상장사나 미공시 기업을 500 에러 없이 처리합니다.

### 재무제표 캐시 — `services/financial.py` `get_financial()`

DART API 호출 비용을 줄이기 위해 Supabase에 캐시합니다. 재무제표는 연 1회 확정되므로 만료 없이 저장합니다. 주가는 매일 변동하므로 캐시 없이 항상 실시간 조회합니다.

```
요청
 └─ Supabase 캐시 확인
     ├─ 히트: 캐시 반환
     └─ 미스: DART API 수집 → Supabase 저장 → 반환
 └─ FinanceDataReader (KRX) → 실시간 주가 병합
```

### 공시 자동 조회 — `services/disclosure.py`

DART `list.json` API를 정기공시(A), 주요사항보고서(B), 외부감사(F) 세 유형으로 각각 호출해 합칩니다. 보고서명 키워드 사전(`REPORT_NM_MAP`)으로 분류 레이블을 매핑합니다.

처음에는 `document.xml`로 공시 본문까지 가져와 BERT로 분류하려 했으나, 일반 API 키는 status 101 오류로 본문 다운로드가 차단됩니다. 보고서명 자체가 명확한 경우("사업보고서", "유상증자" 등)가 많아 키워드 매핑이 실용적으로 충분합니다.

### 뉴스 감성분석 — `services/news.py` + `services/sentiment.py`

네이버 뉴스 검색 API로 기업명 관련 최신 뉴스를 수집하고, `snunlp/KR-FinBert-SC`로 기사별 감성(긍정/부정/중립)을 분류합니다.

DART 분류기(klue/bert-base)는 직접 파인튜닝한 모델이지만, 감성분석은 한국어 금융 텍스트로 사전학습된 KR-FinBERT를 그대로 사용합니다. 두 모델 모두 lazy load로 최초 요청 시 메모리에 올라갑니다.

API 키 미설정 또는 뉴스 조회 실패 시 감성 결과를 빈값으로 채워 전체 응답이 중단되지 않습니다.

## API

### GET /company (v3 핵심)

기업명 하나로 공시 목록, 뉴스 감성, 재무제표를 통합 조회합니다. 재무제표 연도는 전년도로 자동 설정됩니다.

**Request**
```
GET /company?corp_name=삼성전자
```

**Response**
```json
{
  "corp_name": "삼성전자",
  "corp_code": "00126380",
  "stock_code": "005930",
  "disclosures": [
    {
      "rcept_no": "20260310002820",
      "rept_nm": "사업보고서 (2025.12)",
      "rcept_dt": "20260310",
      "flr_nm": "삼성전자",
      "label": "사업보고서",
      "score": null,
      "text_preview": null
    }
  ],
  "news_sentiment": {
    "label": "긍정",
    "positive_ratio": 0.6,
    "negative_ratio": 0.2,
    "neutral_ratio": 0.2,
    "articles": [
      {
        "title": "삼성전자, 반도체 부문 실적 회복세",
        "link": "https://...",
        "pub_date": "Sat, 26 Apr 2026 09:00:00 +0900",
        "sentiment": "긍정",
        "score": 0.912
      }
    ]
  },
  "financial": {
    "corp_name": "삼성전자",
    "stock_code": "005930",
    "year": 2025,
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
    "source": "cache"
  }
}
```

### GET /disclosures (v2.5)

기업명으로 최근 1년간 공시 목록을 조회하고 보고서명 키워드로 분류합니다.

**Request**
```
GET /disclosures?corp_name=삼성전자&count=5
```

### POST /analyze (v2)

공시 본문 텍스트를 BERT로 분류하고 재무·주가 데이터와 통합 분석합니다.

**Request**
```json
{
  "text": "당사는 시설투자 목적으로 보통주 500만 주를 유상증자 결정하였습니다...",
  "corp_name": "삼성전자",
  "year": 2023
}
```

### POST /classify (v1)

공시 본문 텍스트만 BERT로 분류합니다.

**Request**
```json
{ "text": "당사는 시설투자 목적으로 보통주 500만 주를 유상증자 결정하였습니다..." }
```

### GET /health

서비스 상태 확인

## 데이터 아키텍처

```
[/company] 기업명 입력
    ├─ dart_corps (Supabase) → corp_code 조회 (상장사 우선 4단계)
    │       └─ DART list.json → 정기공시 / 주요사항 / 외부감사 목록
    │               └─ report_nm 키워드 매핑 → label
    │
    ├─ 네이버 뉴스 API → 최신 뉴스 수집
    │       └─ KR-FinBERT → 기사별 긍정 / 부정 / 중립 분류
    │
    └─ dart_rag_documents (Supabase) → 재무제표 캐시
            └─ 미스: DART fnlttSinglAcntAll (reprt_code × fs_div 8개 조합 fallback)
            └─ FinanceDataReader (KRX) → 실시간 주가 (항상 실시간)

[/analyze] 기업명 + 연도 + 공시 본문 입력
    └─ klue/bert-base (파인튜닝) → 공시 분류
    └─ 위와 동일한 재무·주가 조회 흐름
```

## 모델

### DART 공시 분류기 (직접 파인튜닝)

- **베이스**: `klue/bert-base`
- **태스크**: Sequence Classification (3-class)
- **학습 데이터**: DART 공시 본문 979건 (2022~2024)
- **입력**: 공시 본문 텍스트 (최대 512 토큰)
- **출력**: 감사보고서 / 사업보고서 / 유상증자 + 신뢰도

### 뉴스 감성분석 (사전학습 모델 사용)

- **모델**: `snunlp/KR-FinBert-SC`
- **특징**: 한국어 금융 뉴스 도메인 특화 BERT, 별도 파인튜닝 없이 사용
- **입력**: 뉴스 제목 + 설명 (최대 512 토큰)
- **출력**: positive / negative / neutral + 신뢰도

## 학습 데이터

- **수집 기간**: 2022년 ~ 2024년
- **수집 건수**: 1,080건 → 전처리 후 979건
- **카테고리별**: 감사보고서 360건 / 사업보고서 319건 / 유상증자 300건
- **출처**: DART Open API (`document.xml`)

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

KR-FinBERT(`snunlp/KR-FinBert-SC`)는 최초 요청 시 HuggingFace에서 자동 다운로드됩니다.

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

# 뉴스 감성분석용 (미설정 시 뉴스 조회 스킵)
NAVER_CLIENT_ID=your-naver-client-id
NAVER_CLIENT_SECRET=your-naver-client-secret
```

## 로컬 실행

```bash
pip install torch==2.4.1+cpu --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

uvicorn main:app --reload
```

> DART 분류기 모델 파일(`models/dart_classifier/`)이 준비되어 있어야 합니다.

## 배포 (GCP Cloud Run)

```bash
cd dart_classifier
gcloud run deploy jukang-dartclassifier --source . --region asia-northeast1
```

Secret Manager 등록 필요: `SUPABASE_URL`, `SUPABASE_KEY`, `GEMINI_API_KEY`, `DART_API_KEY`, `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`

## 기술 스택

| 구분 | 기술 |
|---|---|
| ML (공시 분류) | klue/bert-base 파인튜닝, Hugging Face Transformers 5.x |
| ML (감성분석) | snunlp/KR-FinBert-SC (사전학습 모델) |
| Embedding | Gemini text-embedding-001 (768차원) |
| 공시 데이터 | DART Open API (list.json, fnlttSinglAcntAll) |
| 뉴스 데이터 | 네이버 검색 API (news) |
| 주가 데이터 | FinanceDataReader (KRX) |
| Backend | FastAPI, Uvicorn |
| Database | Supabase (PostgreSQL + pgvector) |
| Infra | GCP Cloud Run, Docker |
