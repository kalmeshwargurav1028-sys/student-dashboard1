"""Freddie embeddings — Gemini text-embedding-004 via google-genai Client."""
from __future__ import annotations

from .config import EMBED_MODEL


def embed_texts(client, texts):
    """Return list of embedding vectors for texts. Empty vector on failure."""
    if not client or not texts:
        return []
    vectors = []
    for text in texts:
        try:
            resp = client.models.embed_content(model=EMBED_MODEL, contents=text)
            emb = None
            if hasattr(resp, 'embeddings') and resp.embeddings:
                emb = resp.embeddings[0]
            elif hasattr(resp, 'embedding'):
                emb = resp.embedding
            values = getattr(emb, 'values', None) if emb is not None else None
            if values is None and isinstance(emb, dict):
                values = emb.get('values')
            if values is None and isinstance(resp, dict):
                values = (resp.get('embedding') or {}).get('values')
            vectors.append(list(values) if values else [])
        except Exception as e:
            print(f'[Freddie:embed] failed: {e}')
            vectors.append([])
    return vectors
