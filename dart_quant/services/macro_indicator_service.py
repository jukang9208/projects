import logging
from typing import Any

import yfinance as yf

logger = logging.getLogger(__name__)


def get_general_macro_indicators(period: str = "1mo") -> dict[str, Any]:
    """거시경제 핵심 지표를 수집하고 시장 환경을 분석합니다."""
    logger.info("거시경제 데이터 수집 및 시장 레짐(Market Regime) 분석 중...")

    tickers = {
        "KOSPI 지수 (국내 시장 심리)": "^KS11",
        "S&P 500 (글로벌 시장 심리)": "^GSPC",
        "원/달러 환율 (수출입 기업 영향)": "KRW=X",
        "WTI 원유 (원자재 및 인플레 지표)": "CL=F",
    }

    results: list[str] = []

    for name, ticker in tickers.items():
        try:
            tk = yf.Ticker(ticker)
            hist = tk.history(period=period)

            if hist.empty:
                logger.warning(f"{name} 지표 데이터가 비어 있습니다.")
                continue

            current = float(hist["Close"].iloc[-1])
            base = float(hist["Close"].iloc[0])

            if base == 0:
                logger.warning(f"{name} 기준값이 0이라 변동률 계산을 건너뜁니다.")
                continue

            change = ((current - base) / base) * 100

            results.append(
                f"- {name}: 현재가 {current:,.2f} (1개월 변동률: {change:+.2f}%)"
            )

        except Exception as e:
            logger.warning(f"{name} 지표 수집 실패: {e}")

    return {
        "title": "글로벌 매크로 지표",
        "indicators": results,
    }