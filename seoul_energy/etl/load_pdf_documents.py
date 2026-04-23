
import os
import re
import time
import fitz
import base64
from pathlib import Path
from PIL import Image
from io import BytesIO
from google import genai
from google.genai import types
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("supabase_URL")
SUPABASE_KEY = os.getenv("supabase_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
client = genai.Client(api_key=GOOGLE_API_KEY)

VISION_MODEL   = "gemini-2.5-flash"
EMBEDDING_MODEL = "models/gemini-embedding-001"
CHUNK_SIZE     = 1200
CHUNK_OVERLAP  = 200
DPI            = 150

def pdf_path_to_doc_id(pdf_path: str) -> str:

    stem = Path(pdf_path).stem          
    doc_id = re.sub(r"[\s\-]+", "_", stem)   
    doc_id = re.sub(r"[^\w]", "", doc_id)    # 알파벳·숫자·언더스코어 외 제거
    return doc_id.lower()

def pdf_to_images(pdf_path: str, dpi: int = DPI,
                  page_range: tuple[int, int] | None = None) -> list[dict]:
    """PDF를 페이지 이미지로 변환.
    page_range: (시작페이지, 끝페이지) 1-based inclusive. None이면 전체.
    """
    doc = fitz.open(pdf_path)
    total = len(doc)
    start, end = (page_range if page_range else (1, total))
    start = max(1, start)
    end   = min(total, end)
    print(f"  → 전체 {total}페이지 중 {start}~{end}페이지 처리")

    pages = []
    mat = fitz.Matrix(dpi / 72, dpi / 72)

    for i in range(start - 1, end):
        page = doc[i]
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
        img_bytes = pix.tobytes("png")
        pages.append({
            "page_num": i + 1,
            "img_bytes": img_bytes,
        })

    doc.close()
    print(f"  → {len(pages)}개 페이지 이미지 생성 완료")
    return pages


OCR_PROMPT = """이 이미지는 한국어 에너지 분석 보고서 PDF의 한 페이지입니다.
아래 형식에 따라 페이지 내용을 추출해 주세요.

[서술 텍스트]
제목, 소제목, 본문, 설명문, 시사점, 결론 등 서술형 문장을 모두 추출합니다.
완전한 문장 형태로 출력합니다.

[표 요약]
표가 있는 경우, 각 행의 핵심 내용을 "자치구명: 주요 수치 및 특성" 형식으로 서술합니다.
예) 강남구: 서비스업 전력 비율 62%, 군집 2 (활동 중심형)
수치만 나열하지 말고, 의미 있는 문장으로 변환합니다.

[차트 인사이트]
차트나 그래프가 있는 경우, 시각적으로 보이는 핵심 패턴을 한두 문장으로 요약합니다.
축 레이블이나 범례 수치만 나열하지 않습니다.

규칙:
- 단순 수치 나열(예: 1, 2, 3, 45.2, ...)은 출력하지 않습니다
- 서술 내용이 없는 페이지는 "내용 없음" 출력
- 섹션이 없으면 해당 섹션은 생략합니다
"""

def extract_text_with_vision(img_bytes: bytes, page_num: int) -> str:
    
    img_b64 = base64.standard_b64encode(img_bytes).decode("utf-8")

    response = client.models.generate_content(
        model=VISION_MODEL,
        contents=[
            types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
            OCR_PROMPT,
        ],
    )
    text = response.text.strip()
    if text == "내용 없음":
        return ""
    return text


_CHART_NOISE_RE = re.compile(
    r"^[\d\s,\.~\-\(\)·]*(만|MWh|%|명|연도|저점|기준선|백만|억|천)?[\d\s,\.~\-\(\)·]*$"
)
# 표의 쉼표 구분 수치 나열 패턴 (예: "강남구, 2, 2, 2, 2, 2, 2")
_TABLE_ROW_NOISE_RE = re.compile(
    r"^[가-힣]{2,5}[구군],\s*[\d,\s\.]+$"
)
# OCR 섹션 헤더 태그 (새 프롬프트에서 삽입됨)
_SECTION_HEADER_RE = re.compile(
    r"^\[(서술 텍스트|표 요약|차트 인사이트)\]$"
)

def remove_chart_noise(text: str) -> str:

    cleaned = []
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            cleaned.append("")
            continue

        # OCR 섹션 헤더 태그 제거 (내용은 유지, 태그만 제거)
        if _SECTION_HEADER_RE.fullmatch(s):
            continue

        korean_chars = [c for c in s if "\uAC00" <= c <= "\uD7A3"]

        if not korean_chars:
            continue
        if len(korean_chars) < 3 and len(s) <= 10:
            continue
        if _CHART_NOISE_RE.fullmatch(s):
            continue
        # 표 행 수치 나열 제거 (예: "강남구, 2, 2, 2, 2, 2, 2")
        if _TABLE_ROW_NOISE_RE.fullmatch(s):
            continue
        # 한국어 비율이 20% 미만인 짧은 줄 제거 (수치 위주 라인)
        if len(s) <= 30 and len(korean_chars) / len(s) < 0.20:
            continue

        cleaned.append(line)
    return "\n".join(cleaned).strip()

def split_into_chunks(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    
    text = remove_chart_noise(text)
    paragraphs = re.split(r"\n{2,}", text)
    chunks, current = [], ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if current and len(current) + len(para) + 2 > size:
            chunks.append(current.strip())
            current = current[-overlap:] + "\n\n" + para if len(current) > overlap else para
        else:
            current = (current + "\n\n" + para).strip() if current else para
    if current.strip() and len(current.strip()) > 50:
        chunks.append(current.strip())
    return chunks

_HEADING_RE = re.compile(
    r"^(Executive Summary|분석 개요|분석 목적|분석 범위|방법론|"
    r"군집 분석|상관관계|클러스터|결론|시사점|데이터 출처|변수|요약|"
    r"핵심 인사이트|분석 결과|정책 제언)"
)

def detect_section(text: str, prev: str) -> str:
    first = text.split("\n")[0].strip()
    return first if _HEADING_RE.match(first) else prev

def build_chunks(pages: list[dict], doc_id: str) -> list[dict]:

    chunks, section, idx = [], "General", 0
    for page in pages:
        raw = page.get("text", "").strip()
        if not raw:
            continue
        section = detect_section(raw, section)
        page_num = page["page_num"]
        local_idx = 0
        for chunk_text in split_into_chunks(raw):
            idx += 1
            local_idx += 1
            title = chunk_text.split("\n")[0][:60].strip() or f"페이지 {page_num}"
            chunks.append({
                "chunk_id": f"{doc_id}_p{page_num:04d}_c{local_idx:02d}",  # ← 페이지번호 포함
                "doc_id":   doc_id,
                "section":  section,
                "title":    title,
                "text":     chunk_text,
                "page_num": page_num,
            })
    return chunks

def get_embedding(text: str) -> list[float]:
    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(
            task_type="retrieval_document",
            output_dimensionality=768,
        ),
    )
    return response.embeddings[0].values

def delete_existing_chunks(doc_id: str):
    
    result = supabase.table("energy_rag_documents").delete().eq("doc_id", doc_id).execute()
    print(f"  기존 청크 삭제 완료 (doc_id={doc_id})")

def upload_chunks(chunks: list[dict], batch_size: int = 10):
    # chunk_id / 내용 유효성 검사
    valid_chunks = [
        c for c in chunks
        if c.get("chunk_id") and str(c["chunk_id"]) != "nan" and len(c.get("text", "")) >= 50
    ]
    skipped = len(chunks) - len(valid_chunks)
    if skipped:
        print(f"  ⚠ 유효하지 않은 청크 {skipped}개 제외 (chunk_id=nan 또는 내용 부족)")
    print(f"총 {len(valid_chunks)}개 청크 임베딩 및 업로드 시작")
    chunks = valid_chunks
    batch = []
    for i, chunk in enumerate(chunks):
        try:
            enriched = f"제목: {chunk['title']}\n내용: {chunk['text']}"
            embedding = get_embedding(enriched)
            batch.append({
                "chunk_id": chunk["chunk_id"],
                "doc_id":   chunk["doc_id"],
                "section":  chunk["section"],
                "title":    chunk["title"],
                "content":  chunk["text"],
                "metadata": {"page_num": chunk["page_num"]},
                "embedding": embedding,
            })
            if len(batch) >= batch_size or i == len(chunks) - 1:
                supabase.table("energy_rag_documents").insert(batch).execute()
                print(f"  업로드: {i + 1}/{len(chunks)}")
                batch = []
        except Exception as e:
            print(f"  실패: {chunk['chunk_id']} | {e}")
    print("모든 청크 적재 완료.")

def load_registry(registry_path: Path) -> dict:
    if registry_path.exists():
        import json
        return json.loads(registry_path.read_text(encoding="utf-8"))
    return {}

def save_registry(registry_path: Path, registry: dict):
    import json
    registry_path.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

def get_loaded_doc_ids() -> set:
    result = supabase.table("energy_rag_documents") \
        .select("doc_id") \
        .execute()
    return {row["doc_id"] for row in (result.data or [])}

def run_pipeline(pdf_path: str, doc_id: str, no_delete: bool = False,
                 page_range: tuple[int, int] | None = None):
    if not no_delete:
        print(f"  [0/4] 기존 청크 삭제 (doc_id={doc_id})")
        delete_existing_chunks(doc_id)

    print(f"  [1/4] PDF → 이미지: {pdf_path}")
    page_images = pdf_to_images(pdf_path, page_range=page_range)

    print("  [2/4] Vision OCR")
    for page in page_images:
        try:
            page["text"] = extract_text_with_vision(page["img_bytes"], page["page_num"])
            print(f"    페이지 {page['page_num']} ({len(page['text'])}자)")
            time.sleep(1)
        except Exception as e:
            print(f"    페이지 {page['page_num']} 실패: {e}")
            page["text"] = ""

    print("  [3/4] 청킹")
    chunks = build_chunks(page_images, doc_id=doc_id)
    print(f"    → {len(chunks)}개 청크")

    print("  [4/4] 임베딩 & 업로드")
    upload_chunks(chunks)


if __name__ == "__main__":
    import argparse, json

    parser = argparse.ArgumentParser(description="PDF → Supabase RAG 적재 스크립트")
    parser.add_argument("--dir",       default=".",
                        help="PDF 폴더 경로 (기본: 현재 디렉터리)")
    parser.add_argument("--pdf",       default=None,
                        help="특정 PDF 파일명만 처리 (예: --pdf \"제5차 서울특별시 지역에너지계획.pdf\")")
    parser.add_argument("--registry",  default="pdf_registry.json",
                        help="파일명↔doc_id 매핑 파일")
    parser.add_argument("--force",     action="store_true",
                        help="이미 적재된 문서도 강제 재적재")
    parser.add_argument("--no-delete", action="store_true",
                        help="기존 청크를 삭제하지 않고 추가 적재 (페이지 범위 분할 적재 시 사용)")
    parser.add_argument("--pages",     default=None,
                        help="처리할 페이지 범위 (예: 130-139). 생략 시 전체")
    args = parser.parse_args()

    pdf_dir       = Path(args.dir).resolve()
    registry_path = pdf_dir / args.registry
    registry      = load_registry(registry_path)

    # 전체 스캔 또는 특정 파일만
    if args.pdf:
        target = pdf_dir / args.pdf
        if not target.exists():
            print(f"파일을 찾을 수 없습니다: {target}")
            raise SystemExit
        pdf_files = [target]
    else:
        pdf_files = sorted(pdf_dir.glob("*.pdf"))
        if not pdf_files:
            print("PDF 파일이 없습니다.")
            raise SystemExit

    # 레지스트리 업데이트
    for pdf in pdf_files:
        if pdf.name not in registry:
            base_id = pdf_path_to_doc_id(pdf.name)
            if len(base_id.replace("_", "")) < 3:
                base_id = f"pdf_{len(registry) + 1:03d}"
            existing = set(registry.values())
            final_id, n = base_id, 1
            while final_id in existing:
                final_id = f"{base_id}_{n}"; n += 1
            registry[pdf.name] = final_id
            print(f"  신규 등록: {pdf.name} → doc_id: {final_id}")

    save_registry(registry_path, registry)

    # --pages 파싱
    page_range = None
    if args.pages:
        try:
            s, e = args.pages.split("-")
            page_range = (int(s), int(e))
        except ValueError:
            print(f"--pages 형식 오류: '{args.pages}' → '130-139' 형식으로 입력하세요.")
            raise SystemExit

    loaded_ids = get_loaded_doc_ids() if not args.force else set()

    for pdf in pdf_files:
        doc_id = registry[pdf.name]
        if doc_id in loaded_ids and not args.force and not args.no_delete:
            print(f"[SKIP] {pdf.name} (doc_id={doc_id} 이미 적재됨, --force 또는 --no-delete로 추가 가능)")
            continue
        print(f"\n{'='*60}")
        print(f"[START] {pdf.name}  →  doc_id: {doc_id}"
              + (f"  pages: {args.pages}" if args.pages else ""))
        print(f"{'='*60}")
        run_pipeline(str(pdf), doc_id, no_delete=args.no_delete,
                     page_range=page_range)

    print("\n전체 완료.")