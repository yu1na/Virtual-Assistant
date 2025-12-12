from typing import Tuple
import numpy as np
import fitz
from PIL import Image

from .config import config


def render_page_to_image(page: fitz.Page, dpi: int = config.DPI_FOR_VISION) -> Image.Image:
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)


def load_to_numpy(pil_image: Image.Image) -> np.ndarray:
    arr = np.asarray(pil_image.convert("L"))  # grayscale
    return arr


def calc_variance(np_array: np.ndarray) -> float:
    if np_array is None or np_array.size == 0:
        return 0.0
    return float(np_array.var())
