import requests
from django.conf import settings


class OllamaError(RuntimeError):
    """Raised when the local Ollama service cannot satisfy an AI request."""


def embed_text(text: str) -> list[float]:
    payload = {
        "model": settings.OLLAMA_EMBEDDING_MODEL,
        "input": text,
    }
    try:
        response = requests.post(
            f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/embed",
            json=payload,
            timeout=settings.OLLAMA_EMBEDDING_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise OllamaError(f"Ollama embedding request failed: {exc}") from exc

    embeddings = data.get("embeddings")
    if not embeddings or not isinstance(embeddings, list) or not embeddings[0]:
        raise OllamaError("Ollama returned no embedding vector.")

    vector = embeddings[0]
    if len(vector) != settings.EMBEDDING_DIMENSIONS:
        raise OllamaError(
            f"Embedding dimension mismatch: expected {settings.EMBEDDING_DIMENSIONS}, got {len(vector)}."
        )
    return vector


def generate_text(prompt: str) -> str:
    payload = {
        "model": settings.OLLAMA_GENERATION_MODEL,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.1,
        },
    }
    try:
        response = requests.post(
            f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate",
            json=payload,
            timeout=settings.OLLAMA_GENERATION_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise OllamaError(f"Ollama generation request failed: {exc}") from exc

    text = data.get("response")
    if not text or not isinstance(text, str):
        raise OllamaError("Ollama returned no generated response.")
    return text.strip()
