import logging
import re
import FinanceDataReader as fdr

logger = logging.getLogger(__name__)


def find_ticker(company_input: str):

    company_input = company_input.strip()
    logger.info(f"종목 검색 시작: '{company_input}'")

    # 6자리 숫자면 종목코드로 간주
    if re.fullmatch(r"\d{6}", company_input):
        ticker = company_input
        try:
            df_krx = fdr.StockListing("KRX").copy()
            matched = df_krx[df_krx["Code"].astype(str).str.zfill(6) == ticker]

            if not matched.empty:
                row = matched.iloc[0]
                return ticker, row["Name"]

            # 코드 자체는 유효할 수 있으니 이름을 못 찾더라도 ticker는 반환
            logger.warning(f"KRX 목록에서 코드 {ticker}의 종목명을 찾지 못했습니다.")
            return ticker, ticker

        except Exception as e:
            logger.warning(f"KRX 목록 조회 실패. 코드만 사용합니다: {e}")
            return ticker, ticker

    # 기업명 검색
    logger.info(f"FinanceDataReader로 '{company_input}' 이름 검색 중.")

    try:
        df_krx = fdr.StockListing("KRX").copy()
        df_krx["Name_clean"] = df_krx["Name"].astype(str).str.replace(" ", "", regex=False)
        query = company_input.replace(" ", "")

        exact = df_krx[df_krx["Name_clean"].str.lower() == query.lower()]
        match_df = exact if not exact.empty else df_krx[df_krx["Name_clean"].str.contains(query, case=False, na=False)]

        if "Market" in match_df.columns:
            match_df = match_df[match_df["Market"].isin(["KOSPI", "KOSDAQ"])]

        if match_df.empty:
            return None, None

        row = match_df.iloc[0]
        ticker = str(row["Code"]).zfill(6)
        return ticker, row["Name"]

    except Exception as e:
        logger.error(f"종목 검색 중 오류: {e}")
        return None, None