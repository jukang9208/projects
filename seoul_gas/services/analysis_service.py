import pandas as pd
from supabase import Client
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

class EnergyAnalysisService:

    def __init__(self, supabase: Client):
        self.supabase = supabase

    def get_merged_data(self, year: int):

        gas = self.supabase.table("gas_supply").select("*").eq("year", year).execute()
        income = self.supabase.table("income_stats").select("*").eq("year", year).execute()
        pop = self.supabase.table("pop_stats").select("*").eq("year", year).execute()
        df_gas = pd.DataFrame(gas.data)
        df_income = pd.DataFrame(income.data)
        df_pop = pd.DataFrame(pop.data)
        if df_gas.empty or df_income.empty or df_pop.empty:
            return None

        df_gas = df_gas[["district", "year", "gas_supply"]].copy()
        df_income = df_income[["district", "year", "avg_income"]].copy()
        df_pop = df_pop[["district", "year", "total_pop", "total_households"]].copy()
        merged = pd.merge(df_gas, df_income, on=["district", "year"], how="inner")
        merged = pd.merge(merged, df_pop, on=["district", "year"], how="inner")
        if merged.empty:
            return None

        numeric_cols = ["gas_supply", "avg_income", "total_pop", "total_households"]
        for col in numeric_cols:
            merged[col] = pd.to_numeric(merged[col], errors="coerce")

        merged = merged.dropna(subset=numeric_cols).copy()
        merged = merged[
            (merged["avg_income"] > 0) &
            (merged["total_pop"] > 0) &
            (merged["total_households"] > 0) &
            (merged["gas_supply"] >= 0)
        ].copy()
        if merged.empty:
            return None

        merged["gas_supply_per_pop"] = merged["gas_supply"] / merged["total_pop"]
        merged["gas_supply_per_income"] = merged["gas_supply"] / merged["avg_income"]
        merged["pop_per_household"] = merged["total_pop"] / merged["total_households"]
        merged["income_per_household"] = merged["avg_income"] / merged["total_households"]
        merged["gas_supply_ratio"] = merged["gas_supply"] / merged["total_households"]

        return merged

    def get_correlation_data(self):

        years = [2019, 2020, 2021, 2022, 2023, 2024]
        raw_cols = [
            "gas_supply",
            "avg_income",
            "total_pop",
            "total_households",
        ]
        derived_cols = [
            "gas_supply_per_pop",
            "gas_supply_ratio",
            "pop_per_household",
            "income_per_household",
        ]
        raw_dfs = []
        derived_dfs = []
        for y in years:
            df = self.get_merged_data(y)
            if df is None:
                continue

            raw_available = [col for col in raw_cols if col in df.columns]
            derived_available = [col for col in derived_cols if col in df.columns]
            if len(raw_available) >= 2:
                raw_dfs.append(df[raw_available].copy())
            if len(derived_available) >= 2:
                derived_dfs.append(df[derived_available].copy())

        if not raw_dfs and not derived_dfs:
            return {"error": "분석할 데이터가 존재하지 않습니다."}

        result = {
            "period": "2019-2024",
            "raw_features": raw_cols,
            "derived_features": derived_cols,
        }
        if raw_dfs:
            raw_df = pd.concat(raw_dfs, ignore_index=True)
            raw_corr = raw_df.corr(numeric_only=True).round(3)
            result["raw_total_records"] = len(raw_df)
            result["raw_correlation_matrix"] = raw_corr.to_dict()
        else:
            result["raw_total_records"] = 0
            result["raw_correlation_matrix"] = {}
        if derived_dfs:
            derived_df = pd.concat(derived_dfs, ignore_index=True)
            derived_corr = derived_df.corr(numeric_only=True).round(3)
            result["derived_total_records"] = len(derived_df)
            result["derived_correlation_matrix"] = derived_corr.to_dict()
        else:
            result["derived_total_records"] = 0
            result["derived_correlation_matrix"] = {}
        return result

    def find_optimal_k(self, df: pd.DataFrame, max_k=10):

        features = [
         "gas_supply",
         "total_households",
         "avg_income",
         "total_pop"
        ]
        clustering_df = df[features].dropna().copy()
        if len(clustering_df) < 2:
            return {
                "k_range": [],
                "inertias": [],
                "silhouette_scores": []
            }
        scaler = StandardScaler()
        scaled_features = scaler.fit_transform(clustering_df)

        max_k = min(max_k, len(clustering_df) - 1)
        if max_k < 2:
            return {
                "k_range": [],
                "inertias": [],
                "silhouette_scores": []
            }

        inertias = []
        silhouette_avg_scores = []
        k_range = range(2, max_k + 1)

        for k in k_range:
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            cluster_labels = kmeans.fit_predict(scaled_features)
            inertias.append(kmeans.inertia_)
            score = silhouette_score(scaled_features, cluster_labels)
            silhouette_avg_scores.append(score)
        return {
            "k_range": list(k_range),
            "inertias": inertias,
            "silhouette_scores": silhouette_avg_scores
        }
    def perform_clustering(self, df: pd.DataFrame, n_clusters=4):

        features = [
            "gas_supply",
            "total_households",
            "avg_income",
            "total_pop"
        ]
        clustering_df = df.dropna(subset=features).copy()
        if clustering_df.empty:
            return {
                "data": df.copy(),
                "metrics": {
                    "silhouette_score": None,
                    "inertia": None,
                    "n_clusters": n_clusters
                }
            }
        n_clusters = min(n_clusters, len(clustering_df))
        if n_clusters < 2:
            clustering_df["cluster"] = 0
            result_df = df.copy()
            result_df = result_df.merge(clustering_df[["district", "year", "cluster"]],on=["district", "year"],how="left")
            return {
                "data": result_df,
                "metrics": {
                    "silhouette_score": None,
                    "inertia": 0.0,
                    "n_clusters": 1
                }
            }
        scaler = StandardScaler()
        scaled_features = scaler.fit_transform(clustering_df[features])
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        clustering_df["cluster"] = kmeans.fit_predict(scaled_features)
        s_score = silhouette_score(scaled_features, clustering_df["cluster"])
        inertia = kmeans.inertia_
        result_df = df.copy()
        result_df = result_df.merge(clustering_df[["district", "year", "cluster"]],on=["district", "year"],how="left")
        return {
            "data": result_df,
            "metrics": {
                "silhouette_score": round(s_score, 4),
                "inertia": round(inertia, 2),
                "n_clusters": n_clusters
            }
        }    
    def get_district_trend(self, district: str) -> list:
        
        try:
            # 도시가스 수급가구수 
            gas_res = self.supabase.table("gas_supply").select("year, gas_supply, district").eq("district", district).order("year", desc=False).execute()
            # 인구 통계 
            pop_res = self.supabase.table("pop_stats").select("year, total_pop").eq("district", district).execute()
            # 소득 통계
            income_res = self.supabase.table("income_stats").select("year, avg_income").eq("district", district).execute()
            # 데이터 병합 
            gas_data = gas_res.data or []
            pop_dict = {item['year']: item['total_pop'] for item in (pop_res.data or [])}
            income_dict = {item['year']: item['avg_income'] for item in (income_res.data or [])}

            combined_data = []
            for row in gas_data:
                year = row['year']
                row['total_pop'] = pop_dict.get(year, 0) 
                row['avg_income'] = income_dict.get(year, 0)
                combined_data.append(row)
            return combined_data
            
        except Exception as e:
            print(f"Error fetching combined trend for {district}: {e}")
            return []