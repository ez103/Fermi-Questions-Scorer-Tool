import unittest
from paddle_recognition import format_reading, prepare_crop, PaddleReader
from PIL import Image, ImageDraw


class PaddleOutputTests(unittest.TestCase):
    def test_signed_integers_and_minus_spacing(self):
        for text, expected in [('0','0'), ('12','12'), ('-12','-12'), ('- 12','-12'), ('\u2212 3','-3')]:
            self.assertEqual(format_reading(text, .99)[0], expected)

    def test_ambiguous_output_is_not_silently_converted(self):
        for text in ['1 2', '1.2', '1,000', 'O', 'I2', '+3', '--2', '-', '12x']:
            answer, warning = format_reading(text, .99)
            self.assertEqual(answer, '')
            self.assertIn(text, warning)
            self.assertIn('manually', warning)

    def test_header_is_unrestricted(self):
        self.assertEqual(format_reading(' Team C12 ', .99, False)[0], 'Team C12')

    def test_blank_and_confidence_remain_advisory(self):
        self.assertIn('Blank', format_reading('', .99)[1])
        self.assertIn('Weak', format_reading('12', .5)[1])
        self.assertIn('Check', format_reading('12', .99)[1])

    def test_empty_batch_does_not_start_process(self):
        reader = PaddleReader()
        self.assertEqual(reader.read([]), [])
        self.assertIsNone(reader.process)

    def test_trim_keeps_separated_minus_and_digit_and_does_not_change_ink(self):
        crop = Image.new('RGB', (200, 60), 'white')
        draw = ImageDraw.Draw(crop)
        draw.line((20,30,35,30), fill='black', width=2)
        draw.line((60,15,60,40), fill='black', width=2)
        trimmed = prepare_crop(crop)
        self.assertLess(trimmed.width, crop.width)
        before = sum(pixel == (0,0,0) for pixel in crop.getdata())
        after = sum(pixel == (0,0,0) for pixel in trimmed.getdata())
        self.assertEqual(before, after)
        self.assertIsNone(prepare_crop(Image.new('RGB', (100,50), 'white')))
