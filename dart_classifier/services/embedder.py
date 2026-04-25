from google import genai
from google.genai import types
from core.config import GEMINI_API_KEY, GEMINI_EMBEDDING_MODEL

_client = genai.Client(api_key=GEMINI_API_KEY)


def embed_text(text: str) -> list[float]:
    response = _client.models.embed_content(
        model=GEMINI_EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(
            task_type="retrieval_document",
            output_dimensionality=768,
        ),
    )
    return response.embeddings[0].values


def embed_query(text: str) -> list[float]:
    response = _client.models.embed_content(
        model=GEMINI_EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(
            task_type="retrieval_query",
            output_dimensionality=768,
        ),
    )
    return response.embeddings[0].values


def embed_batch(texts: list[str]) -> list[list[float]]:
    return [embed_text(t) for t in texts]
