import re
import unittest
from recognition import IntegerTokens


class SentencePieceTokenizer:
    """Small vocabulary including tempting but invalid numeric continuations."""
    eos_token_id = 2
    all_special_ids = [0, 1, 2]
    tokens = ['<s>', '<pad>', '</s>', '▁-', '-', '▁12', '12', '0',
              '▁0', '▁-12', '-12', '▁', '.', ',', '+', 'a', '1.2',
              '1-2', '--', '−', '١', '12 ', '▁a']

    def get_vocab(self):
        return {token: i for i, token in enumerate(self.tokens)}

    def decode(self, ids, **kwargs):
        return ''.join(self.tokens[i] for i in ids if i not in self.all_special_ids).replace('▁', ' ').lstrip(' ')


class IntegerRecognitionTests(unittest.TestCase):
    def setUp(self):
        self.tokenizer = SentencePieceTokenizer()
        self.constraint = IntegerTokens(self.tokenizer)

    def test_start_allows_blank_negative_and_positive(self):
        allowed = self.constraint(0, [2])
        self.assertIn(2, allowed)
        texts = [self.tokenizer.decode([i]) for i in allowed]
        self.assertIn('-', texts)
        self.assertIn('-12', texts)
        self.assertIn('12', texts)
        self.assertTrue(all(re.fullmatch(r'-?[0-9]*', t) for t in texts))

    def test_minus_requires_digits_without_space(self):
        for minus in [3, 4]:
            allowed = self.constraint(0, [2, minus])
            self.assertNotIn(2, allowed)
            self.assertTrue(all(re.fullmatch(r'-[0-9]+', self.tokenizer.decode([minus, i])) for i in allowed))
            self.assertNotIn(self.tokenizer.get_vocab()['▁12'], allowed)

    def test_number_can_end_or_continue_without_symbols(self):
        for token in [5, 6, 7, 8, 9, 10]:
            allowed = self.constraint(0, [2, token])
            self.assertIn(2, allowed)
            self.assertTrue(all(re.fullmatch(r'-?[0-9]+', self.tokenizer.decode([token, i])) for i in allowed))


if __name__ == '__main__':
    unittest.main()
