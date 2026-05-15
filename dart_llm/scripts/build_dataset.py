import os
import csv
import sys
import time
import json
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.config import settings
import google.generativeai as genai

genai.configure(api_key=settings.GEMINI_API_KEY)
_model = genai.GenerativeModel("gemini-2.0-flash")

# 카테고리별 Q&A 유형 (다양성 확보)
QA_TEMPLATES = {
    "사업보고서": [
        "이 사업보고서에서 회사의 주요 사업 내용을 요약해줘.",
        "이 공시에서 언급된 회사의 재무 현황을 설명해줘.",
        "이 사업보고서의 핵심 리스크 요인은 무엇인가?",
    ],
    "감사보고서": [
        "이 감사보고서의 감사 의견을 요약해줘.",
        "감사 과정에서 발견된 주요 사항은 무엇인가?",
        "이 공시에서 감사인이 강조한 핵심 감사사항을 설명해줘.",
    ],
    "유상증자": [
        "이 유상증자 공시의 목적과 규모를 설명해줘.",
        "이 공시에서 유상증자로 조달된 자금은 어떻게 사용될 예정인가?",
        "유상증자 발행 조건(발행가액, 주식 수 등)을 정리해줘.",
    ],
    "자기주식": [
        "이 자기주식 취득 공시의 목적과 규모를 설명해줘.",
        "자기주식 취득 기간과 방법을 정리해줘.",
        "이 공시에서 자기주식 취득이 주주에게 미치는 영향은?",
    ],
    "전환사채": [
        "이 전환사채 발행 공시의 주요 조건을 요약해줘.",
        "전환사채의 전환가액과 전환 기간을 설명해줘.",
        "이 전환사채 발행의 목적과 자금 사용 계획을 정리해줘.",
    ],
    "합병·분할": [
        "이 합병·분할 공시의 목적과 구조를 설명해줘.",
        "합병 비율과 일정을 정리해줘.",
        "이 공시에서 합병·분할이 주주에게 미치는 영향은?",
    ],
}


def generate_qa(text: str, label: str, question: str) -> dict | None:
    
    prompt = f"""다음은 DART에 공시된 '{label}' 문서입니다.

[공시 본문]
{text[:3000]}

[질문]
{question}

위 공시 본문을 바탕으로 질문에 대해 핵심만 간결하게 한국어로 답변해주세요.
공시에 없는 내용은 추측하지 말고, 본문 기반으로만 답변하세요."""

    try:
        resp = _model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=512,
                temperature=0.3,
            ),
        )
        answer = resp.text.strip()
        if len(answer) < 20:
            return None
        return {
            "instruction": question,
            "input": text[:2000],
            "output": answer,
            "label": label,
        }
    except Exception as e:
        print(f"  Gemini 오류: {e}")
        return None


def load_dart_classifier_data() -> list:
    
    base = PROJECT_ROOT.parent / "dart_classifier" / "data"
    rows = []
    for fname in ["dart_corpus_v35.csv", "dart_corpus_text.csv"]:
        fpath = base / fname
        if not fpath.exists():
            continue
        with open(fpath, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("text") and len(row["text"]) > 200:
                    rows.append(row)
    # 중복 제거
    seen = set()
    unique = []
    for r in rows:
        if r["rcept_no"] not in seen:
            seen.add(r["rcept_no"])
            unique.append(r)
    print(f"  dart_classifier 데이터: {len(unique)}건")
    return unique


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["dart_classifier", "raw"], default="dart_classifier")
    parser.add_argument("--per_doc", type=int, default=2, help="문서당 Q&A 생성 수")
    parser.add_argument("--max_docs", type=int, default=500)
    args = parser.parse_args()

    out_path = PROJECT_ROOT / settings.DATASET_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 데이터 로드
    if args.source == "dart_classifier":
        rows = load_dart_classifier_data()
    else:
        rows = []
        raw_dir = PROJECT_ROOT / settings.RAW_DATA_DIR
        for fpath in raw_dir.glob("dart_*.csv"):
            with open(fpath, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                rows.extend(list(reader))
        print(f"  raw 데이터: {len(rows)}건")

    rows = rows[:args.max_docs]

    # 기존 결과 확인 (중복 방지)
    existing_keys = set()
    if out_path.exists():
        with open(out_path, encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line)
                    existing_keys.add(d.get("_rcept_no", "") + d.get("instruction", ""))
                except Exception:
                    pass
        print(f"  기존 데이터셋: {len(existing_keys)}건 스킵")

    total = 0
    with open(out_path, "a", encoding="utf-8") as f:
        for i, row in enumerate(rows):
            label = row.get("label", "")
            text = row.get("text", "")
            rcept_no = row.get("rcept_no", "")

            questions = QA_TEMPLATES.get(label, [])[:args.per_doc]

            for q in questions:
                key = rcept_no + q
                if key in existing_keys:
                    continue

                print(f"  [{i+1}/{len(rows)}] {label} | {row.get('corp_name', '')} | {q[:30]}...")
                result = generate_qa(text, label, q)
                if result:
                    result["_rcept_no"] = rcept_no
                    f.write(json.dumps(result, ensure_ascii=False) + "\n")
                    f.flush()
                    total += 1
                time.sleep(0.5)

    print(f"\n완료: {total}건 생성 → {out_path}")


if __name__ == "__main__":
    main()
