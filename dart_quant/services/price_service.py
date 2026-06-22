import logging
import math
import re
from datetime import datetime

import FinanceDataReader as fdr

logger = logging.getLogger(__name__)

def _is_valid_number(value) -> bool:
    """None, NaN, bool 제외한 정상 숫자인지 확인"""
    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return not math.isnan(value)
    return False

def _to_float(value):
    """DART/FDR 값에서 숫자를 안전하게 float로 변환"""
    if value is None:
        return None

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            if math.isnan(value):
                return None
        except Exception:
            pass
        return float(value)

    text = str(value).strip()
    if text in ("", "-", "N/A", "None", "nan"):
        return None

    is_negative = text.startswith("(") and text.endswith(")")
    if is_negative:
        text = text[1:-1]

    text = text.replace(",", "").replace("원", "").strip()
    text = re.sub(r"[^0-9.\-]", "", text)

    if text in ("", "-", ".", "-."):
        return None

    try:
        number = float(text)
        return -number if is_negative else number
    except Exception:
        return None

def _safe_divide(numerator, denominator):
    """안전한 나눗셈"""
    if not _is_valid_number(numerator) or not _is_valid_number(denominator):
        return None
    if denominator == 0:
        return None
    try:
        return numerator / denominator
    except Exception:
        return None

def _format_number(value, fmt=".2f", default="N/A") -> str:
    """숫자 포맷 안전 처리"""
    if not _is_valid_number(value):
        return default
    try:
        return format(value, fmt)
    except Exception:
        return default

def _format_currency(value, default="N/A") -> str:
    """원화/정수 표시용"""
    if not _is_valid_number(value):
        return default
    try:
        return f"{value:,.0f}"
    except Exception:
        return default

def _format_amount_krw(value, default="N/A") -> str:
    """큰 금액을 억/조 단위로 보기 좋게 표시"""
    if not _is_valid_number(value):
        return default

    abs_value = abs(value)
    sign = "-" if value < 0 else ""

    try:
        if abs_value >= 1_0000_0000_0000:
            return f"{sign}{abs_value / 1_0000_0000_0000:.2f}조원"
        if abs_value >= 1_0000_0000:
            return f"{sign}{abs_value / 1_0000_0000:.2f}억원"
        return f"{sign}{abs_value:,.0f}원"
    except Exception:
        return default

def _extract_account_values(df, account_patterns):
    """[수정됨] DART에서 당기(현재) 및 전기(과거) 재무 수치를 동시 추출"""
    if df is None or df.empty:
        return None, None

    mask = df["account_nm"].astype(str).str.contains(
        account_patterns, case=False, na=False, regex=True,
    )
    matched = df[mask]

    if matched.empty:
        return None, None

    # 매칭된 계정과목에서 당기(thstrm)와 전기(frmtrm) 데이터를 각각 추출
    for _, row in matched.iterrows():
        cur_val = _to_float(row.get("thstrm_amount")) if "thstrm_amount" in matched.columns else None
        prev_val = _to_float(row.get("frmtrm_amount")) if "frmtrm_amount" in matched.columns else None
        
        # 하나라도 유효한 값이 있으면 반환
        if _is_valid_number(cur_val) or _is_valid_number(prev_val):
            return cur_val, prev_val

    return None, None

def _get_stock_count(ticker_symbol: str):
    """FDR에서 상장주식수를 안전하게 조회"""
    try:
        df_krx = fdr.StockListing("KRX")
        matched = df_krx[df_krx["Code"].astype(str).str.zfill(6) == str(ticker_symbol).zfill(6)]
        if not matched.empty and "Stocks" in matched.columns:
            stock_count = _to_float(matched["Stocks"].iloc[0])
            if _is_valid_number(stock_count) and stock_count > 0:
                return stock_count
    except Exception as e:
        logger.warning(f"FDR 상장주식수 조회 실패: {e}")
    return None

def _get_latest_finstate(ticker_symbol: str, dart_client):
    """최근 2개 사업연도 중 사용 가능한 연결/별도 재무제표 반환"""
    current_year = datetime.now().year
    target_years = [str(current_year - 1), str(current_year - 2)]

    for year in target_years:
        try:
            df = dart_client.finstate(ticker_symbol, bsns_year=year, reprt_code="11011")
            if df is not None and not df.empty:
                logger.info(f"DART 재무제표({year}년) 조회 성공")
                return df, year
        except Exception as e:
            logger.warning(f"DART 재무제표({year}년) 조회 실패: {e}")

    return None, None

def _extract_financial_core(indicators):
    """[수정됨] 핵심 재무 항목(당기 및 전기) 추출"""
    if indicators is None or indicators.empty:
        return {
            "revenue": None, "prev_revenue": None,
            "operating_income": None, "prev_operating_income": None,
            "net_income": None, "prev_net_income": None,
            "total_equity": None, "prev_total_equity": None,
        }

    rev, prev_rev = _extract_account_values(indicators, r"^매출액$|^수익\(매출액\)$|^영업수익$|^매출총액$")
    op, prev_op = _extract_account_values(indicators, r"^영업이익$|^영업손익$|^영업이익\(손실\)$")
    ni, prev_ni = _extract_account_values(indicators, r"^당기순이익$|^연결당기순이익$|^당기순이익\(손실\)$|^반기순이익$|^분기순이익$")
    eq, prev_eq = _extract_account_values(indicators, r"^자본총계$|^연결자본총계$")

    return {
        "revenue": rev, "prev_revenue": prev_rev,
        "operating_income": op, "prev_operating_income": prev_op,
        "net_income": ni, "prev_net_income": prev_ni,
        "total_equity": eq, "prev_total_equity": prev_eq,
    }

