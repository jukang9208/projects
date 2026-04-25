# DART 공시 분류기

DART(금융감독원 전자공시시스템) 공시 본문을 BERT 파인튜닝 모델로 3개 카테고리로 분류하는 FastAPI 서비스입니다.

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
│   ├── classify.py           # POST /classify 엔드포인트
│   └── rag.py                # POST /rag/* 엔드포인트
├── core/
│   └── config.py             # 환경변수 및 설정
├── schemas/
│   └── classify.py           # Pydantic 스키마 (분류 + RAG)
├── services/
│   ├── classifier.py         # BERT 추론 로직
│   ├── embedder.py           # Gemini 임베딩
│   └── rag.py                # Supabase 벡터 검색
├── scripts/
│   └── ingest_corpus.py      # 학습 데이터 Supabase 업로드
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

### POST /classify

공시 본문 텍스트를 입력하면 카테고리와 신뢰도를 반환합니다.

**Request**
```json
{
  "text": "당사는 시설투자 목적으로 보통주 500만 주를 유상증자 결정하였습니다..."
}
```

**Response**
```json
{
  "result": {
    "label": "유상증자",
    "score": 0.9542
  },
  "text_length": 47
}
```

### GET /health

서비스 상태 확인

## 환경 변수

`.env.example`을 참고하여 `.env` 파일을 생성합니다.

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

Secret Manager에 환경변수 등록 필요: `SUPABASE_URL`, `SUPABASE_KEY`, `GEMINI_API_KEY`

## 기술 스택

| 구분 | 기술 |
|---|---|
| ML | klue/bert-base, Hugging Face Transformers 5.x |
| Embedding | Gemini text-embedding-004 (768차원) |
| Backend | FastAPI, Uvicorn |
| Database | Supabase (PostgreSQL + pgvector) |
| Infra | GCP Cloud Run, Docker |
