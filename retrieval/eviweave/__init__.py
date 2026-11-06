"""EviWeave: raw-source memory retrieval, with experimental learned recall."""
from adaptive_evidence.core import Config, ConflictError, MemoryStore
from .encoders import HashEncoder

__version__ = "0.1.0"
__all__ = ["Config", "ConflictError", "MemoryStore", "HashEncoder"]
