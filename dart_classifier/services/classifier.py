import torch
from transformers import pipeline
from core.config import CLASSIFIER_MODEL_DIR

_classifier = None

def get_classifier():
    global _classifier
    if _classifier is None:
        print(f"DEBUG: torch name in get_classifier: {'torch' in globals()}")
        _classifier = pipeline(
            "text-classification",
            model=CLASSIFIER_MODEL_DIR,
            tokenizer=CLASSIFIER_MODEL_DIR,
            device="cpu",
            truncation=True,
            max_length=256,
        )
    return _classifier

def classify_text(text: str) -> dict:

    classifier = get_classifier()
    result = classifier(text[:512])[0]  
    return {"label": result["label"], "score": round(result["score"], 4)}
