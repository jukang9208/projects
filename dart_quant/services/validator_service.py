import re
from typing import Any
from pydantic import BaseModel, Field


class ReportContextData(BaseModel):
    company_name: str
    dart_text: str
    news_text: str
    price_data: str
    financial_data: str
    macro_data: dict[str, Any] = Field(default_factory=dict)

    def _extract_macro_text(self) -> str:
        """
        macro_data(dict)를 LLM/검증용 문자열로 평탄화합니다.
        """
        if not self.macro_data:
            return ""

        title = self.macro_data.get("title", "글로벌 매크로 지표")
        indicators = self.macro_data.get("indicators", [])

        if isinstance(indicators, list):
            indicator_text = "\n".join(str(item) for item in indicators)
        else:
            indicator_text = str(indicators)

        return f"[[{title}]]\n{indicator_text}".strip()

    def get_integrity_report(self):
        score = 100
        reasons = []

        # 존재 여부 검사
        if "[HARD_DATA_ERROR]" in self.price_data or "N/A" in self.price_data:
            reasons.append("핵심 정량 지표 누락")
            score -= 40

        # 수치 이상치(Outlier) 상식 검증
        try:
            per_matches = re.findall(r"PER:\s*([-\d\.]+)", self.price_data)
            pbr_matches = re.findall(r"PBR:\s*([-\d\.]+)", self.price_data)

            for p_str in per_matches:
                per_val = float(p_str)

                if per_val > 50:
                    reasons.append(f"치명적 이상치 감지 (PER {per_val}x)")
                    score -= 40
                elif per_val < 0:
                    reasons.append(f"적자 상태 감지 (PER 음수: {per_val}x)")
                    score -= 20

            for p_str in pbr_matches:
                pbr_val = float(p_str)

                if pbr_val > 10:
                    reasons.append(f"치명적 이상치 감지 (PBR {pbr_val}x)")
                    score -= 30
                elif pbr_val < 0:
                    reasons.append(f"비정상 수치 감지 (PBR 음수: {pbr_val}x)")
                    score -= 20

        except Exception:
            reasons.append("정량 지표 상식 검증 실패")
            score -= 20

        # 비정량 데이터 확인
        if len(self.news_text.strip()) < 100:
            reasons.append("뉴스 컨텍스트 부족")
            score -= 20

        macro_text = self._extract_macro_text()
        if len(macro_text.strip()) < 20:
            reasons.append("거시경제 컨텍스트 부족")
            score -= 10

        score = max(0, score)

        if score >= 80:
            status = "신뢰 가능 (수치 검증 통과)"
        elif score >= 50:
            status = "주의 요망 (데이터 오염 가능성)"
        else:
            status = "위험 (수치 신뢰도 붕괴, 판단 보류 권장)"

        return score, reasons, status

    def to_llm_context(self) -> dict[str, str]:
        """
        LLM 프롬프트에 넣기 좋은 문자열 컨텍스트로 변환합니다.
        """
        return {
            "company_name": self.company_name,
            "dart_text": self.dart_text,
            "news_text": self.news_text,
            "price_data": self.price_data,
            "financial_data": self.financial_data,
            "macro_data": self._extract_macro_text(),
        }


def validate_and_build_context(company, dart, news, price, fin, macro):
    valid_data = ReportContextData(
        company_name=company,
        dart_text=dart,
        news_text=news,
        price_data=price,
        financial_data=fin,
        macro_data=macro,
    )
    score, reasons, status = valid_data.get_integrity_report()

    return valid_data, {
        "score": score,
        "reasons": reasons,
        "status": status,
    }