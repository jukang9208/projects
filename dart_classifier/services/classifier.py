import torch
from transformers import pipeline
from core.config import CLASSIFIER_MODEL_DIR

_classifier = None

def get_classifier():
    global _classifier
    if _classifier is None:
        _classifier = pipeline(
            "text-classification",
            model=CLASSIFIER_MODEL_DIR,
            tokenizer=CLASSIFIER_MODEL_DIR,
            device="cpu",
            truncation=True,
            max_length=512,  # 수정 : 256 -> 512
        )
    return _classifier

def classify_text(text: str) -> dict:
    classifier = get_classifier()
    result = classifier(text)[0]  # text[:512] 슬라이싱 제거
    return {"label": result["label"], "score": round(result["score"], 4)}
