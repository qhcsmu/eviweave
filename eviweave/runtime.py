"""Explicit local runtime configuration, independent of benchmark assets."""
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
import gc
import sys

from adaptive_evidence import core
from adaptive_evidence.focused_packing import STANDING_RULE
from .encoders import local_encoder
from .locking import ModelLease


@dataclass
class Settings:
    database: str = "data/memory.sqlite3"
    encoder: str = "hash"
    model_dir: str | None = None
    device: str = "cpu"
    context_chars: int = 24000
    api_token: str | None = None
    experimental: bool = False
    colbert_dir: str | None = None
    colbert_device: str = "cpu"
    adapter_path: str | None = None
    adapter_sha256: str | None = None
    index_dir: str = "data/colbert-index"
    gpu_lock_dir: str | None = None


class Runtime:
    def __init__(self, settings=None):
        self.settings = settings or Settings()
        self.store = self.scorer = self.lease = None

    def __enter__(self):
        s = self.settings
        uses_gpu = s.device.startswith("cuda") or (s.experimental and s.colbert_device.startswith("cuda"))
        if uses_gpu and not s.gpu_lock_dir:
            raise ValueError("GPU use requires an explicit shared --gpu-lock-dir")
        self.lease = ModelLease(s.gpu_lock_dir) if uses_gpu else nullcontext()
        self.lease.__enter__()
        try:
            encoder = local_encoder(s.encoder, s.model_dir, s.device)
            store_class = core.MemoryStore
            kwargs = {}
            if s.experimental:
                if not s.colbert_dir:
                    raise ValueError("Experimental retrieval requires a local --colbert-dir")
                if bool(s.adapter_path) != bool(s.adapter_sha256):
                    raise ValueError("Provide both adapter path and SHA256, or neither")
                from .experimental import token_scorer
                from .experimental.content_tokens import scorer_class
                from .experimental.corpus_index import disk_scorer_class, memory_store_class
                from .experimental.guards import MULTI, RULE_QUERY
                index_dir = Path(s.index_dir).resolve()
                index_dir.mkdir(parents=True, exist_ok=True)
                scorer_type = disk_scorer_class(scorer_class(token_scorer, core.STOP), index_dir)
                self.scorer = scorer_type(s.colbert_dir, device=s.colbert_device,
                                           adapter_path=s.adapter_path, adapter_sha256=s.adapter_sha256)
                store_class = memory_store_class(core, MULTI, RULE_QUERY, STANDING_RULE)
                kwargs["scorer"] = self.scorer
            self.store = store_class(s.database, encoder, core.Config(context_chars=s.context_chars), **kwargs)
            return self
        except Exception:
            self.__exit__(*sys.exc_info())
            raise

    def __exit__(self, *args):
        try:
            if self.scorer is not None and hasattr(self.scorer, "disk"):
                self.scorer.disk.close()
            self.store = self.scorer = None
            gc.collect()
            if "torch" in sys.modules and sys.modules["torch"].cuda.is_initialized():
                sys.modules["torch"].cuda.empty_cache()
        finally:
            if self.lease is not None:
                self.lease.__exit__(*args)
                self.lease = None
