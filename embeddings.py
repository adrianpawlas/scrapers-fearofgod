"""SigLIP image and text embeddings (768-dim) for products."""
import io
import logging
import requests
import torch
from PIL import Image
from transformers import AutoProcessor, AutoModel, AutoTokenizer

from config import SIGLIP_MODEL, EMBEDDING_DIM

logger = logging.getLogger(__name__)


def _device():
    return "cuda" if torch.cuda.is_available() else "cpu"


def load_siglip():
    """Load processor, tokenizer, and model once."""
    device = _device()
    processor = AutoProcessor.from_pretrained(SIGLIP_MODEL)
    tokenizer = AutoTokenizer.from_pretrained(SIGLIP_MODEL)
    model = AutoModel.from_pretrained(
        SIGLIP_MODEL,
        torch_dtype=torch.float32,
        device_map=None,
    )
    model = model.to(device)
    model.eval()
    return processor, tokenizer, model, device


def image_embedding_from_url(image_url: str, processor, model, device) -> list[float] | None:
    """Download image and return 768-dim embedding from SigLIP vision encoder."""
    if not image_url or not image_url.startswith("http"):
        return None
    for attempt in range(2):
        try:
            resp = requests.get(image_url, timeout=30)
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content)).convert("RGB")
            break
        except Exception as e:
            if attempt == 1:
                logger.warning("image_embedding_from_url failed: %s", e)
                return None
    try:
        inputs = processor(images=img, return_tensors="pt", padding="max_length")
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            out = model.get_image_features(**inputs)
        if out is None:
            return None
        vec = out[0].float().cpu().numpy().tolist()
        if len(vec) != EMBEDDING_DIM:
            return None
        return vec
    except Exception as e:
        logger.warning("image_embedding inference failed: %s", e)
        return None


def text_embedding(text: str, tokenizer, model, device) -> list[float] | None:
    """Return 768-dim text embedding from SigLIP text encoder."""
    if not text or not str(text).strip():
        return None
    try:
        inputs = tokenizer(
            str(text)[:5000],
            return_tensors="pt",
            padding="max_length",
            truncation=True,
            max_length=64,
        )
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            out = model.get_text_features(**inputs)
        if out is None:
            return None
        vec = out[0].float().cpu().numpy().tolist()
        if len(vec) != EMBEDDING_DIM:
            return None
        return vec
    except Exception as e:
        logger.warning("text_embedding failed: %s", e)
        return None


def build_info_text(row: dict) -> str:
    """Build a single text blob from product row for info_embedding."""
    parts = [
        row.get("title") or "",
        row.get("description") or "",
        row.get("category") or "",
        row.get("gender") or "",
        row.get("brand") or "",
        row.get("price") or "",
        row.get("sale") or "",
        row.get("metadata") or "",
    ]
    return " ".join(p for p in parts if p).strip()
