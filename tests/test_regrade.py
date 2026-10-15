import copy
from pathlib import Path
import tempfile
import unittest

from streamlit.testing.v1 import AppTest
from core import assess, records, regrade_records, save_record

ROOT = Path(__file__).resolve().parents[1]


def sample_record(team='B12', awards=(5, 3, 1), status='Final'):
    answers = ['0', '-1', '1', ''] + ['3'] * 56
    rows = [dict(Question=i+1, Answer=a, Reviewed=True, Warning='Checked')
            for i, a in enumerate(answers)]
    results = assess(rows, [0] * 60, awards)
    return dict(team_number=team, team_name='Test team', status=status,
                rows=rows, awards=awards, answer_key=[0] * 60, results=results,
                score=sum(r['points'] for r in results), source_filename='scan.png')


class RegradeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.path = self.root/'data'/'grades.sqlite'

    def test_both_divisions_keep_answers_status_and_own_awards(self):
        first = save_record(self.path, sample_record())
        other = sample_record('C34', (10, 4, 2), 'Draft')
        other['rows'].reverse()  # Match key entries by question, not storage order.
        second = save_record(self.path, other)
        before = {r['id']: r for r in records(self.path)}
        self.assertEqual(regrade_records(self.path, [1] * 60), 2)
        after = {r['id']: r for r in records(self.path)}
        self.assertEqual(after[first]['score'], 65)
        self.assertEqual(after[second]['score'], 128)
        for record_id, saved in after.items():
            expected = copy.deepcopy(before[record_id])
            expected['score'] = saved['score']
            expected['record'].update(score=saved['score'], answer_key=[1] * 60,
                                      results=saved['record']['results'])
            self.assertEqual(saved, expected)
            self.assertEqual(saved['record']['results'][3]['points'], 0)
            self.assertEqual(saved['score'], sum(r['points'] for r in saved['record']['results']))
        self.assertEqual(regrade_records(self.path, [1] * 60), 0)
        self.assertEqual(regrade_records(self.path, [0] * 60), 2)
        self.assertEqual({r['id']: r['score'] for r in records(self.path)},
                         {i: r['score'] for i, r in before.items()})

    def test_invalid_keys_and_corrupt_record_do_not_partially_update(self):
        save_record(self.path, sample_record())
        before = records(self.path)
        for key in [[], [1] * 59, [1] * 61, ['x'] * 60, [''] * 60]:
            with self.assertRaises(ValueError):
                regrade_records(self.path, key)
            self.assertEqual(records(self.path), before)
        broken = sample_record('C1')
        broken['rows'].pop()
        save_record(self.path, broken)
        before = records(self.path)
        with self.assertRaisesRegex(ValueError, 'record #'):
            regrade_records(self.path, [1] * 60)
        self.assertEqual(records(self.path), before)

    def test_missing_database_not_created(self):
        self.assertEqual(regrade_records(self.path, [0] * 60), 0)
        self.assertFalse(self.path.exists())

    def app(self):
        # Keep all writes in an isolated database; mock only file upload input.
        source = f'''import io
import sys
from pathlib import Path
from unittest.mock import patch
import streamlit as st
sys.path.insert(0, {str(ROOT)!r})
def uploader(label, *args, **kwargs):
    data = st.session_state.get('test_key_file')
    return io.BytesIO(data) if kwargs.get('key') == 'key_upload' and data is not None else None
with patch.object(st, 'file_uploader', uploader):
    exec(compile(Path({str(ROOT/'app.py')!r}).read_text(encoding='utf-8'), {str(ROOT/'app.py')!r}, 'exec'), {{'__file__': {str(self.root/'app.py')!r}, '__name__': '__main__'}})
'''
        return AppTest.from_string(source).run()

    def test_sidebar_edits_update_saved_tables_and_survive_new_session(self):
        save_record(self.path, sample_record())
        save_record(self.path, sample_record('C34'))
        app = self.app()
        original = records(self.path)
        self.assertEqual(len(app.exception), 0)
        app.text_area(key='key_text').set_value(' '.join(['1'] * 60)).run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(all(r['score'] == 65 for r in records(self.path)))
        self.assertEqual(app.dataframe[0].value['score'].tolist(), [65, 65])
        self.assertTrue(all(app.dataframe[1].value['key'] == 1))
        for invalid in ['', '1 2', ' '.join(['oops'] + ['1'] * 59)]:
            app.text_area(key='key_text').set_value(invalid).run()
            self.assertTrue(all(r['score'] == 65 for r in records(self.path)))
        fresh = self.app()
        self.assertEqual(fresh.dataframe[0].value['score'].tolist(), [65, 65])
        app.text_area(key='key_text').set_value(' '.join(['0'] * 60)).run()
        self.assertEqual(records(self.path), original)

    def test_uploaded_key_can_be_edited_without_file_overriding_it(self):
        save_record(self.path, sample_record())
        app = self.app()
        app.session_state['test_key_file'] = ('\ufeff' + ','.join(['1'] * 60)).encode('utf-8')
        app.run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(records(self.path)[0]['score'], 65)
        self.assertEqual(app.text_area(key='key_text').value, ','.join(['1'] * 60))
        app.text_area(key='key_text').set_value(' '.join(['0'] * 60)).run()
        self.assertEqual(records(self.path)[0]['record']['answer_key'], [0] * 60)
        app.session_state['test_key_file'] = b'\xff'
        app.run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(records(self.path)[0]['record']['answer_key'], [0] * 60)
        self.assertTrue(any('UTF-8' in e.value for e in app.error))


if __name__ == '__main__':
    unittest.main()
