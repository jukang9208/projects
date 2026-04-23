# 서울시 자치구별 에너지 소비 패턴 분석 및 RAG 질의응답 시스템

서울특별시 25개 자치구의 전력·가스 소비 데이터를 기반으로  
K-means 군집 분석과 RAG(Retrieval-Augmented Generation) 기반 자연어 질의응답 시스템을 구현한 프로젝트입니다.

---

## 프로젝트 개요

| 항목 | 내용 |
|---|---|
| 분석 대상 | 서울특별시 25개 자치구 |
| 분석 기간 | 2019 ~ 2024년 (6개년) |
| 관측치 | 25개 자치구 × 6개년 = 150개 |
| 군집 수 | K=6 (Silhouette·ARI 기반 검증) |
| 임베딩 모델 | Google Gemini `gemini-embedding-001` (768차원) |
| 배포 | Google Cloud Run |

---

## 시스템 아키텍처

```
서울 열린데이터광장 API
        ↓
   ETL (load_structured_data.py)
        ↓
Supabase PostgreSQL          PDF 보고서
(seoul_district_energy_stats) ↓
        ↓            load_pdf_documents.py (Vision OCR)
   FastAPI Backend           ↓
   ├── /analysis/*    Supabase pgvector
   ├── /energy/*      (energy_rag_documents)
   └── /rag           ↓
        ↓         RAG 검색 (cosine similarity)
   React + Leaflet.js
   (자치구 군집 지도 시각화)
```

---

## 기술 스택

| 구분 | 기술 |
|---|---|
| 백엔드 | FastAPI, Uvicorn |
| 데이터베이스 | Supabase (PostgreSQL + pgvector) |
| 벡터 검색 | pgvector cosine similarity + match_threshold 필터 |
| 임베딩·OCR | Google Gemini API (gemini-2.5-flash Vision, gemini-embedding-001) |
| 군집 분석 | scikit-learn KMeans + StandardScaler |
| 프론트엔드 | React, Leaflet.js |
| 배포 | Google Cloud Run, Docker |
| 검증 | Jupyter Notebook (val_01 ~ val_04, validation_rag) |

---

## API 엔드포인트

### 에너지 데이터
| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/energy` | 전체 자치구 에너지 데이터 |
| GET | `/energy/year/{year}` | 연도별 데이터 |
| GET | `/energy/district/{district}` | 자치구별 데이터 |

### 군집 분석
| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/analysis/kmeans?k=6` | K-means 군집 결과 |
| GET | `/analysis/elbow` | 엘보우 분석 |
| GET | `/analysis/silhouette` | 실루엣 점수 |
| GET | `/analysis/correlation` | 피처 상관관계 행렬 |
| GET | `/analysis/optimal-k` | 최적 K 추천 |

### RAG 질의응답
| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/rag` | 자연어 질문 → 분석 기반 답변 |

```json
// 요청
{ "question": "강남구 에너지 소비 특성과 정책 방향은?" }

// 응답
{
  "query_type": "cluster",
  "district": "강남구",
  "summary": "강남구는 서비스업·산업용 전력 비율이 합계 85% 이상으로...",
  "sources": [...]
}
```

---

## 군집 분석 결과 (K=6)

| 군집 | 특성 | 대표 자치구 |
|---|---|---|
| C0 | 주거 중심·가스 의존형 | 노원구, 도봉구, 강북구 |
| C1 | 균형형 중산층 주거지 | 은평구, 중랑구, 성동구 |
| C2 | 상업·활동 중심형 | 강남구, 서초구 |
| C3 | 고밀 혼합 주거형 | 관악구, 동작구 |
| C4 | 도심 역사·업무형 | 종로구, 중구, 용산구 |
| C5 | 외곽 저밀 주거형 | 강서구, 구로구, 금천구 |

### K=6 선택 근거
- 수치상 최고점은 K=9(Silhouette 0.4202)이나, 피처 자기상관 0.9972의 패널 데이터 구조에서 K 상승 시 실루엣 인위적 과적합 발생
- K=6(Silhouette 0.3492)은 Bootstrap ARI 안정성 검증과 도시 맥락에서의 해석 가능성을 종합 고려한 최종 선택
- 엘보우 분석: K=5→6 구간(Inertia 54.7 감소)부터 감소폭 완만해지며 균형점 확인
- 상세 근거: [`docs/k6_decision_rationale.md`](docs/k6_decision_rationale.md)

---

## 검증 파이프라인

```
val_01_data.ipynb       데이터 정합성 검증 (CSV ↔ DB 일치 확인)
val_02_kmeans.ipynb     K-means 군집 레이블 재현성 검증
val_03_stability.ipynb  Bootstrap ARI 군집 안정성 검증
val_04_timeline.ipynb   연도별 군집 이동 추적
validation_rag.ipynb    RAG 검색 품질 평가 (유사도 분포, match_count 민감도)
```

---

## RAG 파이프라인

```
PDF 문서 (분석 보고서 + 서울시 에너지 기본계획)
    ↓
