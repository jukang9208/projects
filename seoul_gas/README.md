# Seoul Gas RAG API

서울시 25개 자치구의 도시가스 수급 데이터를 기반으로 군집 분석, 시계열 트렌드, 자연어 질의응답(RAG)을 제공하는 FastAPI 서버입니다.

---

## 프로젝트 구조

```
seoul_gas_rag/
├── main.py                        # FastAPI 앱 진입점, 라우터 등록, CORS 설정
├── api/                           # API 라우터 모음
│   ├── gas_rag.py                 # POST /analysis/seoulgas/rag
│   ├── gas_cluster.py             # GET  /analysis/seoulgas/clusters/{year}
│   └── gas_corr.py                # 상관관계 분석 엔드포인트
├── services/                      # 비즈니스 로직
│   ├── analysis_service.py        # EnergyAnalysisService (KMeans, 실루엣, 엘보우, 트렌드)
│   ├── answer_service.py          # 질문 유형 분기 및 응답 조합
│   ├── question_service.py        # 자연어 파싱 (자치구, 연도, 지표, 클러스터 추출)
│   ├── db_service.py              # Supabase RAG 벡터 검색
│   ├── answer_utils.py            # Python 타입 변환 유틸
│   └── answer_handlers/           # 응답 유형별 핸들러
│       ├── seoul_handler.py       # 서울 전체 요약
│       ├── trend_handler.py       # 시계열 트렌드
│       ├── cluster_handler.py     # 군집 분석 및 군집 목록
│       └── comparison_handler.py  # 자치구 비교
├── core/config.py                 # 환경변수 로드, Supabase·Gemini 클라이언트 초기화
├── schemas/schemas.py             # Pydantic 요청/응답 스키마
├── etl/
│   ├── load_structured_data.py    # CSV → Supabase 정형 데이터 적재
│   └── load_rag_documents.py      # JSONL → Supabase 벡터 임베딩 업로드 (Gemini)
├── data/
│   ├── gas.csv                    # 도시가스 수급가구수 원본 (2019~2024)
│   ├── income.csv                 # 자치구별 평균 소득 원본
│   ├── population.csv             # 자치구별 인구·가구 원본
│   └── processed/
│       ├── seoulgas_chunks.json
│       └── seoulgas_chunks.jsonl  # RAG 임베딩 소스 (62개 청크)
└── requirements.txt
```

---

## 기술 스택

| 구분 | 기술 |
|---|---|
| 웹 프레임워크 | FastAPI + Uvicorn |
| DB | Supabase (PostgreSQL + pgvector) |
| 벡터 검색 | `match_documents` RPC (cosine similarity) |
| 임베딩 모델 | Google Gemini `models/gemini-embedding-001` (768차원) |
| LLM | Google Gemini (google-genai SDK) |
| 군집 분석 | scikit-learn KMeans + StandardScaler |
| 설정 관리 | python-dotenv + `.env` |

