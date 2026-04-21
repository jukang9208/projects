import sys
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

from core.config import supabase


def process_and_upload():
    data_dir = BASE_DIR / "data"

    # 가스 데이터 정제 (gas.csv)
    gas_raw = pd.read_csv(data_dir / "gas.csv", skiprows=3, header=None, encoding="utf-8-sig")

    # 이후 9 간격으로 연도별 가정용 수급가구수 추출
    # 3(2019), 12(2020), 21(2021), 30(2022), 39(2023), 48(2024)
    gas_df = gas_raw[[1, 3, 12, 21, 30, 39, 48]].copy()
    gas_df.columns = ["district", "2019", "2020", "2021", "2022", "2023", "2024"]
    gas_df = gas_df[~gas_df["district"].isin(["소계", "동별(2)"])].copy()

    gas_melted = gas_df.melt(id_vars=["district"],var_name="year",value_name="gas_supply")

    gas_melted["year"] = gas_melted["year"].astype(int)
    gas_melted["gas_supply"] = pd.to_numeric(gas_melted["gas_supply"].astype(str).str.replace(",", ""),errors="coerce")
    gas_melted = gas_melted.dropna(subset=["gas_supply"]).copy()
    gas_melted["gas_supply"] = gas_melted["gas_supply"].astype(int)

    # 소득 데이터 정제 (income.csv)
    income_raw = pd.read_csv(data_dir / "income.csv", encoding="euc-kr")
    income_raw["year"] = (income_raw["기준_년분기_코드"] // 10).astype(int)
    income_raw["quarter"] = (income_raw["기준_년분기_코드"] % 10).astype(int)

    income_filtered = income_raw[
        (income_raw["year"] <= 2024) &
        (income_raw["quarter"] == 4)
    ].copy()

    income_yearly = income_filtered[["year", "행정동_코드_명", "월_평균_소득_금액"]].copy()
    income_yearly.columns = ["year", "district", "avg_income"]

    income_yearly["avg_income"] = pd.to_numeric(income_yearly["avg_income"].astype(str).str.replace(",", ""),errors="coerce")
    income_yearly = income_yearly.dropna(subset=["avg_income"]).copy()

    # 인구 데이터 정제 (population.csv)
    pop_raw = pd.read_csv(data_dir / "population.csv", encoding="euc-kr")
    pop_raw["year"] = (pop_raw["기준_년분기_코드"] // 10).astype(int)
    pop_raw["quarter"] = (pop_raw["기준_년분기_코드"] % 10).astype(int)

    pop_filtered = pop_raw[
        (pop_raw["year"] <= 2024) &
        (pop_raw["quarter"] == 4)
    ].copy()

    pop_yearly = pop_filtered[["year", "자치구_코드_명", "총_상주인구_수", "총_가구_수"]].copy()
    pop_yearly.columns = ["year", "district", "total_pop", "total_households"]

    pop_yearly["total_pop"] = pd.to_numeric(pop_yearly["total_pop"].astype(str).str.replace(",", ""),errors="coerce")
    pop_yearly["total_households"] = pd.to_numeric(pop_yearly["total_households"].astype(str).str.replace(",", ""),errors="coerce")

    pop_yearly = pop_yearly.dropna(subset=["total_pop", "total_households"]).copy()
    pop_yearly["total_pop"] = pop_yearly["total_pop"].astype(int)
    pop_yearly["total_households"] = pop_yearly["total_households"].astype(int)

    # 문자열 정리
    for df in [gas_melted, income_yearly, pop_yearly]:
        df["district"] = df["district"].astype(str).str.strip()

    # Supabase 업로드 
    def upload_to_supabase(df, table_name):
        data = df.to_dict(orient="records")
        print(f"{table_name} 업로드 시작... (총 {len(data)}건)")

        for i in range(0, len(data), 100):
            batch = data[i:i + 100]
            supabase.table(table_name).upsert(batch).execute()

        print(f"{table_name} 완료!")

    # 업로드 실행
    upload_to_supabase(gas_melted, "gas_supply")
    upload_to_supabase(income_yearly, "income_stats")
    upload_to_supabase(pop_yearly, "pop_stats")


if __name__ == "__main__":
    process_and_upload()