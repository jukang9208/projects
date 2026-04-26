from transformers import pipeline

_pipeline = None
SENTIMENT_MODEL = "snunlp/KR-FinBert-SC"

LABEL_KO = {
    "positive": "긍정",
    "negative": "부정",
    "neutral":  "중립",
}

_EMPTY = {
    "label":          "중립",
    "positive_ratio": 0.0,
    "negative_ratio": 0.0,
    "neutral_ratio":  0.0,
    "articles":       [],
}


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = pipeline(
            "text-classification",
            model=SENTIMENT_MODEL,
            tokenizer=SENTIMENT_MODEL,
            device="cpu",
            truncation=True,
            max_length=256,
        )
    return _pipeline


def analyze_sentiment(articles: list[dict]) -> dict:

    if not articles:
        return _EMPTY

    pipe = _get_pipeline()

    # 제목 + 설명 합쳐서 분석 (최대 512자)
    texts = [
        f"{a['title']} {a['description']}"[:512]
        for a in articles
    ]
    results = pipe(texts)

    counts = {"positive": 0, "negative": 0, "neutral": 0}
    analyzed = []

    for article, result in zip(articles, results):
        raw = result["label"].lower()
        counts[raw] = counts.get(raw, 0) + 1
        analyzed.append({
            "title":     article["title"],
            "link":      article["link"],
            "pub_date":  article["pub_date"],
            "sentiment": LABEL_KO.get(raw, raw),
            "score":     round(result["score"], 4),
        })

    total   = len(articles)
    pos_r   = round(counts["positive"] / total, 3)
    neg_r   = round(counts["negative"] / total, 3)
    neu_r   = round(counts["neutral"]  / total, 3)
    dominant = max(counts, key=counts.get)

    return {
        "label":          LABEL_KO.get(dominant, dominant),
        "positive_ratio": pos_r,
        "negative_ratio": neg_r,
        "neutral_ratio":  neu_r,
        "articles":       analyzed,
    }