from typing import Optional
import base64
from PIL import Image

try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # type: ignore

from .config import config


def _pil_to_data_url(image: Image.Image) -> str:
    import io
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def run_vision_ocr(image_b64: str, api_key: Optional[str]) -> str:
    if OpenAI is None or not api_key:
        return ""  # no-op when client missing or api key missing
    client = OpenAI(api_key=api_key)
    prompt = (
        "You are an expert OCR and document formatter for Korean insurance manuals.\n"
        "Read the page image and output a clean, well-structured Markdown representation.\n"
        "- Preserve headings, bullet points, tables.\n"
        "- Only transcribe; do not add any explanation.\n"
    )
    try:
        resp = client.chat.completions.create(
            model=config.VISION_MODEL,
            temperature=0,
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_b64}}
                ]
            }]
        )
        return resp.choices[0].message.content or ""
    except Exception:
        return ""


def pil_image_to_b64(image: Image.Image) -> str:
    return _pil_to_data_url(image)
