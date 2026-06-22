import json
import logging
from typing import List, Tuple
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
logger = logging.getLogger(__name__)


def _build_documents(text_corpus: str) -> List[Document]:
    """
    text_corpus 예시:
    [[공시]]
    공시 본문...

    [[뉴스]]
    뉴스 본문...
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
    )

    docs: List[Document] = []

    for raw_section in text_corpus.split("[["):
        section = raw_section.strip()
        if not section or "]]" not in section:
            continue

        header, body = section.split("]]", 1)
        header = header.strip()
        body = body.strip()

        if not body:
            continue

        source = "DART" if "공시" in header else "NEWS"

        chunks = splitter.split_text(body)
        for i, chunk in enumerate(chunks):
            docs.append(
                Document(
                    page_content=chunk,
                    metadata={
                        "source": source,
                        "order": i,
                    },
                )
            )

    return docs


def _extract_original_section(text_corpus: str, section_name: str) -> str:
    """
    원문 text_corpus에서 [[공시]] / [[뉴스]] 섹션을 직접 추출
    """
    for raw_section in text_corpus.split("[["):
        section = raw_section.strip()
        if not section or "]]" not in section:
            continue

        header, body = section.split("]]", 1)
        if section_name in header.strip():
            return body.strip()

    return ""


def _collect_source_context(context_docs: List[Document], source_name: str, limit: int = 3) -> str:
    """
    검색된 문서 중 source별로 필요한 수만 추려 결합
    """
    chunks = []
    for doc in context_docs:
        if doc.metadata.get("source") == source_name:
            text = doc.page_content.strip()
            if text:
                chunks.append(text)

    if not chunks:
        return ""

    return "\n---\n".join(chunks[:limit])


def _safe_json_loads(text: str) -> dict:
    """
    모델 응답에서 코드블록 제거 후 JSON 파싱
    """
    cleaned = text.replace("```json", "").replace("```", "").strip()
    return json.loads(cleaned)


def _build_quant_detail_text(quant_score_data: dict) -> str:
    return (
        f"- 가치 점수: {quant_score_data.get('value_score', 0)}/25\n"
        f"- 수익성 점수: {quant_score_data.get('profit_score', 0)}/25\n"
        f"- 성장성 점수: {quant_score_data.get('growth_score', 0)}/25\n"
        f"- 안정성 점수: {quant_score_data.get('stability_score', 0)}/25\n"
        f"- 리스크 점수: {quant_score_data.get('risk_score', 0)}/25\n"
        f"- 총점: {quant_score_data.get('total_score', 0)}/100\n"
        f"- 정량 투자 의견: {quant_score_data.get('investment_opinion', '관망')}"
    )


# 파라미터에 analysis_mode 추가 (기본값: 종합 분석)
def generate_report(
    text_corpus: str,
    fixed_metrics: str,
    company: str,
    google_api_key: str,
    user_focus: str,
    today: str,
    confidence_score: dict,
    quant_score_data: dict,
    analysis_mode: str = "종합 분석", 
) -> Tuple[str, list]:
    """
    하이브리드 RAG 기반 리포트 생성
    반환값:
        (json_string, used_docs)
    """
    docs = _build_documents(text_corpus)
    used_docs: List[Document] = []

    news_text = ""
    dart_text = ""

    if docs:
        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001",
            google_api_key=google_api_key,
        )

        vector_store = Chroma.from_documents(docs, embeddings)
        bm25 = BM25Retriever.from_documents(docs)

        retriever = EnsembleRetriever(
            retrievers=[
                vector_store.as_retriever(search_kwargs={"k": 6}),
                bm25,
            ],
            weights=[0.4, 0.6],
        )

        query = f"{company} {user_focus}".strip()
        used_docs = retriever.invoke(query)

        news_text = _collect_source_context(used_docs, "NEWS", limit=3)
        dart_text = _collect_source_context(used_docs, "DART", limit=3)

    # 검색 실패 시 원문 fallback
    if not news_text:
        news_text = _extract_original_section(text_corpus, "뉴스") or "뉴스 데이터가 없습니다."

    if not dart_text:
        dart_text = _extract_original_section(text_corpus, "공시") or "공시 데이터가 없습니다."

    quant_score_text = str(quant_score_data.get("total_score", 0))
    quant_summary_list = quant_score_data.get("analysis_summary", [])
    quant_summary_text = (
        " / ".join(quant_summary_list)
        if quant_summary_list
        else "정량 판단 근거 부족"
    )
    quant_detail_text = _build_quant_detail_text(quant_score_data)

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.1,
        google_api_key=google_api_key,
    )

    # 프롬프트 템플릿에 분석 관점(analysis_mode) 지시어 추가
    template = """
