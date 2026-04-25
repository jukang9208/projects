import os
import io
import zipfile
import xml.etree.ElementTree as ET
import requests
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

DART_API_KEY  = os.environ["DART_API_KEY"]
SUPABASE_URL  = os.environ["SUPABASE_URL"]
SUPABASE_KEY  = os.environ["SUPABASE_KEY"]
CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"

def fetch_corp_codes() -> list[dict]:

    print("DART corpCode.xml 다운로드 중...")
    res = requests.get(
        CORP_CODE_URL,
        params={"crtfc_key": DART_API_KEY},
        timeout=30,
    )
    res.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(res.content)) as z:
        xml_name = [f for f in z.namelist() if f.endswith(".xml")][0]
        with z.open(xml_name) as f:
            tree = ET.parse(f)

    corps = []
    for item in tree.getroot().findall("list"):
        corp_code  = (item.findtext("corp_code")  or "").strip()
        corp_name  = (item.findtext("corp_name")  or "").strip()
        stock_code = (item.findtext("stock_code") or "").strip() or None
        modify_date = (item.findtext("modify_date") or "").strip() or None

        if corp_code and corp_name:
            corps.append({
                "corp_code":   corp_code,
                "corp_name":   corp_name,
                "stock_code":  stock_code,
                "modify_date": modify_date,
            })

    print(f"파싱 완료: {len(corps):,}개 기업")
    return corps


def upload(corps: list[dict]) -> None:

    client = create_client(SUPABASE_URL, SUPABASE_KEY)

    BATCH = 500
    total = len(corps)
    success = 0

    for i in range(0, total, BATCH):
        batch = corps[i : i + BATCH]
        client.table("dart_corps").upsert(batch, on_conflict="corp_code").execute()
        success += len(batch)
        print(f"  업로드: {success:,} / {total:,}")

    print(f"\n완료: {success:,}개 업로드")


if __name__ == "__main__":
    corps = fetch_corp_codes()
    upload(corps)
