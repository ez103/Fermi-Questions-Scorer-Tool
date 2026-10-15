"""PaddleOCR adapter, isolated from TrOCR's Python dependencies."""
import atexit
import base64
import io
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import threading

ROOT = Path(__file__).resolve().parent


def prepare_crop(image):
    """Trim empty margins, keeping original pixels and padding for recognition."""
    from PIL import ImageOps
    image = image.convert('RGB')
    box = ImageOps.grayscale(image).point(lambda p: 255 if p < 220 else 0).getbbox()
    if box is None:
        return None
    return ImageOps.expand(image.crop(box), border=8, fill='white')


def format_reading(text, confidence, integer_only=True):
    text = text.strip()
    if integer_only:
        # Normalize a Unicode minus and whitespace immediately after a minus.
        # Do not remove punctuation/letters or join separated numbers into a guess.
        text = re.sub(r'^[-\u2212]\s*(?=[0-9])', '-', text)
        if text and not re.fullmatch(r'-?[0-9]+', text):
            return '', f'Unreadable integer (OCR: {text}); enter the answer manually'
    if not text:
        return '', 'Blank or unreadable; check handwriting'
    reason = 'Check handwriting' if confidence >= .85 else 'Weak recognition signal; check handwriting'
    return text, reason


class PaddleReader:
    def __init__(self):
        self.process = None
        self.lock = threading.Lock()
        atexit.register(self.close)

    def close(self):
        process, self.process = self.process, None
        if process is not None:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            for pipe in (process.stdin, process.stdout):
                if pipe:
                    pipe.close()

    def _start(self):
        python = ROOT / '.venv-paddle' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        if not python.exists():
            raise RuntimeError('PaddleOCR is not installed. Run Setup_PaddleOCR.bat first.')
        self.process = subprocess.Popen([str(python), '-u', str(ROOT / 'paddle_worker.py')],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding='utf-8', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.responses = queue.Queue()
        def collect(process, responses):
            try:
                for line in process.stdout:
                    if line.startswith('FERMI_RESULT:'):
                        responses.put(json.loads(line[len('FERMI_RESULT:'):]))
            except (ValueError, OSError):
                pass
            finally:
                responses.put({'error': 'PaddleOCR stopped unexpectedly. Run Setup_PaddleOCR.bat or try again.'})
        threading.Thread(target=collect, args=(self.process, self.responses), daemon=True).start()

    def read(self, images, progress=None, *, integer_only=True):
        if not images:
            return []
        encoded = []
        for image in images:
            buffer = io.BytesIO()
            image.convert('RGB').save(buffer, format='PNG')
            encoded.append(base64.b64encode(buffer.getvalue()).decode('ascii'))
        with self.lock:
            if self.process is None or self.process.poll() is not None:
                self.close()
                self._start()
            try:
                self.process.stdin.write(json.dumps({'images': encoded}) + '\n')
                self.process.stdin.flush()
                response = self.responses.get(timeout=180)
                if 'error' in response:
                    raise RuntimeError(response['error'])
                readings = response['readings']
                if len(readings) != len(images):
                    raise RuntimeError('PaddleOCR returned an incomplete sheet. Please try again.')
            except (OSError, queue.Empty, RuntimeError, KeyError) as exc:
                self.close()
                if isinstance(exc, queue.Empty):
                    raise RuntimeError('PaddleOCR timed out. Please try again.') from exc
                raise
        if progress:
            progress(1.)
        return [format_reading(text, score, integer_only) for text, score in readings]
