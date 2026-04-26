import FinanceDataReader as fdr
from datetime import datetime, timedelta

_krx_listing = None
_krx_listing_date: str | None = None

def _get_krx_listing():
    
    global _krx_listing, _krx_listing_date
    today = datetime.today().strftime("%Y-%m-%d")
    if _krx_listing is None or _krx_listing_date != today:
        _krx_listing = fdr.StockListing("KRX")
        _krx_listing_date = today
    return _krx_listing


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

        # 시가총액
        listing = _get_krx_listing()
        row = listing[listing["Code"] == stock_code]
        market_cap = int(row.iloc[0].get("Marcap", 0)) if not row.empty else None

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
