import unittest
import tempfile
from pathlib import Path
from streamlit.testing.v1 import AppTest
from core import records, save_record
from PIL import Image
from imaging import LAYOUT_PRESETS

ROOT=Path(__file__).resolve().parents[1]

class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.app_root = Path(self.directory.name)

    def test_delete_selected_record_and_last_record(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root/'data'/'grades.sqlite'
            record = dict(team_number='B12',team_name='Test team',score=0,status='Draft',results=[])
            first = save_record(path, record)
            second = save_record(path, record)
            source = f'''import sys
from pathlib import Path
sys.path.insert(0, {str(ROOT)!r})
exec(compile(Path({str(ROOT/'app.py')!r}).read_text(encoding='utf-8'), {str(ROOT/'app.py')!r}, 'exec'), {{'__file__': {str(root/'app.py')!r}, '__name__': '__main__'}})
'''
            app = AppTest.from_string(source).run()
            self.assertEqual(len(app.exception), 0)
            self.assertTrue(app.button(key=f'delete_record_{second}').disabled)
            app.checkbox(key=f'confirm_delete_{second}').check().run()
            # Confirmation belongs to the selected ID, not a different record.
            next(s for s in app.selectbox if s.label == 'Open saved record').select(first).run()
            self.assertTrue(app.button(key=f'delete_record_{first}').disabled)
            app.checkbox(key=f'confirm_delete_{first}').check().run()
            app.button(key=f'delete_record_{first}').click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual([r['id'] for r in records(path)], [second])
            self.assertTrue(any(f'Deleted record #{first}' in s.value for s in app.success))
            app.checkbox(key=f'confirm_delete_{second}').check().run()
            app.button(key=f'delete_record_{second}').click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(records(path), [])
            self.assertTrue(any('Saved team records will appear here' in s.value for s in app.info))

    def test_initial_key_and_division(self):
        source = f'''import sys
from pathlib import Path
sys.path.insert(0, {str(ROOT)!r})
exec(compile(Path({str(ROOT/'app.py')!r}).read_text(encoding='utf-8'), {str(ROOT/'app.py')!r}, 'exec'), {{'__file__': {str(self.app_root/'app.py')!r}, '__name__': '__main__'}})
'''
        app=AppTest.from_string(source).run()
        self.assertEqual(len(app.exception),0)
        app.text_area(key='key_text').set_value(' '.join(['0']*60)).run()
        app.text_input(key='team_number').set_value('B004').run()
        self.assertEqual(len(app.exception),0)
        self.assertTrue(any('Middle school' in s.value for s in app.success))
        app.text_input(key='team_number').set_value('C12').run()
        self.assertTrue(any('High school' in s.value for s in app.success))

    def test_uploaded_sheet_and_score_edits(self):
        # Exercise uploads without depending on an unbundled competition PDF.
        sample = self.app_root/'sample.png'
        Image.new('RGB', (1224, 1584), 'white').save(sample)
        source=f'''\nimport sys\nfrom pathlib import Path\nfrom unittest.mock import patch\nimport io\nimport streamlit as st\nsys.path.insert(0,{str(ROOT)!r})\nclass Upload(io.BytesIO):\n    name='sample.png'\nupload=Upload(Path({str(sample)!r}).read_bytes())\ndef uploader(label,*args,**kwargs):\n    return upload if kwargs.get('key')=='sheet' else None\nwith patch.object(st,'file_uploader',uploader):\n    exec(compile(Path({str(ROOT/'app.py')!r}).read_text(encoding="utf-8"),{str(ROOT/'app.py')!r},'exec'),{{'__file__':{str(self.app_root/'app.py')!r},'__name__':'__main__'}})\n'''
        app=AppTest.from_string(source).run(timeout=30)
        self.assertEqual(len(app.exception),0)
        self.assertEqual(len(app.session_state['rows']),60)
        self.assertEqual(app.selectbox(key='layout_template').value, list(LAYOUT_PRESETS)[0])
        for template in list(LAYOUT_PRESETS)[1:] + list(LAYOUT_PRESETS)[:1]:
            app.selectbox(key='layout_template').select(template).run(timeout=30)
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(len(app.session_state['rows']), 60)
        app.text_area(key='key_text').set_value(' '.join(['0']*60)).run(timeout=30)
        self.assertTrue(any(m.value=='0 / 300' for m in app.metric))
        rows=app.session_state['rows']
        rows[0].update(Answer='0',Reviewed=True)
        app.session_state['rows']=rows
        app.session_state['editor_version']+=1
        app.run(timeout=30)
        self.assertEqual(len(app.exception),0)
        self.assertTrue(any(m.value=='5 / 300' for m in app.metric))
        rows=app.session_state['rows']; rows[0].update(Answer='2'); app.session_state['rows']=rows
        app.session_state['editor_version']+=1
        app.run(timeout=30)
        self.assertTrue(any(m.value=='1 / 300' for m in app.metric))

if __name__=='__main__': unittest.main()