당신은 시스템 퀀트 점수를 절대적으로 신뢰하는 금융 분석가입니다.
제공된 데이터만 바탕으로 분석을 수행하세요.
근거 없는 추측은 금지합니다.

[수집된 데이터]
- 현재 날짜: {today}
- 대상 기업: {company}
- 사용자 집중 키워드: {user_focus}
- 분석 관점(렌즈): {analysis_mode}
- 데이터 신뢰도 점수: {score}
- 데이터 신뢰도 상태: {status}

[정량 점수 요약]
- 총점: {quant_score_text}점
- 정량 요약: {quant_summary_text}

[정량 점수 세부]
{quant_detail_text}

[정량/매크로 원문]
{fixed_metrics}

[뉴스 요약]
{news_text}

[공시(DART) 요약]
{dart_text}

[작성 가이드라인]
1. 당신의 역할은 설정된 '분석 관점({analysis_mode})'에 철저히 맞춰서 리포트를 작성하는 것입니다. 
   (예: '성장성 중심'이면 미래 동력 및 투자 위주로, '리스크 중심'이면 하방 위험과 재무 건전성 위주로 편향성 있게 작성하세요.)
2. '추천_의견'은 총점({quant_score_text}점)을 최우선으로 반영하되 다음 중 하나만 선택:
   - 85점 이상: 적극매수
   - 70점 이상: 매수
   - 55점 이상: 보유
   - 40점 이상: 중립
   - 40점 미만: 관망
3. '재무_평가'는 반드시 정량지표 + 공시를 함께 참고해 작성하세요.
4. '최종_의견'은 뉴스와 공시를 함께 반영하되, 정량 점수와 충돌하지 않게 작성하세요.
5. '핵심_요약'은 짧고 명확한 문장 2~4개로 작성하세요.
6. 문장 끝에는 가능한 한 [뉴스], [공시], [정량] 중 하나의 근거 표기를 붙이세요.
7. 뉴스_태그는 실제 뉴스 요약에 근거해 2~4개 생성하세요.
8. JSON 외 다른 텍스트는 절대 출력하지 마세요.