---

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/analysis/seoulgas/clusters/{year}` | 연도별 KMeans 군집 결과 (k=4 고정) |
| GET | `/analysis/seoulgas/correlation` | 피처 간 상관관계 행렬 |
| POST | `/analysis/seoulgas/rag` | 자연어 질문 → 분석 응답 |

RAG 요청 바디: `{ "question": "관악구의 가스 수급 현황은?" }`

응답 구조: `query_type`, `district`, `year`, `summary`, `sections`(kpi·trend·cluster·comparison·map·overview·rag·cluster_list), `sources`

---

## 질문 유형 분기

`answer_service.py`가 자연어 질문을 파싱하여 아래 유형으로 분기합니다.

| 유형 | 조건 | 처리 |
|---|---|---|
| `overview` | "서울" 포함 + 자치구 없음 | 서울 전체 요약 |
| `trend` | 자치구 1개 + 트렌드 키워드 | 시계열 분석 |
| `cluster` | 자치구 1개 | 군집 분석 |
| `compare` | 자치구 2개 이상 | 자치구 비교 |
| `cluster_list` | 클러스터 ID + 목록 키워드 | 군집 소속 목록 |
| `general` | 그 외 | Supabase RAG 벡터 검색 |

트렌드 키워드: 수급, 가스수급, 수급가구수, 소득, 인구, 가구, 변화, 추이, 현황

---

## 군집 분석 결과 요약 (K=4)

### 분석 개요

- **대상**: 서울특별시 25개 자치구
- **기간**: 2019년 ~ 2024년
- **분석 변수**: 도시가스 수급가구수, 총가구수, 평균 소득, 총인구
- **방법**: K-Means Clustering + 엘보우 분석 + 실루엣 점수 검토
- **데이터 범위**: 가정용 도시가스 공급에 한정 (상업·업무·산업용 제외)
- **핵심 발견**: 서울은 단일 주거 구조가 아니라 도시 규모·가구 구성·생활권 특성이 다른 **4개 유형**의 복합 주거 구조로 구분됨

### K=4 군집별 분류 결과

**Cluster 0 — 고소득 다인가구 주거지**
평균 소득과 가구당 인구수가 모두 높은 지역. 가족 단위 거주 비율이 높은 중대형 아파트 중심 생활 구조.
가스 수요는 안정적이나 지역난방·신축 공동주택·대체 난방 체계 혼재로 완전 포화 상태는 아님.
→ 정책 방향: 친환경 보일러·고효율 설비 전환 유도, 스마트 계량기(AMI) 도입 테스트베드로 활용, 통합 에너지 효율 컨설팅 추진

**Cluster 1 — 표준 중산층 균형형 주거지**
인구·소득·가구 구조 등 대부분 지표가 평균 수준. 가스 수급도 안정적으로 유지되는 서울의 표준 주거 구조.
도시가스 인프라가 충분히 구축된 상태로 예측 가능한 소비 패턴.
→ 정책 방향: 노후 배관·가스 안전 점검 정례화, 요금 분할 납부·절약형 캐시백 운영, 기존 공급 체계의 안정적 유지

**Cluster 2 — 소규모 1~2인 가구 고의존 지역**
인구·가구 규모가 비교적 작고 1~2인 가구 비중이 높음. 가구 대비 가스 수급 수준은 매우 높은 편.
소형 주거·개별 주택 단위 사용 비중이 높아 각 가구의 가스 의존도가 높고 사용 밀도가 높은 군집.
→ 정책 방향: 1~2인 가구 에너지 바우처·요금 지원 강화, 노후 개별 보일러 교체·단열 개선 지원, 청년·고령 독거가구 대상 맞춤형 에너지 복지 정책

**Cluster 3 — 대규모 고밀 1~2인 가구 혼합지역**
인구와 가구 수가 모두 높은 대규모 지역. 1~2인 가구 비중이 높은 고밀도 도시형 주거 구조.
오피스텔·원룸·상업시설 등 비가스 기반 주거가 혼재해 가구 수는 많지만 가구 대비 수급 수준은 상대적으로 낮음.
→ 정책 방향: 비가스 난방 가구 실태 조사 우선 실시, 공급 사각지대 식별·인프라 확충, 혼합용도 지역 맞춤형 공급 관리 정책

---

## RAG 문서 요약

### 문서 구성 (총 62개 청크)

| 섹션 | 청크 수 | 내용 |
|---|---|---|
| summary | 5 | 분석 개요, 목적, 데이터 범위, 군집 방법론 |
| features | 9 | 분석 변수별 설명 및 산출 방식 |
| cluster | 12 | K=4 군집별 설명·해석·정책 시사점 |
| correlation | 8 | 피처 간 관계 구조 및 수급 패턴 해석 |
| trend | 5 | 연도별 수급 변화 및 시계열 인사이트 |
| insight | 23 | 핵심 인사이트, 자치구 비교, 정책 시사점 |

### 상관관계 핵심 인사이트

도시가스 수급 구조는 인구 규모보다 **가구 구성(1~2인 vs 다인가구)과 주거 형태**에 더 직접적인 영향을 받습니다.

수급가구수는 총인구보다 총가구수와 더 밀접한 관계를 보이며, 인구가 많은 지역이라도 1~2인 가구 비중이 높거나 고밀 주거 형태가 많으면 인구 대비 수급 비율이 낮게 나타납니다.

평균 소득은 수급 구조에 직접 영향을 주기보다 주거 형태·가구 구성 변화를 통해 간접적으로 작용합니다.

고밀 지역에서는 비가스 사용 가구가 혼재할 가능성이 높아, 총 수급 규모는 크더라도 인구·가구 대비 수급 비율은 낮게 나타나는 구조적 왜곡이 발생합니다.

### 서울 가스 수급 구조 핵심 요약

서울의 가스 수급 구조는 **소득 수준 자체보다 가구 구성과 주거 형태의 차이**에 따라 구분되는 경향이 강합니다. 고소득 다인가구 주거지·표준 중산층 주거지·소규모 1~2인 가구 지역·대규모 고밀 혼합지역의 4가지 유형이 서울 내에 공존하며, 
각 유형별로 공급 전략과 정책 방향이 다르게 적용되어야 합니다.

---

## ETL 파이프라인

```bash
# 1. 정형 데이터 적재 (CSV → Supabase)
python etl/load_structured_data.py

# 2. RAG 문서 임베딩 업로드 (JSONL → Supabase pgvector)
python etl/load_rag_documents.py
```

RAG 임베딩 소스 파일: `data/processed/seoulgas_chunks.jsonl`
