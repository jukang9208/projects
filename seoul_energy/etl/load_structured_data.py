import sys
import math
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

from core.config import Settings, supabase

def read_csv_flexible(path: Path, **kwargs) -> pd.DataFrame:
    encodings = ["utf-8-sig", "cp949", "euc-kr", "utf-8"]
    last_error = None

    for encoding in encodings:
        try:
            return pd.read_csv(path, encoding=encoding, **kwargs)
        except Exception as e:
            last_error = e

    raise RuntimeError(f"CSV 읽기 실패: {path}\n{last_error}")

def clean_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str).str.replace(",", "", regex=False).str.replace("-", "0", regex=False).str.strip(),
        errors="coerce",
    )

def safe_ratio(numerator, denominator, digits=6):
    if denominator in [0, None] or pd.isna(denominator):
        return None
    value = numerator / denominator
    if math.isinf(value) or math.isnan(value):
        return None
    return round(value, digits)

def upload_to_supabase(df: pd.DataFrame, table_name: str, batch_size: int = 100) -> None:
    data = df.to_dict(orient="records")
    print(f"{table_name} 업로드 시작... (총 {len(data)}건)")

    for i in range(0, len(data), batch_size):
        batch = data[i:i + batch_size]
        supabase.table(table_name).upsert(batch).execute()

    print(f"{table_name} 완료!")

def process_gas_data(data_dir: Path) -> pd.DataFrame:
    gas_raw = read_csv_flexible(
        data_dir / "gas.csv",
        skiprows=3,
        header=None,
    )

    # 9 간격 대표 컬럼
    # 3(2019), 12(2020), 21(2021), 30(2022), 39(2023), 48(2024)
    gas_df = gas_raw[[1, 3, 12, 21, 30, 39, 48]].copy()
    gas_df.columns = ["district", "2019", "2020", "2021", "2022", "2023", "2024"]

    gas_df["district"] = gas_df["district"].astype(str).str.strip()
    gas_df = gas_df[~gas_df["district"].isin(["소계", "동별(2)", "nan"])].copy()

    gas_melted = gas_df.melt(
        id_vars=["district"],
        var_name="year",
        value_name="gas_supply",
    )

    gas_melted["year"] = gas_melted["year"].astype(int)
    gas_melted["gas_supply"] = clean_numeric(gas_melted["gas_supply"])
    gas_melted = gas_melted.dropna(subset=["gas_supply"]).copy()
    gas_melted["gas_supply"] = gas_melted["gas_supply"].astype(int)

    return gas_melted

