"""
Freddie — RAG chart assistant for Indus Portal.

Pipeline: ingest → chunk → embed → Mongo vector store → retrieve (RAG)
         + table tools for live metrics → Gemini → chart JSON.
"""
from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any

# Embedding model used with google-genai Client
EMBED_MODEL = 'text-embedding-004'
CHAT_MODEL = 'gemini-2.5-flash'
CHUNK_COLLECTION = 'freddie_chunks'
MAX_CHUNK_CHARS = 900
TOP_K = 6


def _now():
    return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')


def _cosine(a, b):
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _chunk_text(text, source, role_scope='all', meta=None):
    text = re.sub(r'\s+', ' ', (text or '')).strip()
    if not text:
        return []
    parts = []
    if len(text) <= MAX_CHUNK_CHARS:
        parts = [text]
    else:
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


def embed_texts(client, texts):
    """Return list of embedding vectors for texts. Empty list on failure."""
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
            print(f'[Freddie] embed failed: {e}')
            vectors.append([])
    return vectors


def build_corpus(db, role='all', user_id=None):
    """Ingest portal data into text chunks (no embeddings yet)."""
    chunks = []

    # School policies
    try:
        for p in db.school_policies.find({}).limit(40):
            title = p.get('title') or 'Policy'
            body = p.get('body') or p.get('content') or ''
            chunks.extend(_chunk_text(
                f'School policy: {title}. {body}',
                source='school_policies',
                role_scope='all',
                meta={'title': title},
            ))
    except Exception as e:
        print(f'[Freddie] policies ingest: {e}')

    # Announcements
    try:
        for a in db.announcements.find({}).sort('date_sent', -1).limit(30):
            title = a.get('title') or 'Announcement'
            body = a.get('body') or a.get('message') or ''
            chunks.extend(_chunk_text(
                f'Announcement: {title}. {body}',
                source='announcements',
                role_scope='all',
                meta={'title': title},
            ))
    except Exception as e:
        print(f'[Freddie] announcements ingest: {e}')

    # Attendance summary (school-wide for staff/admin; student-scoped for students)
    try:
        if role == 'student' and user_id:
            student = db.students.find_one({'id': user_id}) or db.students.find_one({'_id': user_id}) or {}
            sid = student.get('id') or user_id
            records = list(db.attendance.find({'student_id': sid}).limit(200))
            present = sum(1 for r in records if str(r.get('status', '')).lower() in ('present', 'p'))
            absent = sum(1 for r in records if str(r.get('status', '')).lower() in ('absent', 'a'))
            late = sum(1 for r in records if str(r.get('status', '')).lower() in ('late', 'l'))
            chunks.extend(_chunk_text(
                f'Student attendance for {student.get("name") or sid}: '
                f'{present} present, {absent} absent, {late} late out of {len(records)} marked days.',
                source='attendance',
                role_scope='student',
                meta={'student_id': sid},
            ))
        else:
            pipeline = [
                {'$group': {'_id': {'$toLower': '$status'}, 'count': {'$sum': 1}}},
            ]
            rows = list(db.attendance.aggregate(pipeline))
            parts = [f'{r["_id"] or "unknown"}={r["count"]}' for r in rows]
            chunks.extend(_chunk_text(
                'School attendance totals by status: ' + (', '.join(parts) if parts else 'no records yet') + '.',
                source='attendance',
                role_scope='staff',
                meta={},
            ))
    except Exception as e:
        print(f'[Freddie] attendance ingest: {e}')

    # Subject / grade performance
    try:
        if role == 'student' and user_id:
            grades = list(db.grades.find({'student_id': user_id}).limit(100))
            if not grades:
                grades = list(db.grades.find({'student_id': str(user_id)}).limit(100))
            by_subj = {}
            for g in grades:
                subj = g.get('subject') or 'General'
                score = g.get('score')
                try:
                    score = float(score)
                except (TypeError, ValueError):
                    continue
                by_subj.setdefault(subj, []).append(score)
            lines = []
            for subj, vals in by_subj.items():
                avg = sum(vals) / len(vals)
                lines.append(f'{subj} average {avg:.1f} from {len(vals)} scores')
            chunks.extend(_chunk_text(
                'Student subject performance: ' + ('; '.join(lines) if lines else 'no graded scores yet') + '.',
                source='grades',
                role_scope='student',
                meta={},
            ))
        else:
            students = list(db.students.find({}, {'name': 1, 'performance': 1, 'student_class': 1, 'id': 1}).limit(200))
            if students:
                perfs = []
                for s in students:
                    try:
                        perfs.append(float(s.get('performance')))
                    except (TypeError, ValueError):
                        pass
                avg = (sum(perfs) / len(perfs)) if perfs else 0
                chunks.extend(_chunk_text(
                    f'School performance snapshot: {len(students)} students sampled, '
                    f'average performance {avg:.1f}.',
                    source='students',
                    role_scope='staff',
                    meta={'count': len(students)},
                ))
    except Exception as e:
        print(f'[Freddie] grades ingest: {e}')

    # Assignments overview
    try:
        n = db.assignments.count_documents({})
        chunks.extend(_chunk_text(
            f'There are {n} assignments recorded in the portal.',
            source='assignments',
            role_scope='all',
            meta={'count': n},
        ))
    except Exception as e:
        print(f'[Freddie] assignments ingest: {e}')

    return chunks


