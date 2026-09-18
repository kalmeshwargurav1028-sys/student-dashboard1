"""Freddie shared config — Mongo collection + model names."""

EMBED_MODEL = 'text-embedding-004'
CHAT_MODEL = 'gemini-2.5-flash'
CHUNK_COLLECTION = 'freddie_chunks'  # MongoDB vector + text store
MAX_CHUNK_CHARS = 900
TOP_K = 6
