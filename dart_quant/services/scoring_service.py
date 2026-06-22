import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _clamp(value: float, min_value: float = 0, max_value: float = 100) -> int:
    return int(max(min_value, min(max_value, round(value))))


def _safe_yoy(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None or previous is None or previous == 0:
        return None
    try:
        return ((current - previous) / abs(previous)) * 100
    except Exception:
        return None


def _score_value(per: Optional[float], pbr: Optional[float]) -> tuple[int, list[str]]:
    score = 0
    reasons = []

    # PER 최대 15점
    if per is None or per <= 0:
        reasons.append("PER 산출 불가")
    elif per <= 8:
        score += 15
        reasons.append(f"PER 매우 낮음 ({per:.2f})")
    elif per <= 12:
        score += 13
        reasons.append(f"PER 매력적 ({per:.2f})")
    elif per <= 18:
        score += 10
        reasons.append(f"PER 무난 ({per:.2f})")
    elif per <= 25:
        score += 6
        reasons.append(f"PER 다소 높음 ({per:.2f})")
    else:
        score += 2
        reasons.append(f"PER 부담 ({per:.2f})")

    # PBR 최대 10점
    if pbr is None or pbr <= 0:
        reasons.append("PBR 산출 불가")
    elif pbr <= 1:
        score += 10
        reasons.append(f"PBR 저평가 구간 ({pbr:.2f})")
    elif pbr <= 1.5:
        score += 8
        reasons.append(f"PBR 양호 ({pbr:.2f})")
    elif pbr <= 2.5:
        score += 6
        reasons.append(f"PBR 무난 ({pbr:.2f})")
    elif pbr <= 3.5:
        score += 3
        reasons.append(f"PBR 다소 높음 ({pbr:.2f})")
    else:
        score += 1
        reasons.append(f"PBR 부담 ({pbr:.2f})")

    return min(score, 25), reasons


def _score_profitability(
    roe: Optional[float],
    operating_income: Optional[float],
    net_income: Optional[float]
) -> tuple[int, list[str]]:
    score = 0
    reasons = []

    # ROE 최대 15점
    if roe is None:
        reasons.append("ROE 산출 불가")
    elif roe >= 20:
        score += 15
        reasons.append(f"ROE 매우 우수 ({roe:.1f}%)")
    elif roe >= 15:
        score += 13
        reasons.append(f"ROE 우수 ({roe:.1f}%)")
    elif roe >= 10:
        score += 10
        reasons.append(f"ROE 양호 ({roe:.1f}%)")
    elif roe >= 5:
        score += 6
        reasons.append(f"ROE 보통 ({roe:.1f}%)")
    elif roe > 0:
        score += 3
        reasons.append(f"ROE 낮음 ({roe:.1f}%)")
    else:
        reasons.append("ROE 부진")

    # 영업이익 최대 5점
    if operating_income is None:
        reasons.append("영업이익 데이터 부족")
    elif operating_income > 0:
        score += 5
        reasons.append("영업이익 흑자")
    else:
        reasons.append("영업이익 적자")

    # 순이익 최대 5점
    if net_income is None:
        reasons.append("순이익 데이터 부족")
    elif net_income > 0:
        score += 5
        reasons.append("순이익 흑자")
    else:
        reasons.append("순이익 적자")

    return min(score, 25), reasons


def _score_growth(
    revenue: Optional[float],
    prev_revenue: Optional[float],
    net_income: Optional[float],
    prev_net_income: Optional[float],
    operating_income: Optional[float],
    prev_operating_income: Optional[float],
) -> tuple[int, list[str], dict]:
    score = 0
    reasons = []

    rev_yoy = _safe_yoy(revenue, prev_revenue)
    ni_yoy = _safe_yoy(net_income, prev_net_income)
    op_yoy = _safe_yoy(operating_income, prev_operating_income)

    # 매출 성장 최대 8점
    if rev_yoy is None:
        reasons.append("매출 성장 데이터 부족")
    elif rev_yoy >= 20:
        score += 8
        reasons.append(f"매출 고성장 (+{rev_yoy:.1f}%)")
    elif rev_yoy >= 10:
        score += 6
        reasons.append(f"매출 성장 (+{rev_yoy:.1f}%)")
    elif rev_yoy >= 3:
        score += 4
        reasons.append(f"매출 완만 성장 (+{rev_yoy:.1f}%)")
    elif rev_yoy >= 0:
        score += 2
        reasons.append(f"매출 보합 (+{rev_yoy:.1f}%)")
    elif rev_yoy >= -5:
        score += 1
        reasons.append(f"매출 소폭 감소 ({rev_yoy:.1f}%)")
    else:
        reasons.append(f"매출 감소 ({rev_yoy:.1f}%)")

    # 영업이익 성장 최대 9점
    if prev_operating_income is None or operating_income is None:
        reasons.append("영업이익 성장 데이터 부족")
    else:
        if prev_operating_income < 0 < operating_income:
            score += 9
            reasons.append("영업이익 흑자전환")
        elif prev_operating_income > 0 > operating_income:
            reasons.append("영업이익 적자전환")
        elif op_yoy is None:
            reasons.append("영업이익 성장률 산출 불가")
        elif op_yoy >= 30:
            score += 9
            reasons.append(f"영업이익 고성장 (+{op_yoy:.1f}%)")
        elif op_yoy >= 15:
            score += 7
            reasons.append(f"영업이익 성장 (+{op_yoy:.1f}%)")
        elif op_yoy >= 5:
            score += 5
            reasons.append(f"영업이익 완만 성장 (+{op_yoy:.1f}%)")
        elif op_yoy >= 0:
            score += 3
            reasons.append(f"영업이익 보합 (+{op_yoy:.1f}%)")
        elif op_yoy >= -10:
            score += 1
            reasons.append(f"영업이익 소폭 감소 ({op_yoy:.1f}%)")
        else:
            reasons.append(f"영업이익 감소 ({op_yoy:.1f}%)")

    # 순이익 성장 최대 8점
    if prev_net_income is None or net_income is None:
        reasons.append("순이익 성장 데이터 부족")
    else:
        if prev_net_income < 0 < net_income:
            score += 8
            reasons.append("순이익 흑자전환")
        elif prev_net_income > 0 > net_income:
            reasons.append("순이익 적자전환")
        elif ni_yoy is None:
            reasons.append("순이익 성장률 산출 불가")
        elif ni_yoy >= 30:
            score += 8
            reasons.append(f"순이익 고성장 (+{ni_yoy:.1f}%)")
        elif ni_yoy >= 15:
            score += 6
            reasons.append(f"순이익 성장 (+{ni_yoy:.1f}%)")
        elif ni_yoy >= 5:
            score += 4
            reasons.append(f"순이익 완만 성장 (+{ni_yoy:.1f}%)")
        elif ni_yoy >= 0:
            score += 2
            reasons.append(f"순이익 보합 (+{ni_yoy:.1f}%)")
        elif ni_yoy >= -10:
            score += 1
            reasons.append(f"순이익 소폭 감소 ({ni_yoy:.1f}%)")
        else:
            reasons.append(f"순이익 감소 ({ni_yoy:.1f}%)")

    metrics = {
        "revenue_yoy": round(rev_yoy, 2) if rev_yoy is not None else None,
        "operating_income_yoy": round(op_yoy, 2) if op_yoy is not None else None,
        "net_income_yoy": round(ni_yoy, 2) if ni_yoy is not None else None,
    }

    return min(score, 25), reasons, metrics


def _score_stability(
    total_equity: Optional[float],
    pbr: Optional[float],
    roe: Optional[float],
    operating_income: Optional[float],
    net_income: Optional[float],
) -> tuple[int, list[str]]:
    score = 0
    reasons = []

    # 1. 자본 상태 최대 10점
    if total_equity is None:
        reasons.append("자본총계 데이터 부족")
    elif total_equity <= 0:
        reasons.append("자본잠식 또는 자본총계 비정상")
    else:
        score += 10
        reasons.append("자본총계 양호")

    # 2. PBR 기반 과열/안정성 최대 5점
    if pbr is None or pbr <= 0:
        reasons.append("PBR 기반 안정성 판단 제한")
    elif pbr <= 1:
        score += 5
        reasons.append(f"PBR 안정 구간 ({pbr:.2f})")
    elif pbr <= 2:
        score += 4
        reasons.append(f"PBR 무난 ({pbr:.2f})")
    elif pbr <= 3:
        score += 3
        reasons.append(f"PBR 다소 높음 ({pbr:.2f})")
    elif pbr <= 5:
        score += 1
        reasons.append(f"PBR 부담 구간 ({pbr:.2f})")
    else:
        reasons.append(f"PBR 과열 구간 ({pbr:.2f})")

    # 3. 수익 지속성 최대 5점
    if operating_income is not None and operating_income > 0:
        score += 3
        reasons.append("영업이익 지속 가능성 양호")
    if net_income is not None and net_income > 0:
        score += 2
        reasons.append("순이익 지속 가능성 양호")

    # 4. ROE 안정성 최대 5점
    if roe is None:
        reasons.append("ROE 기반 안정성 판단 제한")
    elif roe >= 15:
        score += 5
        reasons.append(f"ROE 안정성 우수 ({roe:.1f}%)")
    elif roe >= 10:
        score += 4
        reasons.append(f"ROE 안정성 양호 ({roe:.1f}%)")
    elif roe >= 5:
        score += 2
        reasons.append(f"ROE 안정성 보통 ({roe:.1f}%)")
    elif roe > 0:
        score += 1
        reasons.append(f"ROE 안정성 낮음 ({roe:.1f}%)")
    else:
        reasons.append("ROE 안정성 부진")

    return min(score, 25), reasons


def _make_investment_opinion(total_score: int) -> str:
    if total_score >= 85:
        return "적극매수"
    if total_score >= 70:
        return "매수"
    if total_score >= 55:
        return "보유"
    if total_score >= 40:
        return "중립"
    return "관망"


def calculate_quant_score(financial_data: dict) -> dict:
    logger.info("가점형 퀀트 스코어링 엔진 가동 중...")

    try:
        per = financial_data.get("per")
        pbr = financial_data.get("pbr")
        roe = financial_data.get("roe")

        revenue = financial_data.get("revenue")
        prev_revenue = financial_data.get("prev_revenue")

        operating_income = financial_data.get("operating_income")
        prev_operating_income = financial_data.get("prev_operating_income")

        net_income = financial_data.get("net_income")
        prev_net_income = financial_data.get("prev_net_income")

        total_equity = financial_data.get("total_equity")

        value_score, value_reasons = _score_value(per, pbr)
        profit_score, profit_reasons = _score_profitability(
            roe,
            operating_income,
            net_income,
        )
        growth_score, growth_reasons, growth_metrics = _score_growth(
            revenue,
            prev_revenue,
            net_income,
            prev_net_income,
            operating_income,
            prev_operating_income,
        )
        stability_score, stability_reasons = _score_stability(
            total_equity,
            pbr,
            roe,
            operating_income,
            net_income,
        )

        total_score = _clamp(
            value_score + profit_score + growth_score + stability_score,
            0,
            100,
        )

        analysis_summary = []
        analysis_summary.extend(value_reasons[:2])
        analysis_summary.extend(profit_reasons[:2])
        analysis_summary.extend(growth_reasons[:2])
        analysis_summary.extend(stability_reasons[:2])

        return {
            "value_score": value_score,          # 0~25
            "profit_score": profit_score,        # 0~25
            "growth_score": growth_score,        # 0~25
            "stability_score": stability_score,  # 0~25
            "risk_score": 25 - stability_score,  # UI 호환용
            "total_score": total_score,          # 0~100
            "investment_opinion": _make_investment_opinion(total_score),
            "analysis_summary": analysis_summary[:6],
            "raw_metrics": {
                "per": round(per, 2) if per is not None else None,
                "pbr": round(pbr, 2) if pbr is not None else None,
                "roe": round(roe, 2) if roe is not None else None,
                **growth_metrics,
            },
        }

    except Exception as e:
        logger.error(f"스코어링 엔진 에러: {e}", exc_info=True)
        return {
            "value_score": 0,
            "profit_score": 0,
            "growth_score": 0,
            "stability_score": 0,
            "risk_score": 25,
            "total_score": 0,
            "investment_opinion": "관망",
            "analysis_summary": ["점수 계산 실패"],
            "raw_metrics": {},
        }