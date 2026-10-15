import tempfile
import unittest
from pathlib import Path
from core import integer, division, points, assess, save_record, records, delete_record
from imaging import answers, DEFAULT_LAYOUT, load_page
from PIL import Image

class GradingTests(unittest.TestCase):
    def test_integer_validation(self):
        self.assertEqual(integer('−12'),-12)
        self.assertIsNone(integer('  '))
        for bad in ['2.0','1 2','7abc','NaN']:
            with self.assertRaises(ValueError): integer(bad)
    def test_partial_credit_and_blank_zero(self):
        self.assertEqual([points(a,-3) for a in [-3,-2,-5,0,None]],[5,3,1,0,0])
        self.assertEqual(points(None,0),0)
    def test_division_validation(self):
        self.assertEqual(division(' b004 '),'Middle school')
        self.assertEqual(division('C42'),'High school')
        for bad in ['A12','B','C-3','B3junk']:
            with self.assertRaises(ValueError): division(bad)
    def test_correction_changes_score(self):
        rows=[dict(Question=1,Answer='4',Reviewed=False)]
        self.assertEqual(assess(rows,[5])[0]['points'],3)
        rows[0].update(Answer='5',Reviewed=True)
        self.assertEqual(assess(rows,[5])[0]['points'],5)
        rows[0]['Answer']='oops'
        self.assertTrue(assess(rows,[5])[0]['invalid'])
    def test_record_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'db.sqlite'
            rec=dict(team_number='C004',team_name='Seven Lakes',score=281,status='Draft',results=[])
            save_record(path,rec)
            self.assertEqual(records(path)[0]['record'],rec)
            self.assertEqual(records(path)[0]['division'],'High school')
    def test_sixty_crops_and_bounds(self):
        crops=answers(Image.new('RGB',(1200,1553),'white'),DEFAULT_LAYOUT)
        self.assertEqual(len(crops),60)
        self.assertTrue(all(c.width>0 and c.height>0 for c in crops))
        with self.assertRaises(ValueError): answers(Image.new('RGB',(1200,1553)),dict(DEFAULT_LAYOUT,first_y=.9))

    def test_delete_only_selected_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'db.sqlite'
            rec = dict(team_number='C004',team_name='Same team',score=100,status='Draft',results=[])
            first = save_record(path, rec)
            second = save_record(path, rec)
            self.assertTrue(delete_record(path, first))
            self.assertEqual([r['id'] for r in records(path)], [second])
            self.assertFalse(delete_record(path, first))
            self.assertTrue(delete_record(path, second))
            self.assertEqual(records(path), [])

    def test_delete_missing_database_does_not_create_it(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'missing.sqlite'
            self.assertFalse(delete_record(path, 1))
            self.assertFalse(path.exists())

if __name__=='__main__': unittest.main()
