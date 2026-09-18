"""Nova MongoDB vector store — collection `nova_chunks`."""
from __future__ import annotations

import math
from datetime import datetime

from .config import CHUNK_COLLECTION


def _now():
    return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')


def cosine(a, b):
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def clear_scopes(db, role='all'):
    """Remove stale chunks for the role lane before re-index."""
    scopes = ['all']
    if role == 'student':
        scopes.append('student')
    else:
        scopes.append('staff')
    db[CHUNK_COLLECTION].delete_many({'role_scope': {'$in': scopes}})


def save_chunks(db, chunk_docs):
    """Insert embedded chunk docs into Mongo `nova_chunks`."""
    if not chunk_docs:
        return 0
    db[CHUNK_COLLECTION].insert_many(chunk_docs)
    return len(chunk_docs)


def count_chunks(db):
    return db[CHUNK_COLLECTION].count_documents({})


def load_candidates(db, scopes, limit=400):
    """Load candidate docs from Mongo for similarity search."""
    return list(db[CHUNK_COLLECTION].find({'role_scope': {'$in': scopes}}).limit(limit))


def stamp_chunk(chunk, embedding, role=None, user_id=None):
    """Attach embedding + metadata for Mongo storage."""
    return {
        **chunk,
        'embedding': embedding or [],
        'updated_at': _now(),
        'ingested_for_role': role,
        'ingested_for_user': str(user_id) if user_id else None,
    }