def ingest_and_index(db, client, role='all', user_id=None, replace=True):
    """Chunk portal data, embed, and store in freddie_chunks."""
    corpus = build_corpus(db, role=role, user_id=user_id)
    if not corpus:
        return {'ok': False, 'chunks': 0, 'error': 'No data to ingest'}

    if replace:
        # Keep global chunks; refresh role-scoped lanes for this ingest
        scopes = ['all']
        if role == 'student':
            scopes.append('student')
        else:
            scopes.append('staff')
        db[CHUNK_COLLECTION].delete_many({'role_scope': {'$in': scopes}})

    texts = [c['text'] for c in corpus]
    vectors = embed_texts(client, texts)
    docs = []
    for c, vec in zip(corpus, vectors):
        if not vec:
            # Still store text for keyword fallback
            vec = []
        docs.append({
            **c,
            'embedding': vec,
            'updated_at': _now(),
            'ingested_for_role': role,
            'ingested_for_user': str(user_id) if user_id else None,
        })
    if docs:
        db[CHUNK_COLLECTION].insert_many(docs)
    return {'ok': True, 'chunks': len(docs), 'embedded': sum(1 for d in docs if d.get('embedding'))}


def retrieve(db, client, query, role='all', user_id=None, top_k=TOP_K):
    """RAG retrieve: vector search with keyword fallback."""
    scopes = ['all']
    if role == 'student':
        scopes.append('student')
    else:
        scopes.extend(['staff', 'admin'])

    q_vecs = embed_texts(client, [query]) if client else [[]]
    q_vec = q_vecs[0] if q_vecs else []

    cursor = db[CHUNK_COLLECTION].find({'role_scope': {'$in': scopes}}).limit(400)
    scored = []
    q_lower = (query or '').lower()
    for doc in cursor:
        emb = doc.get('embedding') or []
        score = _cosine(q_vec, emb) if q_vec and emb else 0.0
        # light keyword boost
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


# ---------------------------------------------------------------------------
# Table tools — structured metrics for charts
# ---------------------------------------------------------------------------

def tool_attendance_breakdown(db, role='all', user_id=None):
    labels, values = [], []
    try:
        match = {}
        if role == 'student' and user_id:
            match['student_id'] = user_id
            # also try string id variants via student record
            st = db.students.find_one({'id': user_id}) or {}
            if st.get('id'):
                match = {'student_id': {'$in': [user_id, st.get('id'), str(st.get('id'))]}}
        pipeline = []
        if match:
            pipeline.append({'$match': match})
        pipeline.append({'$group': {'_id': {'$toLower': '$status'}, 'count': {'$sum': 1}}})
        rows = list(db.attendance.aggregate(pipeline))
        order = ['present', 'absent', 'late', 'excused']
        mapped = {(r['_id'] or 'unknown'): r['count'] for r in rows}
        for key in order:
            if key in mapped:
                labels.append(key.title())
                values.append(mapped[key])
        for key, val in mapped.items():
            if key not in order:
                labels.append((key or 'Other').title())
                values.append(val)
    except Exception as e:
        print(f'[Freddie] attendance tool: {e}')
    return {
        'tool': 'attendance_breakdown',
        'title': 'Attendance breakdown',
        'chart_type': 'doughnut',
        'labels': labels or ['No data'],
        'values': values or [0],
    }


