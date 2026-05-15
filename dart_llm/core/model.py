import os
from llama_cpp import Llama

_llm: Llama | None = None


def get_llm() -> Llama:
    global _llm
    if _llm is None:
        model_path = os.getenv("GGUF_MODEL_PATH", "")
        if not model_path:
            raise RuntimeError("GGUF_MODEL_PATH 환경변수를 설정하세요.")
        print(f"모델 로딩: {model_path}")
        _llm = Llama(
            model_path=model_path,
            n_ctx=4096,
            n_threads=os.cpu_count() or 4,
            verbose=False,
        )
        print("모델 로딩 완료")
    return _llm
