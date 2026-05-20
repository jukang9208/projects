# DART LLM

DART 금융공시 데이터에 특화된 LLM을 직접 파인튜닝하여 GCP Cloud Run에서 서빙하는 End-to-End 파이프라인.

## 개요

DART API로 공시 문서를 수집하고, Gemini로 Q&A 데이터를 합성한 뒤 EXAONE-3.5-2.4B-Instruct 모델을 QLoRA로 파인튜닝한다. 학습된 모델을 GCS에 업로드하고 GCP Cloud Run에서 FastAPI로 서빙한다.

```
DART API 수집 (collect_dart.py)
      ↓
Gemini Q&A 합성 (build_dataset.py)  ← Alpaca 포맷 JSONL
      ↓
EXAONE QLoRA 파인튜닝 (notebooks/finetune.ipynb)  ← GPU 필요
      ↓
LoRA merge → outputs/merged/ (HuggingFace safetensors)
      ↓
GCS 업로드 (gsutil)
      ↓
transformers + FastAPI 서빙 (main.py)  ← GCP Cloud Run (CPU)
```

## 베이스 모델

**[LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct](https://huggingface.co/LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct)**

- 한국어 특화 모델 (DART 공시는 전부 한국어)
- RTX 4070 Ti (12GB)에서 QLoRA 학습 가능한 최적 크기
- Instruct 버전이라 적은 파인튜닝 데이터로도 Q&A 형식에 잘 적응

## 학습 데이터

| 항목 | 내용 |
|------|------|
| 원천 데이터 | DART API 공시 문서 7,200건 |
| 합성 데이터 | Gemini Q&A 12,996건 |
| 공시 유형 | 사업보고서, 감사보고서, 유상증자, 합병·분할, 자기주식, 전환사채 |
| 포맷 | Alpaca (instruction / input / output) |

## 파인튜닝 설정

```python
MODEL_ID     = 'LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct'
LORA_R       = 16
LORA_ALPHA   = 32
BATCH_SIZE   = 4
GRAD_ACCUM   = 4       
MAX_SEQ_LEN  = 512
EPOCHS       = 3
LR           = 2e-4
```

target_modules: `q_proj, k_proj, v_proj, o_proj` (Attention) + `gate_proj, up_proj, down_proj` (FFN)

## 프로젝트 구조

```
dart_llm/
├── main.py                      # FastAPI 앱, lifespan, 라우터 연결
├── app/
│   └── router.py                # /health, /ask 엔드포인트
├── schemas/
│   └── ask.py                   # AskRequest, AskResponse
├── core/
│   ├── config.py                # 환경변수
│   └── model.py                 # transformers 모델 로딩 (get_llm)
├── scripts/
│   ├── collect_dart.py       # DART API 공시 수집
│   ├── build_dataset.py      # Gemini Q&A 합성
│   └── download_model.py        # GCS에서 모델 다운로드 (Cloud Run 시작 시)
├── notebooks/
│   └── 04_finetune.ipynb        # QLoRA 파인튜닝
├── Dockerfile
├── requirements.txt
├── data/                        # .gitignore
└── outputs/                     # .gitignore (파인튜닝 결과)
```

## 실행 방법

### 1. 환경 설정

```bash
cp .env.example .env
# .env에서 DART_API_KEY, GEMINI_API_KEY 입력
# 로컬 실행 시 LLM_MODEL_PATH=outputs/merged 추가
```

### 2. 데이터 수집 및 Q&A 합성

```bash
pip install -r requirements.txt

# 공시 수집
python scripts/01_collect_dart.py --all --count 100

# Q&A 합성
python scripts/02_build_dataset.py --source raw --max_docs 7200
```

### 3. 파인튜닝 (GPU 환경)

`notebooks/04_finetune.ipynb` 실행 → `outputs/merged/`에 병합 모델 저장

### 4. GCS 업로드

```bash
gsutil -m cp -r outputs/merged gs://jukang-dartllm/model/merged/
```

### 5. 로컬 서버 실행

```bash
uvicorn main:app --reload
```

### 6. GCP Cloud Run 배포

```powershell
gcloud run deploy jukang-dartllm --source . --region asia-northeast1 `
  --memory 16Gi --cpu 4 --timeout 3600 --cpu-boost `
  --no-allow-unauthenticated `
  --set-env-vars "GCS_BUCKET=jukang-dartllm" `
  --set-env-vars "GCS_MODEL_PREFIX=model/merged/merged" `
  --set-env-vars "LLM_MODEL_PATH=/app/model/merged"
```

> Cloud Run 컨테이너 시작 시 `download_model.py`가 GCS에서 모델을 자동 다운로드한다.  
> `GCS_BUCKET`이 설정되지 않은 경우(로컬) 다운로드를 건너뛴다.

## API

### Health Check

```bash
GET /health
→ {"status": "ok"}
```

### 공시 질의

```bash
POST /ask
Content-Type: application/json

{
  "question": "이 사업보고서에서 주요 리스크 요인은 무엇인가?",
  "context": "공시 본문 텍스트...",
  "max_tokens": 512,
  "temperature": 0.3
}
```

```json
{
  "answer": "제시된 공시 본문의 'II. 사업의 내용'에 따르면...",
  "question": "이 사업보고서에서 주요 리스크 요인은 무엇인가?"
}
```

## 환경변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `DART_API_KEY` | DART Open API 키 | 필수 |
| `GEMINI_API_KEY` | Google Gemini API 키 | 필수 (데이터 합성 시) |
| `LLM_MODEL_PATH` | 모델 경로 | 필수 |
| `GCS_BUCKET` | GCS 버킷명 | 미설정 시 로컬 모드 |
| `GCS_MODEL_PREFIX` | GCS 모델 경로 prefix | `model/merged/merged` |
