from fastapi import APIRouter, HTTPException
from services.financial import get_financial
from services.classifier import classify_text
from schemas.classify import AnalyzeRequest, AnalyzeResponse, ClassifyResult, FinancialData

router = APIRouter(prefix="/analyze", tags=["분석"])


def build_insight(label: str, score: float, f: FinancialData) -> str:

    def fmt(v: int | None) -> str:
        if v is None:
            return "정보없음"
        return f"{v / 1_0000_0000:,.1f}억원"

    corp = f.corp_name
    year = f.year
    dr   = f"{f.debt_ratio:.1f}%" if f.debt_ratio is not None else "정보없음"
    op   = f.operating_profit
    ni   = f.net_income

    if label == "유상증자":
        if op is not None and op < 0:
            reason = f"영업손실({fmt(op)}) 상태로, 재무 부담 완화를 위한 자금 조달로 판단됩니다."
        elif f.debt_ratio is not None and f.debt_ratio > 200:
            reason = f"부채비율({dr})이 높아 추가 차입보다 주식 발행을 선택한 것으로 보입니다."
        else:
            reason = f"영업이익 {fmt(op)} 상태에서 시설투자 또는 사업 확장을 위한 자금 조달로 보입니다."
        return (
            f"[{label} · 신뢰도 {score:.0%}] {corp} {year}년\n"
            f"매출액 {fmt(f.revenue)}, 영업이익 {fmt(op)}, 부채비율 {dr}\n"
            f"{reason}"
        )

    elif label == "사업보고서":
        trend = "흑자" if (ni is not None and ni > 0) else "적자"
        return (
            f"[{label} · 신뢰도 {score:.0%}] {corp} {year}년\n"
            f"매출액 {fmt(f.revenue)}, 영업이익 {fmt(op)}, 당기순이익 {fmt(ni)}\n"
            f"해당 연도 순이익 기준 {trend} 상태입니다."
        )

    elif label == "감사보고서":
        return (
            f"[{label} · 신뢰도 {score:.0%}] {corp} {year}년\n"
            f"자산총계 {fmt(f.total_assets)}, 부채총계 {fmt(f.total_liabilities)}, "
            f"자본총계 {fmt(f.total_equity)}, 부채비율 {dr}\n"
            f"재무 건전성 지표를 기반으로 감사보고서를 검토하세요."
        )

    elif label == "전환사채":
        if f.debt_ratio is not None and f.debt_ratio > 200:
            reason = f"부채비율({dr})이 높은 상황에서 전환사채 발행은 추가 재무 부담으로 작용할 수 있습니다."
        elif op is not None and op < 0:
            reason = f"영업손실({fmt(op)}) 상태에서 전환사채 발행은 향후 주주 가치 희석 리스크를 내포합니다."
        else:
            reason = "전환사채 발행을 통한 자금 조달로, 향후 주식 전환 시 주주 희석 가능성을 검토하세요."
        return (
            f"[{label} · 신뢰도 {score:.0%}] {corp} {year}년\n"
            f"매출액 {fmt(f.revenue)}, 영업이익 {fmt(op)}, 부채비율 {dr}\n"
            f"{reason}"
        )

    elif label == "자기주식":
        if ni is not None and ni > 0:
            reason = f"순이익({fmt(ni)}) 흑자 상태에서의 자기주식 취득은 주주환원 정책으로 해석할 수 있습니다."
        else:
            reason = "자기주식 취득·처분 내용을 재무 현황과 함께 검토하세요."
        return (
            f"[{label} · 신뢰도 {score:.0%}] {corp} {year}년\n"
            f"매출액 {fmt(f.revenue)}, 당기순이익 {fmt(ni)}, 자본총계 {fmt(f.total_equity)}\n"
            f"{reason}"
        )

    elif label == "합병·분할":
        return (
            f"[{label} · 신뢰도 {score:.0%}] {corp} {year}년\n"
            f"자산총계 {fmt(f.total_assets)}, 매출액 {fmt(f.revenue)}, 부채비율 {dr}\n"
            f"합병·분할은 기업 구조 변경을 수반하므로 거래 조건 및 합병비율을 공시 원문에서 확인하세요."
        )

    return f"[{label} · 신뢰도 {score:.0%}] {corp} {year}년 재무 데이터를 확인하세요."


@router.post("", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    """공시 본문 분류 + 기업 재무 데이터 통합 분석"""
    try:
        cls       = classify_text(req.text)
        fin_raw   = get_financial(req.corp_name, req.year)

        classify_result = ClassifyResult(label=cls["label"], score=cls["score"])
        financial = FinancialData(**fin_raw)
        insight   = build_insight(cls["label"], cls["score"], financial)

        return AnalyzeResponse(
            classify=classify_result,
            financial=financial,
            insight=insight,
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
