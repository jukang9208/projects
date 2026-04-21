import pandas as pd
from sklearn.preprocessing import StandardScaler

def to_dataframe(rows):

    df = pd.DataFrame(rows)

    if df.empty:
        raise ValueError("데이터가 비어있습니다.")

    return df

def select_feature_columns(df):

    feature_cols = [
        "total_resident_population",
        "total_households",
        "gas_supply_ratio",
        "home_ratio",
        "public_ratio",
        "service_ratio",
        "industry_ratio",
    ]

    missing_cols = [col for col in feature_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"누락된 컬럼: {missing_cols}")

    df_features = df[feature_cols].copy()

    return df_features

def clean_dataframe(df):

    df = df.copy()
    df = df.apply(pd.to_numeric, errors="coerce")
    df = df.dropna()

    if df.empty:
        raise ValueError("전처리 후 데이터가 비어있습니다.")

    return df


def scale_features(df):

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df)

    return X_scaled, scaler

def prepare_scaled_features(rows):

    df = to_dataframe(rows)
    df_features = select_feature_columns(df)
    df_clean = clean_dataframe(df_features)
    X_scaled, scaler = scale_features(df_clean)

    return df_clean, X_scaled, scaler