import os
import sys
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.config import settings


def convert_to_gguf(merged_dir: Path, output_dir: Path, quantization: str = "q4_k_m"):
    
    output_dir.mkdir(parents=True, exist_ok=True)
    gguf_fp16 = output_dir / "model-f16.gguf"
    gguf_quant = output_dir / f"model-{quantization}.gguf"

    # llama.cpp 위치 
    llama_cpp_path = PROJECT_ROOT / "llama.cpp"
    convert_script = llama_cpp_path / "convert_hf_to_gguf.py"

    if not convert_script.exists():
        print("llama.cpp 없음. 설치 방법:")
        print("  git clone https://github.com/ggerganov/llama.cpp")
        print("  cd llama.cpp && pip install -r requirements.txt")
        sys.exit(1)

    # HF → GGUF (f16)
    print(f"[1/2] GGUF 변환 (f16): {merged_dir} → {gguf_fp16}")
    subprocess.run([
        sys.executable, str(convert_script),
        str(merged_dir),
        "--outfile", str(gguf_fp16),
        "--outtype", "f16",
    ], check=True)

    # f16 → quantized
    print(f"[2/2] 양자화 ({quantization}): {gguf_fp16} → {gguf_quant}")
    quantize_bin = llama_cpp_path / "llama-quantize"
    if not quantize_bin.exists():
        quantize_bin = llama_cpp_path / "build" / "bin" / "llama-quantize"
    subprocess.run([
        str(quantize_bin),
        str(gguf_fp16),
        str(gguf_quant),
        quantization.upper().replace("-", "_"),
    ], check=True)

    print(f"\nGGUF 완료: {gguf_quant}")
    return gguf_quant


def upload_to_hf(gguf_path: Path):
    
    from huggingface_hub import HfApi
    api = HfApi(token=settings.HF_TOKEN)

    repo_id = settings.HF_REPO_ID
    if not repo_id:
        print("HF_REPO_ID 설정 필요 (.env)")
        return

    print(f"\nHuggingFace 업로드: {repo_id}")
    api.upload_file(
        path_or_fileobj=str(gguf_path),
        path_in_repo=gguf_path.name,
        repo_id=repo_id,
        repo_type="model",
    )
    print(f"완료: https://huggingface.co/{repo_id}")


def main():
    merged_dir = PROJECT_ROOT / settings.MERGED_OUTPUT_DIR
    output_dir = PROJECT_ROOT / "outputs" / "gguf"

    if not merged_dir.exists():
        print(f"병합된 모델 없음: {merged_dir}")
        print("노트북에서 파인튜닝 + 병합 먼저 실행하세요.")
        sys.exit(1)

    gguf_path = convert_to_gguf(merged_dir, output_dir)
    upload_to_hf(gguf_path)


if __name__ == "__main__":
    main()