Gemini Vision OCR (페이지 → 텍스트 추출)
    ↓
텍스트 청킹 (CHUNK_SIZE=1200, OVERLAP=200)
    ↓
Gemini Embedding (768차원, task_type=retrieval_document)
    ↓
Supabase pgvector HNSW 인덱스
    ↓
쿼리 임베딩 (task_type=retrieval_query)
    ↓
cosine similarity 검색 (match_threshold=0.70)
    ↓
LLM 답변 생성 (Gemini)
```

---

## 실행 방법

### 환경 설정
```bash
cp .env.example .env
# .env에 실제 키 입력
pip install -r requirements.txt
```

### 정형 데이터 적재
```bash
python etl/load_structured_data.py
```

### RAG 문서 적재
```bash
# 기본 실행 (현재 디렉터리의 모든 PDF 자동 감지)
python etl/load_pdf_documents.py

# 특정 PDF + 페이지 범위 지정
python etl/load_pdf_documents.py --pdf "문서명.pdf" --pages 130-200
```

### 서버 실행
```bash
uvicorn main:app --reload
```

### Docker
```bash
docker build -t seoul-energy-api .
docker run -p 8080:8080 --env-file .env seoul-energy-api
```

---

## 프로젝트 구조

```
seoul_energy_rag/
├── main.py                    # FastAPI 앱 진입점
├── app/                       # API 라우터
│   ├── analysis_router.py     # 군집·상관관계·엘보우 분석
│   ├── energy_router.py       # 에너지 데이터 조회
│   └── energyrag_router.py    # RAG 질의응답
├── services/                  # 비즈니스 로직
│   ├── analysis_service.py    # KMeans, 실루엣, 엘보우
│   ├── db_service.py          # Supabase RAG 벡터 검색
│   ├── answer_service.py      # 질문 유형 분기
│   ├── question_service.py    # 자연어 파싱
│   └── answer_handlers/       # 유형별 응답 핸들러
├── etl/
│   ├── load_structured_data.py
│   └── load_pdf_documents.py  # PDF OCR → pgvector 자동 적재
├── db/sql/
│   └── rag.sql                # pgvector 테이블·RPC 함수 정의
├── docs/
│   ├── k6_decision_rationale.md   # K=6 선택 근거 문서
│   └── k9_validation_issues.md    # K=9 검증 실패 기록
├── notebooks/                 # 검증 노트북
│   ├── val_01_data.ipynb      # 데이터 정합성 검증
│   ├── val_02_kmeans.ipynb    # 군집 레이블 재현성 검증
│   ├── val_03_stability.ipynb # Bootstrap ARI 안정성 검증
│   ├── val_04_timeline.ipynb  # 연도별 군집 이동 추적
│   └── validation_rag.ipynb   # RAG 검색 품질 평가
└── .env.example               # 환경변수 템플릿
```

---

## 데이터 출처

- [서울 열린데이터광장 - 자치구별 전기 사용량](https://data.seoul.go.kr)
- [서울 열린데이터광장 - 자치구별 도시가스 사용량](https://data.seoul.go.kr)
- [제5차 서울특별시 지역에너지계획 (서울시 공식 발간)](https://news.seoul.go.kr/env/archives/507994)
