import FinanceDataReader as fdr
from datetime import datetime, timedelta


def get_market_data(stock_code: str) -> dict:

    today = datetime.today()
    start = (today - timedelta(days=365)).strftime("%Y-%m-%d")
    end   = today.strftime("%Y-%m-%d")

    try:
        df = fdr.DataReader(stock_code, start, end)
        if df.empty:
            return _empty()

        latest = df.iloc[-1]
        close  = int(latest["Close"])

        # 시가총액: KRX 상장 종목 정보에서 조회
        listing = fdr.StockListing("KRX")
        row = listing[listing["Code"] == stock_code]
        if not row.empty:
            market_cap = int(row.iloc[0].get("Marcap", 0))  
        else:
            market_cap = None

        return {
            "close":      close,
            "market_cap": market_cap,
            "high_52w":   int(df["High"].max()),
            "low_52w":    int(df["Low"].min()),
            "listed":     True,
        }

    except Exception:
        return _empty()


def _empty() -> dict:
    return {
        "close":      None,
        "market_cap": None,
        "high_52w":   None,
        "low_52w":    None,
        "listed":     False,
    }