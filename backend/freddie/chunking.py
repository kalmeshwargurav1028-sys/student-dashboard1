"""Freddie chunking — split long text into RAG-ready pieces."""
from __future__ import annotations

import re

from .config import MAX_CHUNK_CHARS


def chunk_text(text, source, role_scope='all', meta=None):
    """Split text into overlapping-safe sentence-aware chunks."""
    text = re.sub(r'\s+', ' ', (text or '')).strip()
    if not text:
        return []
    if len(text) <= MAX_CHUNK_CHARS:
        parts = [text]
    else:
        parts = []
        start = 0
        while start < len(text):
            end = min(start + MAX_CHUNK_CHARS, len(text))
            if end < len(text):
                cut = text.rfind('. ', start, end)
                if cut > start + 200:
                    end = cut + 1
            parts.append(text[start:end].strip())
            start = end
    out = []
    for i, p in enumerate(parts):
        if not p:
            continue
        out.append({
            'text': p,
            'source': source,
            'role_scope': role_scope,
            'meta': meta or {},
            'chunk_index': i,
        })
    return out
