# DART Quant — AI 기업 펀더멘털 분석

투자자가 한 기업을 분석하려면 공시(DART)·재무·주가·뉴스를 사이트마다 따로 찾아봐야 한다. **기업명만 입력하면 흩어진 데이터를 한 번에 모아, 퀀트 점수와 LLM 분석으로 한 화면에서 보여주는** 기업 분석 서비스다.

기업명 하나 → 최근 공시(자동 분류) + 뉴스 + 재무·주가 + 거시지표를 수집하고, 하이브리드 RAG로 LLM이 종합 투자 의견을 생성한다. 두 기업 비교도 지원한다.

**Live Demo →** [jukang.tech](https://jukang.tech)

---

## 핵심 기능

- **멀티소스 데이터 통합** — DART 공시, FinanceDataReader 주가/재무, 네이버 뉴스, 거시지표(환율·금리 등)를 한 번에 수집
- **퀀트 스코어** — PER/PBR(가치)·ROE(수익성)·성장률·안정성·리스크를 규칙 기반으로 점수화
- **하이브리드 RAG + LLM** — 공시·뉴스를 Chroma(벡터) + BM25(키워드) 앙상블 검색으로 근거 추출 → Gemini가 투자 의견 생성
- **두 기업 비교 분석** — 단일 분석 결과를 재사용해 A/B 기업 비교
- **분석 신뢰도 평가** — 데이터 결측·품질을 검증해 confidence score 제공

---

## 기술적 포인트

### 1. 장중/장외 동적 캐싱 (Firebase Firestore · NoSQL)
- 주가는 장중에 계속 변하므로, **장중에는 3분 TTL**, 장외·휴일에는 마지막 캐시를 fallback으로 사용
- 한국 주식시장 개장 판단에 **주말 + 법정 공휴일(holidays) + 특수 휴장일(근로자의날·연말폐장)** 까지 반영
- 같은 API 호출 비용·지연·rate limit 문제를 캐싱으로 해결

### 2. 투트랙 저장 (서빙 + 시계열)
- `stock_analysis_latest` — 서빙용 최신 결과 (전체 데이터)
- `stock_analysis_history` — 시계열 분석용 (핵심 지표만 평탄화 저장) → 향후 추세 분석 대비

### 3. 동시성 제어
- 종목·관점별 독립 락 + **Double-checked locking** 으로 같은 분석이 동시 요청돼도 중복 수행 방지

### 4. 하이브리드 검색 RAG
- 공시·뉴스를 `RecursiveCharacterTextSplitter`로 청킹 (chunk 800 / overlap 100)
- **Chroma(의미 기반 벡터 검색) + BM25(키워드 검색)** 를 EnsembleRetriever로 결합 → 단일 검색보다 정확한 근거 추출

---

## 아키텍처

```
기업명 입력
   │
   ▼
ticker_service        기업명 → 종목코드
   │
   ├─ dart_service        DART 공시 수집
   ├─ news_service        네이버 뉴스 수집
   ├─ price_service       주가 · 재무 (FinanceDataReader)
   └─ macro_service       거시지표 (환율·금리 등)
   │
   ▼
validator_service     데이터 검증 + confidence score + LLM 컨텍스트 구성
   │
   ├─ scoring_service    퀀트 스코어 (PER·PBR·ROE·성장·안정·리스크)
   └─ report_service     하이브리드 RAG (Chroma+BM25) → Gemini 리포트
   │
   ▼
Firestore 캐싱 (latest 서빙 + history 시계열)
   │
   ▼
FastAPI → static 프론트
```

---

## 기술 스택

| 역할 | 기술 |
|---|---|
| API 서버 | FastAPI · Uvicorn · Gunicorn |
| 데이터 수집 | OpenDartReader · FinanceDataReader · yfinance · 네이버 검색 API |
| LLM · RAG | LangChain · Gemini (ChatGoogleGenerativeAI · Embeddings) · Chroma · BM25 |
| 캐싱 · DB | Firebase Firestore (NoSQL) |
| 배포 | GCP Cloud Run · Docker |

---

## 프로젝트 구조

```
dart_quant/
├── main.py                  # FastAPI 앱 · 단일 분석 엔드포인트
├── api/
│   └── compare.py           # 비교 분석 라우터
├── core/
│   └── config.py            # 환경변수 · DART 클라이언트
├── models/
│   └── schemas.py           # 요청 스키마
├── services/
│   ├── ticker_service.py        # 기업명 → 종목코드
│   ├── dart_service.py          # DART 공시 수집
│   ├── news_service.py          # 네이버 뉴스 수집
│   ├── price_service.py         # 주가 · 재무 지표
│   ├── macro_indicator_service.py  # 거시지표
│   ├── validator_service.py     # 데이터 검증 · 신뢰도 · 컨텍스트
│   ├── scoring_service.py       # 퀀트 스코어 계산
│   ├── report_service.py        # 하이브리드 RAG + LLM 리포트
│   └── analyzer.py              # 분석 파이프라인 · 캐싱 · 동시성 제어
├── static/                  # 프론트 (index.html · app.js · style.css)
├── Dockerfile
└── requirements.txt
```

---

## 실행

### 1. 환경 변수
`.env.example`을 복사해 `.env` 작성 (DART · Google · Naver API 키).
Firebase 서비스 계정 키는 `serviceAccountKey.json`으로 배치.

```bash
cp .env.example .env
```

### 2. 설치 · 실행
```bash
pip install -r requirements.txt
uvicorn main:app --reload
# http://localhost:8000
```

### 3. API
```bash
POST /api/analyze        # 단일 기업 분석
POST /api/compare        # 두 기업 비교
```

---

## 데이터 출처
- **DART** 전자공시 (금융감독원 Open API)
- **FinanceDataReader / yfinance** 주가 · 재무
- **네이버 검색 API** 뉴스
