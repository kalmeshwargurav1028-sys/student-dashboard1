"""Freddie pipeline — orchestrate ingest → chunk → embed → Mongo store."""
from __future__ import annotations

from .embed import embed_texts
from .ingest import ingest_from_mongo
from .vector_store import clear_scopes, save_chunks, stamp_chunk


def ingest_and_index(db, client, role='all', user_id=None, replace=True):
    """
    Full index pipeline against the app MongoDB:
      1) ingest live collections
      2) chunks already produced by ingest/chunking
      3) embed with Gemini
      4) write to Mongo collection `freddie_chunks`
    """
    corpus = ingest_from_mongo(db, role=role, user_id=user_id)
    if not corpus:
        return {'ok': False, 'chunks': 0, 'error': 'No data to ingest from MongoDB'}

    if replace:
        clear_scopes(db, role=role)

    texts = [c['text'] for c in corpus]
    vectors = embed_texts(client, texts)
    docs = [
        stamp_chunk(c, vec, role=role, user_id=user_id)
        for c, vec in zip(corpus, vectors)
    ]
    saved = save_chunks(db, docs)
    return {
        'ok': True,
        'chunks': saved,
        'embedded': sum(1 for d in docs if d.get('embedding')),
        'collection': 'freddie_chunks',
    }
