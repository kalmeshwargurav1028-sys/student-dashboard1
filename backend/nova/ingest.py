"""Nova data ingestion — pull records from the app MongoDB into text chunks."""
from __future__ import annotations

from .chunking import chunk_text


def ingest_from_mongo(db, role='all', user_id=None):
    """
    Read live portal collections from MongoDB and return unembedded chunks.
    Collections used: school_policies, announcements, attendance, grades,
    students, assignments.
    """
    chunks = []

    # School policies
    try:
        for p in db.school_policies.find({}).limit(40):
            title = p.get('title') or 'Policy'
            body = p.get('body') or p.get('content') or ''
            chunks.extend(chunk_text(
                f'School policy: {title}. {body}',
                source='school_policies',
                role_scope='all',
                meta={'title': title},
            ))
    except Exception as e:
        print(f'[Nova:ingest] policies: {e}')

    # Announcements
    try:
        for a in db.announcements.find({}).sort('date_sent', -1).limit(30):
            title = a.get('title') or 'Announcement'
            body = a.get('body') or a.get('message') or ''
            chunks.extend(chunk_text(
                f'Announcement: {title}. {body}',
                source='announcements',
                role_scope='all',
                meta={'title': title},
            ))
    except Exception as e:
        print(f'[Nova:ingest] announcements: {e}')

    # Attendance
    try:
        if role == 'student' and user_id:
            student = db.students.find_one({'id': user_id}) or db.students.find_one({'_id': user_id}) or {}
            sid = student.get('id') or user_id
            records = list(db.attendance.find({'student_id': sid}).limit(200))
            present = sum(1 for r in records if str(r.get('status', '')).lower() in ('present', 'p'))
            absent = sum(1 for r in records if str(r.get('status', '')).lower() in ('absent', 'a'))
            late = sum(1 for r in records if str(r.get('status', '')).lower() in ('late', 'l'))
            chunks.extend(chunk_text(
                f'Student attendance for {student.get("name") or sid}: '
                f'{present} present, {absent} absent, {late} late out of {len(records)} marked days.',
                source='attendance',
                role_scope='student',
                meta={'student_id': sid},
            ))
        else:
            rows = list(db.attendance.aggregate([
                {'$group': {'_id': {'$toLower': '$status'}, 'count': {'$sum': 1}}},
            ]))
            parts = [f'{r["_id"] or "unknown"}={r["count"]}' for r in rows]
            chunks.extend(chunk_text(
                'School attendance totals by status: ' + (', '.join(parts) if parts else 'no records yet') + '.',
                source='attendance',
                role_scope='staff',
                meta={},
            ))
    except Exception as e:
        print(f'[Nova:ingest] attendance: {e}')

    # Grades / performance
    try:
        if role == 'student' and user_id:
            grades = list(db.grades.find({'student_id': user_id}).limit(100))
            if not grades:
                grades = list(db.grades.find({'student_id': str(user_id)}).limit(100))
            by_subj = {}
            for g in grades:
                subj = g.get('subject') or 'General'
                try:
                    by_subj.setdefault(subj, []).append(float(g.get('score')))
                except (TypeError, ValueError):
                    continue
            lines = [
                f'{subj} average {sum(vals) / len(vals):.1f} from {len(vals)} scores'
                for subj, vals in by_subj.items()
            ]
            chunks.extend(chunk_text(
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
                chunks.extend(chunk_text(
                    f'School performance snapshot: {len(students)} students sampled, '
                    f'average performance {avg:.1f}.',
                    source='students',
                    role_scope='staff',
                    meta={'count': len(students)},
                ))
    except Exception as e:
        print(f'[Nova:ingest] grades: {e}')

    # Assignments
    try:
        n = db.assignments.count_documents({})
        chunks.extend(chunk_text(
            f'There are {n} assignments recorded in the portal.',
            source='assignments',
            role_scope='all',
            meta={'count': n},
        ))
    except Exception as e:
        print(f'[Nova:ingest] assignments: {e}')

    return chunks


# Backwards-compatible alias
build_corpus = ingest_from_mongo