def tool_subject_averages(db, role='all', user_id=None):
    labels, values = [], []
    try:
        match = {}
        if role == 'student' and user_id:
            match['student_id'] = {'$in': [user_id, str(user_id)]}
        pipeline = []
        if match:
            pipeline.append({'$match': match})
        pipeline.extend([
            {'$addFields': {'score_num': {'$convert': {'input': '$score', 'to': 'double', 'onError': None, 'onNull': None}}}},
            {'$match': {'score_num': {'$ne': None}}},
            {'$group': {'_id': '$subject', 'avg': {'$avg': '$score_num'}, 'n': {'$sum': 1}}},
            {'$sort': {'avg': -1}},
            {'$limit': 12},
        ])
        rows = list(db.grades.aggregate(pipeline))
        for r in rows:
            labels.append(r['_id'] or 'General')
            values.append(round(float(r['avg']), 1))
        # Fallback: student.performance by class for staff
        if not labels and role != 'student':
            by_class = {}
            for s in db.students.find({}, {'student_class': 1, 'performance': 1}).limit(300):
                cls = s.get('student_class') or '—'
                try:
                    by_class.setdefault(cls, []).append(float(s.get('performance')))
                except (TypeError, ValueError):
                    pass
            for cls, vals in sorted(by_class.items()):
                if vals:
                    labels.append(f'Grade {cls}')
                    values.append(round(sum(vals) / len(vals), 1))
    except Exception as e:
        print(f'[Freddie] subject tool: {e}')
    return {
        'tool': 'subject_averages',
        'title': 'Subject / class averages',
        'chart_type': 'bar',
        'labels': labels or ['No data'],
        'values': values or [0],
    }


def tool_assignment_load(db, role='all', user_id=None):
    labels, values = [], []
    try:
        pipeline = [
            {'$group': {'_id': {'$ifNull': ['$subject', 'General']}, 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}},
            {'$limit': 10},
        ]
        rows = list(db.assignments.aggregate(pipeline))
        for r in rows:
            labels.append(r['_id'] or 'General')
            values.append(int(r['count']))
    except Exception as e:
        print(f'[Freddie] assignment tool: {e}')
    return {
        'tool': 'assignment_load',
        'title': 'Assignments by subject',
        'chart_type': 'bar',
        'labels': labels or ['No data'],
        'values': values or [0],
    }


def pick_table_tools(question, db, role='all', user_id=None):
    q = (question or '').lower()
    tools = []
    if any(w in q for w in ('attend', 'absent', 'present', 'late', 'presence')):
        tools.append(tool_attendance_breakdown(db, role, user_id))
    if any(w in q for w in ('grade', 'score', 'mark', 'subject', 'performance', 'average', 'pg')):
        tools.append(tool_subject_averages(db, role, user_id))
    if any(w in q for w in ('assign', 'homework', 'task', 'workload')):
        tools.append(tool_assignment_load(db, role, user_id))
    # Default chart if nothing matched but user asked for chart/trend/compare
    if not tools and any(w in q for w in ('chart', 'graph', 'trend', 'compare', 'show', 'how')):
        tools.append(tool_attendance_breakdown(db, role, user_id))
        tools.append(tool_subject_averages(db, role, user_id))
    if not tools:
        tools.append(tool_attendance_breakdown(db, role, user_id))
    return tools[:2]


def answer_with_freddie(db, client, question, role='all', user_id=None):
    """Full Freddie turn: retrieve + table tools + LLM summary + chart payload."""
    question = (question or '').strip()
    if not question:
        return {'ok': False, 'error': 'Ask Freddie a question first.'}

    # Ensure we have some indexed chunks
    count = db[CHUNK_COLLECTION].count_documents({})
    if count == 0 and client:
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
            'You are Freddie, the Indus Portal analytics assistant. '
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
            print(f'[Freddie] generate failed: {e}')
            answer = ''

    if not answer:
        # Deterministic fallback without LLM
        bits = [f"Here's what Freddie found for: {question}"]
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
            'title': primary.get('title') or 'Freddie chart',
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
