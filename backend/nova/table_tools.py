"""Nova table tools — live Mongo aggregates for Chart.js."""
from __future__ import annotations


def tool_attendance_breakdown(db, role='all', user_id=None):
    labels, values = [], []
    try:
        match = {}
        if role == 'student' and user_id:
            st = db.students.find_one({'id': user_id}) or {}
            ids = [user_id, str(user_id)]
            if st.get('id'):
                ids.append(st.get('id'))
                ids.append(str(st.get('id')))
            match = {'student_id': {'$in': list(dict.fromkeys(ids))}}
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
        print(f'[Nova:tools] attendance: {e}')
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
        print(f'[Nova:tools] subjects: {e}')
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
        rows = list(db.assignments.aggregate([
            {'$group': {'_id': {'$ifNull': ['$subject', 'General']}, 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}},
            {'$limit': 10},
        ]))
        for r in rows:
            labels.append(r['_id'] or 'General')
            values.append(int(r['count']))
    except Exception as e:
        print(f'[Nova:tools] assignments: {e}')
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
    if not tools and any(w in q for w in ('chart', 'graph', 'trend', 'compare', 'show', 'how')):
        tools.append(tool_attendance_breakdown(db, role, user_id))
        tools.append(tool_subject_averages(db, role, user_id))
    if not tools:
        tools.append(tool_attendance_breakdown(db, role, user_id))
    return tools[:2]
