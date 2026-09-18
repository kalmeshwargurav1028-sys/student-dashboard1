"""
Freddie package — split pipeline modules:

  ingest.py        → read Mongo portal data
  chunking.py      → split text
  embed.py         → Gemini embeddings
  vector_store.py  → Mongo `freddie_chunks`
  table_tools.py   → live aggregates for charts
  rag.py           → retrieve + answer
  pipeline.py      → ingest → embed → store
"""
from .config import CHUNK_COLLECTION, EMBED_MODEL, CHAT_MODEL
from .ingest import ingest_from_mongo, build_corpus
from .chunking import chunk_text
from .embed import embed_texts
from .vector_store import cosine, count_chunks, save_chunks, clear_scopes
from .table_tools import pick_table_tools, tool_attendance_breakdown, tool_subject_averages, tool_assignment_load
from .pipeline import ingest_and_index
from .rag import retrieve, answer_with_freddie

__all__ = [
    'CHUNK_COLLECTION',
    'EMBED_MODEL',
    'CHAT_MODEL',
    'ingest_from_mongo',
    'build_corpus',
    'chunk_text',
    'embed_texts',
    'cosine',
    'count_chunks',
    'save_chunks',
    'clear_scopes',
    'pick_table_tools',
    'tool_attendance_breakdown',
    'tool_subject_averages',
    'tool_assignment_load',
    'ingest_and_index',
    'retrieve',
    'answer_with_freddie',
]
