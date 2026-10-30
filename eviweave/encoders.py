"""A deterministic model-free demo encoder and explicit local BGE loading."""
import hashlib
import numpy as np
from adaptive_evidence.core import tokens


class HashEncoder:
    """Lexical demonstration only: not a pretrained semantic embedding model."""
    identity = "eviweave-demo-hash256-v1"

    def encode(self, texts, *, query=False):
        values = np.zeros((len(texts), 256), dtype=np.float32)
        for i, text in enumerate(texts):
            for term in tokens(text):
                slot = int.from_bytes(hashlib.sha256(term.encode()).digest()[:4], "big") % 256
                values[i, slot] += 1
            if not values[i].any():
                values[i, 0] = 1
        norms = np.linalg.norm(values, axis=1, keepdims=True)
        return values / np.maximum(norms, 1e-12)


def local_encoder(kind="hash", model_dir=None, device="cpu"):
    if kind == "hash":
        if device != "cpu":
            raise ValueError("The model-free hash encoder uses CPU only")
        return HashEncoder()
    if kind != "bge" or not model_dir:
        raise ValueError("Choose hash, or bge with an existing local model directory")
    from adaptive_evidence.encoder import BGEEncoder
    return BGEEncoder(str(model_dir), device=device)
