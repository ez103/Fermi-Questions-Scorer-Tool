import base64
import io
from PIL import Image

# Measured from page 2 of the 2026 UT Invitational answer sheet (612 x 792 pt).
# Include the writing area above each rule, leaving the printed rule outside.
DEFAULT_LAYOUT = dict(column_x=[88.711/612, 203.774/612, 318.837/612, 433.900/612],
                      width=74/612, first_y=70.794/792,
                      row_step=35.86557/792, height=24.5/792)
LEGACY_LAYOUT = dict(column_x=[.146, .522], width=.120,
                     first_y=.083, row_step=.025158, height=.020)
LAYOUT_PRESETS = {'2026 UT Invitational (4 columns of 15)': DEFAULT_LAYOUT,
                  'Original sheet (2 columns of 30)': LEGACY_LAYOUT}


def load_page(data, filename, page=1):
    if filename.lower().endswith('.pdf'):
        import fitz
        with fitz.open(stream=data, filetype='pdf') as pdf:
            if not 1 <= page <= len(pdf):
                raise ValueError(f'PDF has {len(pdf)} pages; choose a page from 1 to {len(pdf)}.')
            pix = pdf[page - 1].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            return Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    from PIL import ImageOps
    return ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert('RGB')


def region(image, box):
    x, y, width, height = box
    if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > 1.000001 or y + height > 1.000001:
        raise ValueError('Crop is outside the page. Adjust layout coordinates.')
    w, h = image.size
    return image.crop((round(x*w), round(y*h), round((x+width)*w), round((y+height)*h)))


def answer_boxes(layout):
    """Return 60 boxes in question order, down columns from left to right."""
    # Older saved layout JSON used left_x/right_x instead of column_x.
    columns = layout.get('column_x')
    if columns is None:
        columns = [layout['left_x'], layout['right_x']]
    if len(columns) not in (2, 4):
        raise ValueError('Choose either 2 columns of 30 or 4 columns of 15.')
    if any(a >= b for a, b in zip(columns, columns[1:])):
        raise ValueError('Column X positions must increase from left to right.')
    if layout['row_step'] <= 0:
        raise ValueError('Row spacing must be greater than zero.')
    rows = 60 // len(columns)
    return [(columns[q // rows], layout['first_y'] + (q % rows)*layout['row_step'],
             layout['width'], layout['height']) for q in range(60)]


def answers(image, layout):
    return [region(image, box) for box in answer_boxes(layout)]


def preview(image, layout):
    from PIL import ImageDraw
    out = image.copy()
    draw = ImageDraw.Draw(out)
    w, h = out.size
    for x, y, width, height in answer_boxes(layout):
        draw.rectangle((x*w, y*h, (x+width)*w, (y+height)*h), outline='red', width=2)
    return out


def image_url(image):
    buffer = io.BytesIO()
    image.resize((300, 70)).save(buffer, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode()


def align_corners(image, corners):
    """Map user-selected page corners to a complete upright page."""
    import cv2
    import numpy as np
    w, h = image.size
    source = np.array([(x*w, y*h) for x, y in corners], dtype=np.float32)
    contour = source.astype(np.int32)
    if not cv2.isContourConvex(contour) or abs(cv2.contourArea(contour)) < .05*w*h:
        raise ValueError('Choose four page corners in clockwise order: top-left, top-right, bottom-right, bottom-left.')
    target = np.array([(0, 0), (1199, 0), (1199, 1552), (0, 1552)], dtype=np.float32)
    transform = cv2.getPerspectiveTransform(source, target)
    return Image.fromarray(cv2.warpPerspective(np.array(image), transform, (1200, 1553), borderValue=(255,255,255)))
