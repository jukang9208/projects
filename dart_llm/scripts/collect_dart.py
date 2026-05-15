import csv
import io
import re
import sys
import time
import base64
import zipfile
import requests
import argparse
from pathlib import Path
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.config import settings

BASE_URL = "https://opendart.fss.or.kr/api"

CATEGORY_PBLNTF = {
    "사업보고서": "A",
    "감사보고서": "F",
    "유상증자":   "D",
    "자기주식":   "J",
    "전환사채":   "D",
    "합병·분할":  "B",
}


# 공시 목록 조회 
def fetch_list(category: str, bgn_de: str, end_de: str, page_count: int) -> list:
    
    resp = requests.get(f"{BASE_URL}/list.json", params={
        "crtfc_key":  settings.DART_API_KEY,
        "pblntf_ty":  CATEGORY_PBLNTF[category],
        "bgn_de":     bgn_de,
        "end_de":     end_de,
        "page_no":    1,
        "page_count": page_count,
    }, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "000":
        print(f"  목록 API 오류: {data.get('message')}")
        return []
    return data.get("list", [])


# 공시 원문 텍스트 추출 
DOC_URL = "https://opendart.fss.or.kr/api/document.xml"

def fetch_document_text(rcept_no: str, max_chars=3000) -> str:
    try:
        res = requests.get(DOC_URL, params={
            "crtfc_key": settings.DART_API_KEY,
            "rcept_no": rcept_no
        }, timeout=15)

        if res.status_code != 200:
            return ""

        with zipfile.ZipFile(io.BytesIO(res.content)) as z:
            candidates = [f for f in z.namelist() if f.endswith(('.htm', '.xml'))]
            if not candidates:
                return ""
            main_file = max(candidates, key=lambda f: z.getinfo(f).file_size)
            with z.open(main_file) as f:
                content = f.read()
                for enc in ['euc-kr', 'cp949', 'utf-8']:
                    try:
                        raw = content.decode(enc)
                        break
                    except:
                        continue
                else:
                    raw = content.decode('utf-8', errors='ignore')

        soup = BeautifulSoup(raw, 'lxml')
        for tag in soup(['script', 'style', 'table']):
            tag.decompose()
        text = soup.get_text(separator=' ', strip=True)
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:max_chars]

    except Exception:
        return ""


# 저장
def load_existing(out_path: Path) -> set:
    if not out_path.exists():
        return set()
    with open(out_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return {row["rcept_no"] for row in reader}


def save_rows(out_path: Path, rows: list, write_header: bool):
    mode = "w" if write_header else "a"
    with open(out_path, mode, encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["rcept_no", "corp_name", "report_nm", "rcept_dt", "label", "text"]
        )
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


# 메인
def collect(category: str, count: int, bgn_de: str, end_de: str):
    out_path = PROJECT_ROOT / settings.RAW_DATA_DIR / f"dart_{category}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    existing = load_existing(out_path)
    print(f"\n[{category}] 목록 조회 중... (기존 {len(existing)}건 스킵)")

    items = fetch_list(category, bgn_de, end_de, count)
    new_items = [i for i in items if i.get("rcept_no") not in existing]
    print(f"  새 항목: {len(new_items)}건")

    collected = 0
    for idx, item in enumerate(new_items, 1):
        rcept_no = item.get("rcept_no", "")
        print(f"  [{idx}/{len(new_items)}] {item.get('corp_name', '')} | {item.get('report_nm', '')[:40]}")

        text = fetch_document_text(rcept_no)
        if not text:
            print("    → 본문 없음, 스킵")
            time.sleep(0.5)
            continue

        row = {
            "rcept_no":  rcept_no,
            "corp_name": item.get("corp_name", ""),
            "report_nm": item.get("report_nm", ""),
            "rcept_dt":  item.get("rcept_dt", ""),
            "label":     category,
            "text":      text,
        }
        save_rows(out_path, [row], write_header=(not out_path.exists() and collected == 0))
        collected += 1
        time.sleep(0.4)   # API rate limit

    print(f"  완료: {collected}건 저장 → {out_path}")
    return collected


PERIODS = [
    ("20220101", "20220331"), ("20220401", "20220630"),
    ("20220701", "20220930"), ("20221001", "20221231"),
    ("20230101", "20230331"), ("20230401", "20230630"),
    ("20230701", "20230930"), ("20231001", "20231231"),
    ("20240101", "20240331"), ("20240401", "20240630"),
    ("20240701", "20240930"), ("20241001", "20241231"),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", default="사업보고서", choices=list(CATEGORY_PBLNTF.keys()))
    parser.add_argument("--all", action="store_true", help="전 카테고리 수집")
    parser.add_argument("--count", type=int, default=100, help="카테고리당 최대 수집 건수")
    args = parser.parse_args()

    categories = list(CATEGORY_PBLNTF.keys()) if args.all else [args.category]
    total = 0
    for cat in categories:
        for bgn, end in PERIODS:
            total += collect(cat, args.count, bgn, end)

    print(f"\n전체 수집 완료: {total}건")


if __name__ == "__main__":
    main()
