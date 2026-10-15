"""Explicit setup-time model download. Recognition itself stays local."""
from pathlib import Path


if __name__ == '__main__':
    from huggingface_hub import snapshot_download
    root = Path(__file__).resolve().parent
    destination = root / 'models' / 'en_PP-OCRv5_mobile_rec'
    snapshot_download('PaddlePaddle/en_PP-OCRv5_mobile_rec',
        revision='267c36e24c331595590fe7bd72bde2436fd286f2',
        local_dir=str(destination), cache_dir=str(root / 'models' / '.download-cache'),
        allow_patterns=['inference.json', 'inference.pdiparams', 'inference.yml'])
    print(f'PaddleOCR model installed: {destination}')
