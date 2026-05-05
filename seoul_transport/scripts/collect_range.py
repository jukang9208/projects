import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, PROJECT_ROOT)
from core.config import settings
from ingestion.subway_collector import fetch_subway_data, save_raw


def date_range(start: str, end: str):
   
    s = datetime.strptime(start, "%Y%m%d")
    e = datetime.strptime(end, "%Y%m%d")
    while s <= e:
        yield s.strftime("%Y%m%d")
        s += timedelta(days=1)


def already_collected(date: str) -> bool:
    
    import pandas as pd
    path = Path(settings.RAW_PATH) / "subway" / date[:6] / f"subway_{date}.csv"
    if not path.exists():
        return False
    # 컬럼 확인
    df = pd.read_csv(path, nrows=1)
    return "SBWY_ROUT_LN_NM" in df.columns


def run(start: str, end: str, overwrite: bool = False):
    dates = list(date_range(start, end))
    print(f"\n수집 대상: {start} ~ {end} ({len(dates)}일)\n")

    success, skip, fail = [], [], []

    for date in dates:
        if not overwrite and already_collected(date):
            print(f"[SKIP] {date} - 이미 수집됨")
            skip.append(date)
            continue

        try:
            df = fetch_subway_data(date=date)
            if df.empty:
                print(f"[EMPTY] {date} - 데이터 없음 (휴일/미집계)")
                skip.append(date)
            else:
                save_raw(df, date)
                print(f"[OK]   {date} - {len(df)}행 저장")
                success.append(date)
        except Exception as e:
            print(f"[FAIL] {date} - {e}")
            fail.append(date)

    print(f"\n{'='*40}")
    print(f"완료: {len(success)}일 / 스킵: {len(skip)}일 / 실패: {len(fail)}일")
    if fail:
        print(f"실패 날짜: {', '.join(fail)}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("사용법: python collect_range.py <시작날짜> <종료날짜> [--overwrite]")
        print("예시:   python collect_range.py 20260401 20260430")
        sys.exit(1)

    start_date = sys.argv[1]
    end_date   = sys.argv[2]
    overwrite  = "--overwrite" in sys.argv

    run(start_date, end_date, overwrite=overwrite)