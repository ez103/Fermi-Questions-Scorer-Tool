"""Private local OCR process; stdin/stdout carry PNG crops and readings only."""
import base64
import io
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
MODEL_NAME = 'en_PP-OCRv5_mobile_rec'
PREFIX = 'FERMI_RESULT:'


def main():
    # Keep library messages separate from the response protocol.
    output = sys.stdout
    sys.stdout = sys.stderr
    os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'
    os.environ['PADDLE_PDX_CACHE_HOME'] = str(ROOT / 'models' / '.paddle-cache')
    model = None
    for line in sys.stdin:
        try:
            from PIL import Image
            from paddle_recognition import prepare_crop
            import numpy as np
            if model is None:
                from paddleocr import TextRecognition
                model_dir = ROOT / 'models' / MODEL_NAME
                for name in ('inference.json', 'inference.pdiparams', 'inference.yml'):
                    if not (model_dir / name).is_file():
                        raise RuntimeError('PaddleOCR model is missing. Run Setup_PaddleOCR.bat.')
                model = TextRecognition(model_name=MODEL_NAME, model_dir=str(model_dir),
                    device='cpu', enable_mkldnn=True, cpu_threads=4)
            request = json.loads(line)
            crops = [prepare_crop(Image.open(io.BytesIO(base64.b64decode(data)))) for data in request['images']]
            active = [(i, np.asarray(crop)[:, :, ::-1].copy()) for i, crop in enumerate(crops) if crop is not None]
            results = list(model.predict([array for _, array in active], batch_size=16)) if active else []
            if len(results) != len(active):
                raise RuntimeError('Recognition returned an unexpected number of answers. Try again.')
            readings = [['', 0.] for _ in crops]
            for (index, _), result in zip(active, results):
                readings[index] = [result['rec_text'], float(result['rec_score'])]
            response = {'readings': readings}
        except Exception as exc:
            response = {'error': str(exc)}
        output.write(PREFIX + json.dumps(response) + '\n')
        output.flush()


if __name__ == '__main__':
    main()
