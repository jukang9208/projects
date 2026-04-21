
import os
import re
import time
import fitz      
import base64   
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
DOC_ID         = "seoul_energy_pdf"
CHUNK_SIZE     = 1200   
CHUNK_OVERLAP  = 200    
DPI            = 150    


def pdf_to_images(pdf_path: str, dpi: int = DPI) -> list[dict]:
    
    doc = fitz.open(pdf_path)
    pages = []
    mat = fitz.Matrix(dpi / 72, dpi / 72)  

    for i, page in enumerate(doc):
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
페이지에 표시된 **모든 텍스트**를 빠짐없이 그대로 추출해 주세요.

규칙:
- 표, 차트 레이블, 수치, 단위 모두 포함
- 이미지 설명이나 분석 없이 텍스트만 출력
- 텍스트가 없는 페이지는 "내용 없음" 출력
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

def remove_chart_noise(text: str) -> str:
    
    cleaned = []
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            cleaned.append("")
            continue

        korean_chars = [c for c in s if "\uAC00" <= c <= "\uD7A3"]

        
        if not korean_chars:
            continue

       
        if len(korean_chars) < 3 and len(s) <= 10:
            continue

        
        if _CHART_NOISE_RE.fullmatch(s):
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


def build_chunks(pages: list[dict]) -> list[dict]:
    
    chunks, section, idx = [], "General", 0
    for page in pages:
        raw = page.get("text", "").strip()
        if not raw:
            continue
        section = detect_section(raw, section)
        for chunk_text in split_into_chunks(raw):
            idx += 1
            title = chunk_text.split("\n")[0][:60].strip() or f"페이지 {page['page_num']}"
            chunks.append({
                "chunk_id": f"pdf_chunk_{idx:04d}",
                "doc_id":   DOC_ID,
                "section":  section,
                "title":    title,
                "text":     chunk_text,
                "page_num": page["page_num"],
            })
    return chunks


def get_embedding(text: str) -> list[float]:
    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config={"task_type": "retrieval_document", "output_dimensionality": 768},
    )
    return response.embeddings[0].values


def upload_chunks(chunks: list[dict], batch_size: int = 10):
    print(f"총 {len(chunks)}개 청크 임베딩 및 업로드 시작")
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



if __name__ == "__main__":
    PDF_PATH = "seoul_energy.pdf"

    print(f"[1/4] PDF 페이지 이미지 변환: {PDF_PATH}")
    page_images = pdf_to_images(PDF_PATH)

    print("[2/4] Gemini Vision으로 텍스트 추출 (페이지당 약 2~3초 소요)")
    for page in page_images:
        try:
            page["text"] = extract_text_with_vision(page["img_bytes"], page["page_num"])
            print(f"  페이지 {page['page_num']} 완료 ({len(page['text'])}자)")
            time.sleep(1)  
        except Exception as e:
            print(f"  페이지 {page['page_num']} 실패: {e}")
            page["text"] = ""

    
    print("[3/4] 텍스트 청킹")
    chunks = build_chunks(page_images)
    print(f"  → {len(chunks)}개 청크 생성")

  
    print("[4/4] 임베딩 & Supabase 업로드")
    upload_chunks(chunks)