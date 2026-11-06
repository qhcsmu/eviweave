"""Atomic directory lock: only this process and token can release it."""
import json
import os
from pathlib import Path
import socket
import uuid
from datetime import datetime, timezone


class ModelLease:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.owner = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.path.mkdir()
        except FileExistsError as error:
            raise RuntimeError("Model lock is occupied; do CPU work and wait for its owner") from error
        self.owner = dict(token=uuid.uuid4().hex, pid=os.getpid(), host=socket.gethostname(),
                          run="eviweave", created_utc=datetime.now(timezone.utc).isoformat())
        try:
            (self.path / "owner.json").write_text(json.dumps(self.owner, indent=2), encoding="utf-8")
        except Exception:
            self.path.rmdir()
            raise
        return self

    def assert_owned(self):
        current = json.loads((self.path / "owner.json").read_text(encoding="utf-8-sig"))
        if current.get("token") != self.owner["token"] or current.get("pid") != os.getpid():
            raise RuntimeError("Model lock ownership changed; refuse to release another owner's lock")

    def __exit__(self, *args):
        self.assert_owned()
        (self.path / "owner.json").unlink()
        self.path.rmdir()
