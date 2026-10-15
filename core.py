"""Recognition-independent grading and persistence."""
import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path


def integer(value):
    text = str(value).strip().replace('−', '-')
    if not text:
        return None
    if not re.fullmatch(r'[+-]?\d+', text):
        raise ValueError('Enter an integer or leave blank.')
    return int(text)


def division(number):
    number = number.strip().upper()
    if not re.fullmatch(r'[BC]\d+', number):
        raise ValueError('Team number must be B or C followed by digits, such as B12 or C004.')
    return 'Middle school' if number[0] == 'B' else 'High school'


def points(answer, key, awards=(5, 3, 1)):
    if answer is None or key is None:
        return 0
    difference = abs(answer - key)
    return awards[difference] if difference < 3 else 0


def assess(rows, keys, awards=(5, 3, 1)):
    results = []
    for row, key in zip(rows, keys, strict=True):
        try:
            answer = integer(row['Answer'])
            error = ''
        except ValueError as exc:
            answer, error = None, str(exc)
        results.append(dict(question=row['Question'], answer=answer, key=key,
                            points=points(answer, key, awards), invalid=error,
                            reviewed=bool(row['Reviewed'])))
    return results


def save_record(path, record):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    division(record['team_number'])
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('CREATE TABLE IF NOT EXISTS records (id INTEGER PRIMARY KEY, created TEXT DEFAULT CURRENT_TIMESTAMP, team TEXT, name TEXT, division TEXT, score INTEGER, status TEXT, data TEXT)')
        cursor = db.execute('INSERT INTO records(team,name,division,score,status,data) VALUES (?,?,?,?,?,?)',
                           (record['team_number'], record['team_name'], division(record['team_number']), record['score'], record['status'], json.dumps(record)))
        return cursor.lastrowid


def records(path):
    if not Path(path).exists():
        return []
    with closing(sqlite3.connect(path)) as db:
        return [dict(id=r[0], created=r[1], team_number=r[2], team_name=r[3], division=r[4], score=r[5], status=r[6], record=json.loads(r[7]))
                for r in db.execute('SELECT * FROM records ORDER BY id DESC')]


def delete_record(path, record_id):
    """Delete one snapshot by ID; return whether it still existed."""
    if not Path(path).exists():
        return False
    with closing(sqlite3.connect(path)) as db, db:
        cursor = db.execute('DELETE FROM records WHERE id = ?', (record_id,))
        return cursor.rowcount == 1


def regrade_records(path, keys):
    """Apply a complete key to every saved record in one transaction.

    Keep each record's answers, review state, status and scoring rules. Return
    the number updated; a malformed record rolls back the whole update.
    """
    keys = [integer(value) for value in keys]
    if len(keys) != 60 or any(value is None for value in keys):
        raise ValueError('The answer key must contain exactly 60 integers.')
    if not Path(path).exists():
        return 0
    updated = 0
    with closing(sqlite3.connect(path)) as db, db:
        for record_id, data in db.execute('SELECT id, data FROM records').fetchall():
            try:
                record = json.loads(data)
                if record.get('answer_key') == keys:
                    continue
                rows = record['rows']
                if len(rows) != 60 or {r['Question'] for r in rows} != set(range(1, 61)):
                    raise ValueError('Expected saved answers for questions 1 through 60.')
                awards = record['awards']
                if len(awards) != 3 or any(type(a) is not int or a < 0 for a in awards):
                    raise ValueError('Invalid saved scoring rules.')
                results = assess(sorted(rows, key=lambda row: row['Question']), keys, awards)
                record.update(answer_key=keys, results=results,
                              score=sum(r['points'] for r in results))
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f'Cannot recalculate record #{record_id}: {exc}') from exc
            db.execute('UPDATE records SET score = ?, data = ? WHERE id = ?',
                       (record['score'], json.dumps(record), record_id))
            updated += 1
    return updated


def update_record_answers(path, record_id, answers_by_question):
    """Correct an existing record, using its current saved key and awards."""
    if set(answers_by_question) != set(range(1, 61)):
        raise ValueError('Provide answers for questions 1 through 60; blanks are allowed.')
    answers = {q: '' if a is None else str(a).strip() for q, a in answers_by_question.items()}
    invalid = []
    for question, answer in answers.items():
        try:
            integer(answer)
        except ValueError:
            invalid.append(question)
    if invalid:
        raise ValueError('Enter integers or blanks for questions: ' + ', '.join(map(str, sorted(invalid))))
    if not Path(path).exists():
        raise ValueError('This saved record no longer exists.')
    with closing(sqlite3.connect(path)) as db, db:
        stored = db.execute('SELECT data FROM records WHERE id = ?', (record_id,)).fetchone()
        if stored is None:
            raise ValueError('This saved record no longer exists.')
        record = json.loads(stored[0])
        rows = record.get('rows', [])
        if len(rows) != 60 or {r['Question'] for r in rows} != set(range(1, 61)):
            raise ValueError('This record does not contain all 60 saved answers.')
        keys = [integer(k) for k in record.get('answer_key', [])]
        awards = record.get('awards', [])
        if len(keys) != 60 or any(k is None for k in keys):
            raise ValueError('This record needs a complete answer key before it can be edited.')
        if len(awards) != 3 or any(type(a) is not int or a < 0 for a in awards):
            raise ValueError('This record has invalid saved scoring rules.')
        for row in rows:
            row['Answer'] = answers[row['Question']]
        results = assess(sorted(rows, key=lambda row: row['Question']), keys, awards)
        record.update(results=results, score=sum(r['points'] for r in results))
        cursor = db.execute('UPDATE records SET score = ?, data = ? WHERE id = ? AND data = ?',
                            (record['score'], json.dumps(record), record_id, stored[0]))
        if cursor.rowcount != 1:
            raise ValueError('This record changed while saving. Reopen it and try again.')
        return record['score']
