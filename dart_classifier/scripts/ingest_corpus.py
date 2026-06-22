import sys
import csv
import time
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services.embedder import embed_text
from services.rag import get_client


CSV_PATH   = ROOT / "data" / "dart_corpus_text.csv"
TABLE      = "dart_rag_documents"
DELAY_SEC  = 0.3   

def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def ingest_chunk(
    chunk_id: str,
    doc_id: str,
    content: str,
    title: str,
    metadata: dict,
) -> bool:

    embedding = embed_text(content)
    row = {
        "chunk_id": chunk_id,
        "doc_id":   doc_id,
        "content":  content,
        "title":    title,
        "section":  None,
        "metadata": metadata,
        "embedding": embedding,
    }
    result = (
        get_client()
        .table(TABLE)
        .upsert(row, on_conflict="chunk_id")
        .execute()
    )
    return bool(result.data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunk-size", type=int, default=800,  help="청크 최대 글자 수 (기본 800)")
    parser.add_argument("--overlap",    type=int, default=100,  help="청크 간 겹침 글자 수 (기본 100)")
    parser.add_argument("--limit",      type=int, default=None, help="처리할 최대 행 수 (테스트용)")
    parser.add_argument("--skip",       type=int, default=0,    help="건너뛸 시작 행 수 (재시작용)")
    args = parser.parse_args()

    print(f"[ingest_corpus] CSV: {CSV_PATH}")
    print(f"[ingest_corpus] chunk_size={args.chunk_size}, overlap={args.overlap}")
    if args.limit:
        print(f"[ingest_corpus] limit={args.limit} 행만 처리")

    total_chunks = 0
    total_docs   = 0
    errors       = 0

    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    rows = rows[args.skip:]
    if args.limit:
        rows = rows[:args.limit]

    print(f"[ingest_corpus] 처리 대상: {len(rows)}건\n")

    for idx, row in enumerate(rows, start=1):
        rcept_no  = row["rcept_no"].strip()
        corp_name = row["corp_name"].strip()
        report_nm = row["report_nm"].strip()
        rcept_dt  = row["rcept_dt"].strip()
        label     = row["label"].strip()
        text      = row["text"].strip()

        if not text:
            print(f"  [{idx}/{len(rows)}] {rcept_no} — 텍스트 없음, 건너뜀")
            continue

        metadata = {
            "company_code": corp_name,
            "report_type":  label,
            "period":       rcept_dt[:4],   
            "rcept_dt":     rcept_dt,
        }

        chunks = chunk_text(text, args.chunk_size, args.overlap)
        print(f"  [{idx}/{len(rows)}] {corp_name} / {report_nm} → {len(chunks)}개 청크", end="", flush=True)

        doc_ok = True
        for c_idx, chunk in enumerate(chunks):
            chunk_id = f"{rcept_no}_{c_idx:04d}"
            try:
                ingest_chunk(
                    chunk_id=chunk_id,
                    doc_id=rcept_no,
                    content=chunk,
                    title=report_nm,
                    metadata=metadata,
                )
                total_chunks += 1
                time.sleep(DELAY_SEC)
            except Exception as e:
                print(f"\n    ⚠️  chunk {chunk_id} 실패: {e}")
                errors += 1
                doc_ok = False
                time.sleep(1.0)   

        print(" ✓" if doc_ok else " ✗")
        total_docs += 1

    print(f"\n[ingest_corpus] 완료!")
    print(f"  문서: {total_docs}건 / 청크: {total_chunks}개 / 오류: {errors}개")


if __name__ == "__main__":
    main()