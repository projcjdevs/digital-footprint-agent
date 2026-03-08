from sentence_transformers import SentenceTransformer
import logging

logger = logging.getLogger(__name__)

_model = None

def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info("Loading embedding model...")
        _model = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info("Embedding model ready")
    return _model

def embed_text(text: str) -> list[float]:
    """Convert any text into a 384-dim vector"""
    model = get_model()
    return model.encode(text).tolist()