반드시 아래 JSON 구조로만 응답하세요:
{{
  "추천_의견": "보유",
  "재무_평가": "정량지표와 공시를 반영한 재무 상태 요약 [정량][공시]",
  "최종_의견": "시장 흐름과 투자 전략을 반영한 종합 의견 [뉴스][공시]",
  "신뢰도": 0.95,
  "핵심_요약": [
    "핵심 포인트 1 [정량]",
    "핵심 포인트 2 [뉴스]"
  ],
  "뉴스_태그": [
    {{
      "title": "주요 뉴스 제목 요약",
      "date": "{today}",
      "summary": "뉴스 내용 핵심 요약",
      "tags": ["태그1", "태그2"]
    }}
  ]
}}
"""

    prompt = ChatPromptTemplate.from_template(template)
    chain = prompt | llm

    # invoke 호출 시 analysis_mode 파라미터 전달
    response = chain.invoke(
        {
            "today": today,
            "company": company,
            "user_focus": user_focus,
            "analysis_mode": analysis_mode, 
            "news_text": news_text,
            "dart_text": dart_text,
            "fixed_metrics": fixed_metrics,
            "score": confidence_score.get("score", 100),
            "status": confidence_score.get("status", "정상"),
            "quant_score_text": quant_score_text,
            "quant_summary_text": quant_summary_text,
            "quant_detail_text": quant_detail_text,
        }
    )

    response_text = response.content.strip()

    # 1차 JSON 검증
    try:
        parsed = _safe_json_loads(response_text)

        # 정량 의견이 누락되거나 비정상일 때 보정
        if not isinstance(parsed, dict):
            raise ValueError("모델 응답이 dict 형식이 아님")

        parsed.setdefault(
            "추천_의견",
            quant_score_data.get("investment_opinion", "관망"),
        )
        parsed.setdefault("신뢰도", round(confidence_score.get("score", 100) / 100, 2))
        parsed.setdefault("핵심_요약", quant_score_data.get("analysis_summary", [])[:3])
        parsed.setdefault("뉴스_태그", [])

        return json.dumps(parsed, ensure_ascii=False), used_docs

    except Exception:
        logger.warning("1차 JSON 파싱 실패. 강제 교정 프롬프트 재시도.")

    # 2차 교정 시도
    repair_template = """
아래 응답을 JSON 스키마에 맞게 다시 변환하세요.
설명 없이 JSON만 출력하세요.

[원본 응답]
{raw_response}

[정량 기준]
- 총점: {quant_score_text}
- 정량 추천 의견: {investment_opinion}
- 정량 요약: {quant_summary_text}

[반드시 맞춰야 할 스키마]
{{
  "추천_의견": "{investment_opinion}",
  "재무_평가": "문자열",
  "최종_의견": "문자열",
  "신뢰도": 0.95,
  "핵심_요약": ["문자열", "문자열"],
  "뉴스_태그": [
    {{
      "title": "문자열",
      "date": "{today}",
      "summary": "문자열",
      "tags": ["문자열", "문자열"]
    }}
  ]
}}
"""
    repair_prompt = ChatPromptTemplate.from_template(repair_template)
    repair_chain = repair_prompt | llm

    repaired = repair_chain.invoke(
        {
            "raw_response": response_text,
            "quant_score_text": quant_score_text,
            "investment_opinion": quant_score_data.get("investment_opinion", "관망"),
            "quant_summary_text": quant_summary_text,
            "today": today,
        }
    )

    repaired_text = repaired.content.strip()

    try:
        parsed = _safe_json_loads(repaired_text)

        if not isinstance(parsed, dict):
            raise ValueError("교정 응답이 dict 형식이 아님")

        parsed.setdefault(
            "추천_의견",
            quant_score_data.get("investment_opinion", "관망"),
        )
        parsed.setdefault("신뢰도", round(confidence_score.get("score", 100) / 100, 2))
        parsed.setdefault("핵심_요약", quant_score_data.get("analysis_summary", [])[:3])
        parsed.setdefault("뉴스_태그", [])

        return json.dumps(parsed, ensure_ascii=False), used_docs

    except Exception as e:
        logger.error("최종 JSON 파싱 실패", exc_info=True)
        fallback = {
            "추천_의견": quant_score_data.get("investment_opinion", "관망"),
            "재무_평가": f"정량 점수 {quant_score_text}점을 기준으로 재무 상태를 요약하기에 충분한 구조이나, 모델 응답 변환에 실패했습니다. [정량]",
            "최종_의견": f"모델 응답 JSON 변환 실패로 정량 의견 '{quant_score_data.get('investment_opinion', '관망')}'을 기본값으로 사용합니다. 세부 오류: {str(e)} [정량]",
            "신뢰도": round(confidence_score.get("score", 100) / 100, 2),
            "핵심_요약": quant_score_data.get("analysis_summary", [])[:3] or ["정량 요약 생성 실패"],
            "뉴스_태그": [],
        }
        return json.dumps(fallback, ensure_ascii=False), used_docs