def process_pop_data(data_dir: Path) -> pd.DataFrame:
    pop_raw = read_csv_flexible(data_dir / "pop.csv")

    pop_raw["year"] = (pop_raw["기준_년분기_코드"] // 10).astype(int)
    pop_raw["quarter"] = (pop_raw["기준_년분기_코드"] % 10).astype(int)

    # 분기별 마지막 자리 4만 사용
    pop_filtered = pop_raw[
        (pop_raw["year"] >= 2019) &
        (pop_raw["year"] <= 2024) &
        (pop_raw["quarter"] == 4)
    ].copy()

    pop_yearly = pop_filtered[["year", "자치구_코드_명", "총_상주인구_수", "총_가구_수"]].copy()
    pop_yearly.columns = ["year", "district", "total_resident_population", "total_households"]

    pop_yearly["district"] = pop_yearly["district"].astype(str).str.strip()
    pop_yearly["total_resident_population"] = clean_numeric(pop_yearly["total_resident_population"])
    pop_yearly["total_households"] = clean_numeric(pop_yearly["total_households"])

    pop_yearly = pop_yearly.dropna(subset=["total_resident_population", "total_households"]).copy()
    pop_yearly["total_resident_population"] = pop_yearly["total_resident_population"].astype(int)
    pop_yearly["total_households"] = pop_yearly["total_households"].astype(int)

    return pop_yearly

def process_resident_register_data(data_dir: Path) -> pd.DataFrame:
    r_raw = read_csv_flexible(data_dir / "r_rpop.csv")

    # 합계 연령대 + 성별(합계/남자/여자)만 사용
    r_filtered = r_raw[
        (r_raw["각세별"] == "합계") &
        (r_raw["성별"].isin(["합계", "남자", "여자"]))
    ].copy()

    year_cols = {
        2019: "2019 년",
        2020: "2020 년",
        2021: "2021 년",
        2022: "2022 년",
        2023: "2023 년",
        2024: "2024 년",
    }

    result = []

    for year, col in year_cols.items():
        temp = r_filtered[["자치구별", "성별", col]].copy()
        temp.columns = ["district", "gender", "value"]

        temp["district"] = temp["district"].astype(str).str.strip()
        temp["value"] = clean_numeric(temp["value"])
        temp = temp.dropna(subset=["value"]).copy()
        temp["value"] = temp["value"].astype(int)

        pivoted = temp.pivot_table(
            index="district",
            columns="gender",
            values="value",
            aggfunc="first",
        ).reset_index()

        pivoted = pivoted.rename(
            columns={
                "합계": "total_registered_population",
                "남자": "male_population",
                "여자": "female_population",
            }
        )

        pivoted = pivoted[~pivoted["district"].isin(["합계", "서울시", "nan"])].copy()
        pivoted["year"] = year

        pivoted["male_female_ratio"] = pivoted.apply(
            lambda row: safe_ratio(row["male_population"], row["female_population"]),
            axis=1,
        )

        result.append(
            pivoted[
                [
                    "district",
                    "year",
                    "total_registered_population",
                    "male_population",
                    "female_population",
                    "male_female_ratio",
                ]
            ]
        )

    rrpop_yearly = pd.concat(result, ignore_index=True)
    return rrpop_yearly

def process_electricity_data(data_dir: Path) -> pd.DataFrame:
    ele_raw = read_csv_flexible(data_dir / "ele_used.csv")

    # 상단 헤더 구조 기준:
    # 0행: 합계
    # 1행: 가정용 / 공공용 / 서비스업 / 산업용
    # 2행: 소계 / 전철 / 수도 / 사업자용 / 순수서비스 / 제조업 ...
    # 실제 데이터는 3행부터
    ele_data = ele_raw.iloc[3:].copy()

    ele_data.columns = ele_raw.columns
    ele_data["district"] = ele_data["자치구별(2)"].astype(str).str.strip()

    ele_data = ele_data[~ele_data["district"].isin(["소계", "합계", "자치구별(2)", "nan"])].copy()

    # 컬럼 구조: 합계/가정용/공공용/서비스업소계/서비스업전철/서비스업수도/서비스업사업자용/서비스업순수서비스/산업용소계/...
    # pandas 자동 헤더: 2019=합계, 2019.1=가정용, 2019.2=공공용, 2019.3=서비스업소계
    year_col_map = {
        2019: {
            "home_usage": "2019.1",
            "public_usage": "2019.2",
            "service_usage": "2019.3",
            "industry_usage": "2019.8",
        },
        2020: {
            "home_usage": "2020.1",
            "public_usage": "2020.2",
            "service_usage": "2020.3",
            "industry_usage": "2020.8",
        },
        2021: {
            "home_usage": "2021.1",
            "public_usage": "2021.2",
            "service_usage": "2021.3",
            "industry_usage": "2021.8",
        },
        2022: {
            "home_usage": "2022.1",
            "public_usage": "2022.2",
            "service_usage": "2022.3",
            "industry_usage": "2022.8",
        },
        2023: {
            "home_usage": "2023.1",
            "public_usage": "2023.2",
            "service_usage": "2023.3",
            "industry_usage": "2023.8",
        },
        2024: {
            "home_usage": "2024.1",
            "public_usage": "2024.2",
            "service_usage": "2024.3",
            "industry_usage": "2024.8",
        },
    }

    result = []

    for year, cols in year_col_map.items():
        temp = ele_data[
            [
                "district",
                cols["home_usage"],
                cols["public_usage"],
                cols["service_usage"],
                cols["industry_usage"],
            ]
        ].copy()

        temp.columns = [
            "district",
            "home_usage",
            "public_usage",
            "service_usage",
            "industry_usage",
        ]

        for col in ["home_usage", "public_usage", "service_usage", "industry_usage"]:
            temp[col] = clean_numeric(temp[col])

        temp = temp.dropna(subset=["home_usage", "public_usage", "service_usage", "industry_usage"]).copy()

        for col in ["home_usage", "public_usage", "service_usage", "industry_usage"]:
            temp[col] = temp[col].astype(int)

        temp["year"] = year
        temp["total_usage"] = (
            temp["home_usage"] +
            temp["public_usage"] +
            temp["service_usage"] +
            temp["industry_usage"]
        )

        temp["home_ratio"] = temp.apply(lambda row: safe_ratio(row["home_usage"], row["total_usage"]), axis=1)
        temp["public_ratio"] = temp.apply(lambda row: safe_ratio(row["public_usage"], row["total_usage"]), axis=1)
        temp["service_ratio"] = temp.apply(lambda row: safe_ratio(row["service_usage"], row["total_usage"]), axis=1)
        temp["industry_ratio"] = temp.apply(lambda row: safe_ratio(row["industry_usage"], row["total_usage"]), axis=1)

        result.append(
            temp[
                [
                    "district",
                    "year",
                    "home_usage",
                    "public_usage",
                    "service_usage",
                    "industry_usage",
                    "home_ratio",
                    "public_ratio",
                    "service_ratio",
                    "industry_ratio",
                ]
            ]
        )

    electricity_yearly = pd.concat(result, ignore_index=True)
    return electricity_yearly

def process_integrated_data(
    gas_df: pd.DataFrame,
    pop_df: pd.DataFrame,
    rrpop_df: pd.DataFrame,
    ele_df: pd.DataFrame,
) -> pd.DataFrame:
    merged = pop_df.merge(gas_df, on=["district", "year"], how="inner")
    merged = merged.merge(rrpop_df, on=["district", "year"], how="left")
    merged = merged.merge(ele_df, on=["district", "year"], how="inner")

    merged["gas_supply_ratio"] = merged.apply(
        lambda row: safe_ratio(row["gas_supply"], row["total_households"]),
        axis=1,
    )

    final_df = merged[
        [
            "district",
            "year",
            "total_resident_population",
            "total_households",
            "gas_supply",
            "gas_supply_ratio",
            "total_registered_population",
            "male_population",
            "female_population",
            "male_female_ratio",
            "home_usage",
            "public_usage",
            "service_usage",
            "industry_usage",
            "home_ratio",
            "public_ratio",
            "service_ratio",
            "industry_ratio",
        ]
    ].copy()

    return final_df

def process_and_upload():
    if not Settings.supabase_URL or not Settings.supabase_KEY:
        raise ValueError("supabase_URL 또는 supabase_KEY가 비어 있습니다.")

    data_dir = BASE_DIR / "data"

    gas_df = process_gas_data(data_dir)
    pop_df = process_pop_data(data_dir)
    rrpop_df = process_resident_register_data(data_dir)
    ele_df = process_electricity_data(data_dir)
    integrated_df = process_integrated_data(gas_df, pop_df, rrpop_df, ele_df)

    for df in [gas_df, pop_df, rrpop_df, ele_df, integrated_df]:
        df["district"] = df["district"].astype(str).str.strip()

    upload_to_supabase(gas_df, "seoul_gas_supply")
    upload_to_supabase(pop_df, "seoul_pop_stats")
    upload_to_supabase(rrpop_df, "seoul_resident_register_stats")
    upload_to_supabase(ele_df, "seoul_electricity_usage")
    upload_to_supabase(integrated_df, "seoul_district_energy_stats")

    print("전체 업로드 완료")

if __name__ == "__main__":
    process_and_upload()