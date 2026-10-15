"""Online, one-time setup. The grading app itself uses local files only."""
from recognition import MODEL_DIR
from transformers import TrOCRProcessor, VisionEncoderDecoderModel

if __name__ == '__main__':
    model_id = 'microsoft/trocr-small-handwritten'
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    TrOCRProcessor.from_pretrained(model_id).save_pretrained(MODEL_DIR)
    VisionEncoderDecoderModel.from_pretrained(model_id).save_pretrained(MODEL_DIR)
    print('Downloaded model. Launch with: python -m streamlit run app.py')
