"""Nova RAG — retrieve from Mongo vectors + answer with Gemini + chart payload."""
from __future__ import annotations

from .config import CHAT_MODEL, TOP_K
from .embed import embed_texts
from .pipeline import ingest_and_index
from .table_tools import pick_table_tools
from .vector_store import cosine, count_chunks, load_candidates


def retrieve(db, client, query, role='all', user_id=None, top_k=TOP_K):
    """RAG retrieve against Mongo `nova_chunks` with keyword boost."""
    scopes = ['all']
    if role == 'student':
        scopes.append('student')
    else:
        scopes.extend(['staff', 'admin'])

    q_vecs = embed_texts(client, [query]) if client else [[]]
    q_vec = q_vecs[0] if q_vecs else []
    q_lower = (query or '').lower()

    scored = []
    for doc in load_candidates(db, scopes):
        emb = doc.get('embedding') or []
        score = cosine(q_vec, emb) if q_vec and emb else 0.0
        text = (doc.get('text') or '').lower()
        if q_lower and any(w in text for w in q_lower.split() if len(w) > 3):
            score += 0.08
        scored.append((score, doc))
    scored.sort(key=lambda x: x[0], reverse=True)

    hits = []
    for score, doc in scored[:top_k]:
        hits.append({
            'text': doc.get('text'),
            'source': doc.get('source'),
            'score': round(float(score), 4),
            'meta': doc.get('meta') or {},
        })
    return hits


def answer_with_nova(db, client, question, role='all', user_id=None):
    """Full Nova turn: RAG retrieve + table tools + LLM + Chart.js payload."""
    question = (question or '').strip()
    if not question:
        return {'ok': False, 'error': 'Ask Nova a question first.'}

    if count_chunks(db) == 0 and client:
        ingest_and_index(db, client, role=role, user_id=user_id)

    hits = retrieve(db, client, question, role=role, user_id=user_id)
    tools = pick_table_tools(question, db, role=role, user_id=user_id)

    context = '\n'.join(f"- ({h['source']}) {h['text']}" for h in hits) or 'No retrieved context yet.'
    tool_blob = '\n'.join(
        f"- {t['title']}: labels={t['labels']}, values={t['values']}" for t in tools
    )

    answer = ''
    if client:
        prompt = (
            'You are Nova, the Indus Portal analytics assistant. '
            'Answer clearly for a school LMS. Use only the context and tool numbers. '
            'If data is missing, say what is missing. Keep answer under 120 words.\n\n'
            f'Role: {role}\nQuestion: {question}\n\n'
            f'Retrieved context:\n{context}\n\n'
            f'Table tool results:\n{tool_blob}\n\n'
            'Answer:'
        )
        try:
            resp = client.models.generate_content(model=CHAT_MODEL, contents=prompt)
            answer = (getattr(resp, 'text', None) or '').strip()
        except Exception as e:
            print(f'[Nova:rag] generate failed: {e}')
            answer = ''

    if not answer:
        bits = [f"Here's what Nova found for: {question}"]
        for t in tools:
            if t['labels'] and t['values'] and t['labels'][0] != 'No data':
                pairs = ', '.join(f"{l}={v}" for l, v in zip(t['labels'], t['values']))
                bits.append(f"{t['title']}: {pairs}.")
        if hits:
            bits.append(hits[0]['text'])
        answer = ' '.join(bits)

    primary = tools[0]
    return {
        'ok': True,
        'answer': answer,
        'sources': [{'source': h['source'], 'score': h['score']} for h in hits],
        'chart': {
            'type': primary.get('chart_type') or 'bar',
            'title': primary.get('title') or 'Nova chart',
            'labels': primary.get('labels') or [],
            'values': primary.get('values') or [],
        },
        'charts': [
            {
                'type': t.get('chart_type') or 'bar',
                'title': t.get('title') or 'Chart',
                'labels': t.get('labels') or [],
                'values': t.get('values') or [],
            }
            for t in tools
        ],
        'tools_used': [t.get('tool') for t in tools],
    }
