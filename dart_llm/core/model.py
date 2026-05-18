import os
import torch
from dotenv import load_dotenv
from transformers import AutoTokenizer, AutoModelForCausalLM


load_dotenv()
_model = None
_tokenizer = None

MODEL_PATH = os.getenv("LLM_MODEL_PATH", "")
SYSTEM = os.getenv("LLM_SYSTEM", "당신은 DART 금융 공시 문서를 분석하는 전문 AI입니다.")


def get_llm():
    global _model, _tokenizer
    if _model is None:
        if not MODEL_PATH:
            raise RuntimeError("LLM_MODEL_PATH 환경변수를 설정하세요.")
        print(f"모델 로딩: {MODEL_PATH}")
        _tokenizer = AutoTokenizer.from_pretrained(
            MODEL_PATH, trust_remote_code=True
        )
        _model = AutoModelForCausalLM.from_pretrained(
            MODEL_PATH,
            torch_dtype=torch.bfloat16,
            device_map='auto',
            trust_remote_code=True,
        )
        _model.eval()
        print("모델 로딩 완료")
    return _model, _tokenizer