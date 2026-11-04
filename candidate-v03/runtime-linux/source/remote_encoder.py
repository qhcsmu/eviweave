"""Fixed text-embedding-v4 adapter for the documented DashScope HTTP API.

Only text supplied by the caller is sent to the configured endpoint. Responses
are checked before any vector is persisted. No fallback model or truncation.
Only provider-confirmed input-length errors use lossless segments of the same
text and model; successful requests retain the original code path and vectors.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import threading
import time
from urllib.parse import urlsplit

import httpx
import numpy as np


class EmbeddingError(RuntimeError):
    """Safe to expose: never contains provider responses, input text or keys."""


class EmbeddingInputLengthError(EmbeddingError):
    """A recognized provider length error, with numeric metadata only."""

    def __init__(self, limit: int):
        self.limit = limit
        super().__init__("Embedding provider HTTP 400 category=input_length")


LOG = logging.getLogger("adaptive_evidence")


def provider_error(response):
    """Classify errors without logging raw bodies or potentially echoed input."""
    try:
        body = response.json()
    except (ValueError, TypeError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    code = body.get("code")
    message = body.get("message", "")
    if response.status_code == 400 and code == "InvalidParameter" and isinstance(message, str):
        match = re.search(r"Range of input length should be \[1,\s*(\d+)\]", message, re.I)
        if match and 256 < int(match[1]) <= 1000000:
            return EmbeddingInputLengthError(int(match[1]))
    categories = {"InvalidParameter": "invalid_parameter", "DataInspectionFailed": "content_rejected",
                  "InvalidApiKey": "invalid_key", "Arrearage": "billing", "Throttling": "rate_limit"}
    category = categories.get(code, "unclassified") if isinstance(code, str) else "unclassified"
    return EmbeddingError(f"Embedding provider HTTP {response.status_code} category={category}")


def lossless_segments(text: str, byte_limit: int) -> list[str]:
    """Bound UTF-8 bytes, preserve codepoints and every source character."""
    chunks = []
    start = 0
    size = 0
    for position, char in enumerate(text):
        width = len(char.encode("utf-8"))
        if size and size + width > byte_limit:
            chunks.append(text[start:position])
            start, size = position, 0
        size += width
    chunks.append(text[start:])
    # Whitespace-only pieces carry no standalone embedding tokens. Attach them
    # to a neighboring content piece rather than dropping or embedding them.
    output, pending = [], ""
    for chunk in chunks:
        if not chunk.strip():
            pending += chunk
        else:
            output.append(pending + chunk)
            pending = ""
    if pending and output:
        output[-1] += pending
    assert "".join(output) == text
    return output


def validate_endpoint(endpoint: str):
    url = urlsplit(endpoint)
    if (url.scheme != "https" or not url.hostname or url.username or url.password
            or url.query or url.fragment or "{" in endpoint or "}" in endpoint):
        raise ValueError("AE_EMBEDDING_URL must be a configured HTTPS endpoint without credentials")


class DashScopeEncoder:
    model = "text-embedding-v4"
    input_length_recovery = "provider-confirmed-lossless-v1"
    dimensions_allowed = {64, 128, 256, 512, 768, 1024, 1536, 2048}
    retryable = {408, 425, 429, 500, 502, 503, 504}

    def __init__(self, key: str, endpoint: str, *, dimensions: int = 1024,
                 batch_size: int = 10, timeout: float = 60, max_attempts: int = 3,
                 max_requests: int = 0, transport=None, sleep=time.sleep):
        if not key or not key.strip():
            raise ValueError("DASHSCOPE_API_KEY is required")
        validate_endpoint(endpoint)
        if type(dimensions) is not int or dimensions not in self.dimensions_allowed:
            raise ValueError("Unsupported text-embedding-v4 dimension")
        if type(batch_size) is not int or not 1 <= batch_size <= 10:
            raise ValueError("Embedding batch size must be between 1 and 10")
        if not math.isfinite(timeout) or not 0 < timeout <= 300:
            raise ValueError("Embedding timeout must be between 0 and 300 seconds")
        if type(max_attempts) is not int or not 1 <= max_attempts <= 5:
            raise ValueError("Embedding max attempts must be between 1 and 5")
        if type(max_requests) is not int or max_requests < 0:
            raise ValueError("Embedding request budget must be non-negative")
        self.endpoint = endpoint
        self.dimensions = dimensions
        self.batch_size = batch_size
        self.max_attempts = max_attempts
        self.max_requests = max_requests
        self.sleep = sleep
        self.lock = threading.Lock()
        self.requests = 0
        self.total_tokens = 0
        # Model, endpoint, dimension and role semantics are part of DB identity.
        # Keys, timeout and batch size do not change the vector space.
        profile = {"model": self.model, "endpoint": endpoint, "dimensions": dimensions,
                   "protocol": "dashscope-native-v1", "document_type": "document",
                   "query_type": "query", "normalization": "l2", "truncation": "none"}
        self.identity = self.model + ":" + hashlib.sha256(
            json.dumps(profile, sort_keys=True).encode()).hexdigest()
        self.client = httpx.Client(timeout=timeout, follow_redirects=False,
                                   headers={"Authorization": "Bearer " + key}, transport=transport)

    def close(self):
        self.client.close()

    def usage(self) -> dict:
        with self.lock:
            return {"requests": self.requests, "reported_total_tokens": self.total_tokens,
                    "max_requests_this_process": self.max_requests}

    def _request(self, payload: dict) -> dict:
        for attempt in range(self.max_attempts):
            with self.lock:
                if self.max_requests and self.requests >= self.max_requests:
                    raise EmbeddingError("Embedding request budget exhausted")
                self.requests += 1
            try:
                response = self.client.post(self.endpoint, json=payload)
            except httpx.RequestError:
                if attempt + 1 == self.max_attempts:
                    raise EmbeddingError("Embedding provider connection failed") from None
            else:
                if response.status_code == 200:
                    try:
                        body = response.json()
                        if (not isinstance(body, dict) or body.get("code")
                                or body.get("status_code", 200) not in (200, "200")):
                            raise ValueError("Provider error envelope")
                        usage = body.get("usage", {})
                        amount = usage.get("total_tokens", 0) if isinstance(usage, dict) else 0
                        if type(amount) is int and amount >= 0:
                            with self.lock:
                                self.total_tokens += amount
                        return body
                    except (ValueError, TypeError):
                        raise EmbeddingError("Embedding provider returned an invalid response") from None
                if response.status_code not in self.retryable or attempt + 1 == self.max_attempts:
                    raise provider_error(response)
            self.sleep(min(2 ** attempt, 8))
        raise EmbeddingError("Embedding provider unavailable")

    def encode(self, texts: list[str], *, query: bool = False) -> np.ndarray:
        if not isinstance(texts, list) or any(not isinstance(t, str) or not t.strip() for t in texts):
            raise ValueError("Embedding input must be a list of non-empty strings")
        if not texts:
            return np.empty((0, self.dimensions), dtype=np.float32)
        output = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start:start + self.batch_size]
            output.append(self._encode_batch(batch, query=query))
        return np.concatenate(output)

    def _encode_batch(self, batch: list[str], *, query: bool, recover: bool = True) -> np.ndarray:
        try:
            body = self._request({"model": self.model, "input": {"texts": batch},
                                  "parameters": {"dimension": self.dimensions, "output_type": "dense",
                                                 "text_type": "query" if query else "document"}})
        except EmbeddingInputLengthError as exc:
            if not recover or not query:
                raise
            if len(batch) > 1:
                middle = len(batch) // 2
                return np.concatenate([self._encode_batch(batch[:middle], query=query),
                                       self._encode_batch(batch[middle:], query=query)])
            text = batch[0]
            pieces = lossless_segments(text, min(7680, exc.limit - 256))
            if len(pieces) <= 1:
                raise
            vectors = np.concatenate([
                self._encode_batch(pieces[start:start + self.batch_size], query=query, recover=False)
                for start in range(0, len(pieces), self.batch_size)])
            # Fixed weighted pooling uses every segment and the original role.
            # Original source text and lexical retrieval are never modified.
            weights = np.asarray([len(part.encode("utf-8")) for part in pieces], dtype=np.float64)
            pooled = np.average(vectors.astype(np.float64), axis=0, weights=weights)
            norm = np.linalg.norm(pooled)
            if not np.isfinite(norm) or norm == 0:
                raise EmbeddingError("Embedding provider returned invalid pooled vector") from None
            LOG.warning("embedding_length_recovery role=%s chars=%d utf8_bytes=%d segments=%d provider_limit=%d",
                        "query" if query else "document", len(text), len(text.encode("utf-8")),
                        len(pieces), exc.limit)
            return (pooled / norm).astype(np.float32)[None, :]
        try:
            records = body["output"]["embeddings"]
            if not isinstance(records, list) or len(records) != len(batch):
                raise ValueError("Missing embeddings")
            ordered = [None] * len(batch)
            for record in records:
                index = record["text_index"]
                vector = record["embedding"]
                if (type(index) is not int or not 0 <= index < len(batch) or ordered[index] is not None
                        or not isinstance(vector, list) or len(vector) != self.dimensions
                        or any(type(v) not in (int, float) for v in vector)):
                    raise ValueError("Invalid vector or index")
                ordered[index] = vector
            # Normalize in float64 so large finite values cannot overflow norm.
            matrix = np.asarray(ordered, dtype=np.float64)
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            if not np.isfinite(matrix).all() or not np.isfinite(norms).all() or np.any(norms == 0):
                raise ValueError("Invalid vector norm")
            return (matrix / norms).astype(np.float32)
        except (KeyError, IndexError, TypeError, ValueError, OverflowError):
            raise EmbeddingError("Embedding provider returned invalid vectors") from None


def encoder_from_env():
    """Official candidate defaults to v4; local BGE requires explicit selection."""
    import os

    backend = os.getenv("AE_EMBEDDING_BACKEND", "dashscope")
    if backend == "bge":
        from .encoder import BGEEncoder
        return BGEEncoder(os.environ["AE_EMBEDDING_PATH"], os.getenv("AE_DEVICE", "cpu"))
    if backend != "dashscope":
        raise ValueError("AE_EMBEDDING_BACKEND must be dashscope or bge")
    return DashScopeEncoder(
        os.getenv("DASHSCOPE_API_KEY", ""), os.getenv("AE_EMBEDDING_URL", ""),
        dimensions=int(os.getenv("AE_EMBEDDING_DIMENSIONS", "1024")),
        batch_size=int(os.getenv("AE_EMBEDDING_BATCH_SIZE", "10")),
        timeout=float(os.getenv("AE_EMBEDDING_TIMEOUT", "60")),
        max_attempts=int(os.getenv("AE_EMBEDDING_MAX_ATTEMPTS", "3")),
        max_requests=int(os.getenv("AE_EMBEDDING_MAX_REQUESTS", "0")))
