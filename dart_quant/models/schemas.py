from pydantic import BaseModel

class AnalyzeRequest(BaseModel):
    company_name: str
    focus_keyword: str = ""
    analysis_mode: str = "종합 분석"
    force_refresh: bool = False

class CompareRequest(BaseModel):
    company_a: str
    company_b: str
    focus_keyword: str = ""      
    compare_focus: str = "종합 평가 비교"
    force_refresh: bool = False