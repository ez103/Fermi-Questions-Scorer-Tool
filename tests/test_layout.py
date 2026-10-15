import unittest
from PIL import Image, ImageDraw
from imaging import DEFAULT_LAYOUT, LEGACY_LAYOUT, answer_boxes, answers


class LayoutTests(unittest.TestCase):
    def test_new_sheet_reads_all_sixty_answers_in_column_order(self):
        # Independently measured answer-rule positions on the supplied PDF.
        sheet = Image.new('RGB', (1224, 1584), 'white')
        draw = ImageDraw.Draw(sheet)
        expected = []
        for column, x in enumerate([89.711, 204.774, 319.837, 434.900]):
            for row in range(15):
                question = column*15 + row + 1
                baseline = 96.794 + row*35.86557
                color = (question*3, 20, 100)
                expected.append(color)
                draw.rectangle((round((x+20)*2), round((baseline-18)*2),
                                round((x+50)*2), round((baseline-6)*2)), fill=color)
                draw.line((round(x*2), round(baseline*2), round((x+72)*2), round(baseline*2)), fill='black')
        crops = answers(sheet, DEFAULT_LAYOUT)
        self.assertEqual(len(crops), 60)
        for question, (crop, color) in enumerate(zip(crops, expected), 1):
            colors = set(crop.getdata())
            self.assertIn(color, colors, f'Question {question} is in the wrong crop')
            self.assertNotIn((0, 0, 0), colors, f'Question {question} includes the printed rule')
            self.assertEqual(colors - {(255, 255, 255)}, {color})

    def test_column_boundaries_and_old_layout_compatibility(self):
        boxes = answer_boxes(DEFAULT_LAYOUT)
        for start in (0, 15, 30, 45):
            self.assertEqual(boxes[start][1], boxes[0][1])
            self.assertGreater(boxes[start+14][1], boxes[start][1])
        self.assertLess(boxes[0][0], boxes[15][0])
        old_json = dict(left_x=.146, right_x=.522, width=.120,
                        first_y=.083, row_step=.025158, height=.020)
        self.assertEqual(answer_boxes(old_json), answer_boxes(LEGACY_LAYOUT))
        old_boxes = answer_boxes(LEGACY_LAYOUT)
        self.assertEqual(old_boxes[0][1], old_boxes[30][1])
        self.assertLess(old_boxes[0][0], old_boxes[30][0])

    def test_invalid_geometry_is_rejected(self):
        image = Image.new('RGB', (1224, 1584), 'white')
        for change in [dict(column_x=[.1, .3, .5]), dict(column_x=[.5, .2]),
                       dict(row_step=0), dict(first_y=.8), dict(width=0), dict(column_x=[.2, .95])]:
            with self.assertRaises(ValueError):
                answers(image, dict(DEFAULT_LAYOUT, **change))


if __name__ == '__main__':
    unittest.main()
