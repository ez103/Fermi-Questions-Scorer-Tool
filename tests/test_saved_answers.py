import copy
from pathlib import Path
import tempfile
import unittest

from streamlit.testing.v1 import AppTest
from core import records, regrade_records, save_record, update_record_answers
from test_regrade import sample_record

ROOT = Path(__file__).resolve().parents[1]


class SavedAnswerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.path = self.root/'data'/'grades.sqlite'
        self.record_id = save_record(self.path, sample_record())

    def answers(self):
        record = next(r['record'] for r in records(self.path) if r['id'] == self.record_id)
        return {row['Question']: row['Answer'] for row in record['rows']}

    def test_corrections_preserve_identity_metadata_and_other_records(self):
        other_id = save_record(self.path, sample_record('C12'))
        before = {r['id']: r for r in records(self.path)}
        answers = self.answers()
        answers.update({1: '-2', 2: '', 3: '0'})
        self.assertEqual(update_record_answers(self.path, self.record_id, answers), 6)
        after = {r['id']: r for r in records(self.path)}
        self.assertEqual(after[other_id], before[other_id])
        expected = copy.deepcopy(before[self.record_id])
        expected['score'] = 6
        expected['record']['score'] = 6
        expected['record']['results'] = after[self.record_id]['record']['results']
        for row in expected['record']['rows']:
            row['Answer'] = answers[row['Question']]
        self.assertEqual(after[self.record_id], expected)
        self.assertEqual(len(after), 2)
        self.assertEqual([r['answer'] for r in expected['record']['results'][:3]], [-2, None, 0])
        regrade_records(self.path, [1] * 60)
        self.assertEqual(next(r['score'] for r in records(self.path) if r['id'] == self.record_id), 59)

    def test_custom_awards_and_current_saved_key(self):
        self.record_id = save_record(self.path, sample_record('C1', (10, 4, 2), 'Draft'))
        regrade_records(self.path, [1] * 60)
        answers = self.answers()
        answers.update({1: '-2', 2: None, 3: '0'})
        self.assertEqual(update_record_answers(self.path, self.record_id, answers), 116)
        saved = records(self.path)[0]
        self.assertEqual(saved['status'], 'Draft')
        self.assertEqual(saved['record']['answer_key'], [1] * 60)
        self.assertEqual(saved['record']['awards'], [10, 4, 2])

    def test_invalid_answers_or_deleted_record_never_write(self):
        before = records(self.path)
        for invalid in ['1.5', 'abc', '- 2']:
            answers = self.answers()
            answers[1] = invalid
            with self.assertRaisesRegex(ValueError, 'questions: 1'):
                update_record_answers(self.path, self.record_id, answers)
            self.assertEqual(records(self.path), before)
        answers = self.answers()
        answers.pop(60)
        with self.assertRaises(ValueError):
            update_record_answers(self.path, self.record_id, answers)
        with self.assertRaisesRegex(ValueError, 'no longer exists'):
            update_record_answers(self.path, 999, self.answers())
        self.assertEqual(records(self.path), before)

    def app(self):
        source = f'''import sys
from pathlib import Path
sys.path.insert(0, {str(ROOT)!r})
exec(compile(Path({str(ROOT/'app.py')!r}).read_text(encoding='utf-8'), {str(ROOT/'app.py')!r}, 'exec'), {{'__file__': {str(self.root/'app.py')!r}, '__name__': '__main__'}})
'''
        return AppTest.from_string(source).run()

    def edit(self, app, changes):
        # AppTest has no grid-cell API; send the same widget delta as the editor.
        key = next(k for k in app.session_state if k.startswith('saved_answers_'))
        app.session_state[key] = {'edited_rows': changes, 'added_rows': [], 'deleted_rows': []}
        next(b for b in app.button if b.label == 'Save answer changes').click().run()

    def test_editor_save_refreshes_table_and_rejects_invalid_input(self):
        app = self.app()
        self.assertEqual(len(app.exception), 0)
        self.edit(app, {0: {'Answer': '-2'}, 1: {'Answer': ''}, 2: {'Answer': '0'}})
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(records(self.path)[0]['score'], 6)
        self.assertEqual(app.dataframe[0].value['score'].tolist(), [6])
        self.assertTrue(any('New score: 6' in s.value for s in app.success))
        before = records(self.path)
        self.edit(app, {0: {'Answer': 'oops'}})
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any('Answers were not saved' in e.value for e in app.error))
        self.assertEqual(records(self.path), before)
        self.assertEqual(self.app().dataframe[0].value['score'].tolist(), [6])


if __name__ == '__main__':
    unittest.main()
