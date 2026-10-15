"""Local-only inference. Download weights separately with download_model.py."""
from pathlib import Path
import re

MODEL_DIR = Path(__file__).resolve().parent / 'models' / 'trocr-small-handwritten'


class IntegerTokens:
    """Constrain TrOCR's SentencePiece vocabulary to a signed integer or blank."""

    def __init__(self, tokenizer):
        self.tokenizer = tokenizer
        self.eos = tokenizer.eos_token_id
        special = set(tokenizer.all_special_ids)
        # SentencePiece's leading marker is removed at the start of a reading,
        # but would insert a space anywhere else (including after a minus).
        self.starts = []
        self.digits = []
        for token, token_id in tokenizer.get_vocab().items():
            if token_id in special:
                continue
            if re.fullmatch(r'▁?(?:-?[0-9]+|-)', token):
                self.starts.append(token_id)
            if re.fullmatch(r'[0-9]+', token):
                self.digits.append(token_id)
        if not self.starts or not self.digits or self.eos is None:
            raise RuntimeError('The installed tokenizer does not support integer-only recognition.')

    def __call__(self, batch_id, input_ids):
        # The first ID is the decoder start token (also EOS in TrOCR).
        if len(input_ids) == 1:
            return self.starts + [self.eos]
        text = self.tokenizer.decode(input_ids[1:], skip_special_tokens=True,
                                     clean_up_tokenization_spaces=False)
        if text == '-':
            return self.digits
        if re.fullmatch(r'-?[0-9]+', text):
            return self.digits + [self.eos]
        raise ValueError('Unexpected prefix during integer-only recognition.')


class Reader:
    def __init__(self):
        import torch
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel
        if not MODEL_DIR.exists():
            raise RuntimeError('Model is not installed. Run python download_model.py first.')
        self.torch = torch
        self.processor = TrOCRProcessor.from_pretrained(str(MODEL_DIR), local_files_only=True)
        self.integer_tokens = IntegerTokens(self.processor.tokenizer)
        self.model = VisionEncoderDecoderModel.from_pretrained(str(MODEL_DIR), local_files_only=True)
        self.model.eval()
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model.to(self.device)

    def read(self, images, progress=None, *, integer_only=True):
        from core import integer
        readings = []
        constraints = {}
        if integer_only:
            constraints = dict(prefix_allowed_tokens_fn=self.integer_tokens,
                               forced_bos_token_id=None,
                               forced_eos_token_id=self.processor.tokenizer.eos_token_id)
        for i, image in enumerate(images):
            pixels = self.processor(images=image.convert('RGB'), return_tensors='pt').pixel_values.to(self.device)
            with self.torch.inference_mode():
                output = self.model.generate(pixels, max_new_tokens=24, return_dict_in_generate=True,
                    output_scores=True, output_logits=True, do_sample=False, num_beams=1, **constraints)
            text = self.processor.batch_decode(output.sequences, skip_special_tokens=True)[0].strip()
            if integer_only and text and not re.fullmatch(r'-?[0-9]+', text):
                readings.append(('', 'Unreadable integer; enter the answer manually'))
                if progress:
                    progress((i+1)/len(images))
                continue
            try:
                value = integer(text)
                reason = 'Check handwriting' if value is not None else 'Blank or unreadable'
            except ValueError:
                reason = 'Recognition did not produce an integer'
            # Scores are a warning signal, never a calibrated correctness probability.
            # Use raw logits: masking other characters must not inflate the signal.
            if output.logits:
                transitions = self.model.compute_transition_scores(output.sequences, output.logits, normalize_logits=True)
                signal = float(transitions.exp().mean().cpu())
                if signal < .85:
                    reason = 'Weak recognition signal; check handwriting'
            readings.append((text, reason))
            if progress:
                progress((i+1)/len(images))
        return readings