def get_price_and_indicators(ticker_symbol: str, dart_client) -> str:
    """FDR(주가/주식수) + OpenDART 기반으로 지표 산출 (문자열 반환)"""
    logger.info("주가 및 재무 데이터 수집 중...")
    try:
        df = fdr.DataReader(ticker_symbol)
        if df is None or df.empty or "Close" not in df.columns:
            return "주가 데이터를 찾을 수 없습니다."

        current_price = _to_float(df.iloc[-1]["Close"])
        if not _is_valid_number(current_price):
            return "현재가 데이터를 해석할 수 없습니다."

        stock_count = _get_stock_count(ticker_symbol)
        indicators, used_year = _get_latest_finstate(ticker_symbol, dart_client)
        core = _extract_financial_core(indicators)

        net_income = core["net_income"]
        total_equity = core["total_equity"]

        eps = _safe_divide(net_income, stock_count)
        bps = _safe_divide(total_equity, stock_count)

        per = _safe_divide(current_price, eps) if _is_valid_number(eps) and eps > 0 else None
        pbr = _safe_divide(current_price, bps) if _is_valid_number(bps) and bps > 0 else None

        current_price_str = _format_currency(current_price, default="N/A")
        eps_str = _format_currency(eps, default="N/A")
        bps_str = _format_currency(bps, default="N/A")
        per_str = _format_number(per, fmt=".2f", default="N/A (적자)")
        pbr_str = _format_number(pbr, fmt=".2f", default="N/A")
        year_str = used_year if used_year else "기준연도 미확인"

        return (
            f"현재가: {current_price_str}원\n"
            f"EPS: {eps_str}원 ({year_str})\n"
            f"BPS: {bps_str}원 ({year_str})\n"
            f"PER: {per_str}\n"
            f"PBR: {pbr_str}"
        )

    except Exception as e:
        logger.exception("데이터 수집 오류")
        return f"데이터 수집 실패: {e}"

def get_financials(ticker_symbol: str, dart_client) -> str:
    """DART 재무제표 기반 LLM 입력용 문자열 반환"""
    logger.info("상세 재무 데이터 수집 중...")
    try:
        indicators, used_year = _get_latest_finstate(ticker_symbol, dart_client)
        if indicators is None or indicators.empty:
            return "상세 재무 데이터를 불러오지 못했습니다."

        core = _extract_financial_core(indicators)
        year_str = used_year if used_year else "미확인"

        revenue_str = _format_amount_krw(core["revenue"])
        op_str = _format_amount_krw(core["operating_income"])
        ni_str = _format_amount_krw(core["net_income"])
        eq_str = _format_amount_krw(core["total_equity"])

        return (
            f"재무제표 기준연도: {year_str}\n"
            f"매출액: {revenue_str}\n"
            f"영업이익: {op_str}\n"
            f"당기순이익: {ni_str}\n"
            f"자본총계: {eq_str}"
        )
    except Exception as e:
        logger.exception("상세 재무 데이터 수집 오류")
        return f"상세 재무 데이터 수집 실패: {e}"

def get_financial_data_dict(ticker_symbol: str, dart_client) -> dict:
    """[수정됨] scoring_service에 넘겨줄 딕셔너리에 전기(Prev) 데이터 추가"""
    try:
        df = fdr.DataReader(ticker_symbol)
        current_price = _to_float(df.iloc[-1]["Close"]) if (df is not None and not df.empty and "Close" in df.columns) else None

        stock_count = _get_stock_count(ticker_symbol)
        indicators, used_year = _get_latest_finstate(ticker_symbol, dart_client)
        core = _extract_financial_core(indicators)

        net_income = core["net_income"]
        total_equity = core["total_equity"]

        eps = _safe_divide(net_income, stock_count)
        bps = _safe_divide(total_equity, stock_count)
        per = _safe_divide(current_price, eps) if _is_valid_number(eps) and eps > 0 else None
        pbr = _safe_divide(current_price, bps) if _is_valid_number(bps) and bps > 0 else None

        roe = _safe_divide(net_income, total_equity)
        roe_pct = roe * 100 if _is_valid_number(roe) else None

        return {
            "current_price": current_price,
            "revenue": core["revenue"],
            "prev_revenue": core["prev_revenue"],               # ✅ 전기 매출액 추가
            "operating_income": core["operating_income"],
            "prev_operating_income": core["prev_operating_income"], # ✅ 전기 영업이익 추가
            "net_income": core["net_income"],
            "prev_net_income": core["prev_net_income"],         # ✅ 전기 순이익 추가
            "total_equity": total_equity,
            "prev_total_equity": core["prev_total_equity"],     # ✅ 전기 자본총계 추가
            "stock_count": stock_count,
            "eps": eps,
            "bps": bps,
            "per": per,
            "pbr": pbr,
            "roe": roe_pct,
            "financial_year": used_year,
        }
    except Exception as e:
        logger.error(f"financial_data_dict 수집 오류: {e}")
        return {}