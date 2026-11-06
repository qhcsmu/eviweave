"""Audit the publication tree; never reads files outside this repository."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    manifest = json.loads((ROOT / "docs/source-manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["copied_source_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError("Frozen upstream/research source changed: " + name)
        staged = subprocess.run(["git", "show", ":" + name], cwd=ROOT, capture_output=True, check=True).stdout
        if hashlib.sha256(staged).hexdigest() != expected:
            raise RuntimeError("Staged frozen source changed (check Git line endings): " + name)
    tracked = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout.decode().split("\0")
    files = [ROOT / name for name in tracked if name]
    if not files:
        raise RuntimeError("Stage the explicit release files before auditing")
    token = re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)")
    forbidden_suffixes = {".sqlite3", ".sqlite", ".db", ".gguf", ".safetensors", ".bin", ".log"}
    issues = []
    for file in files:
        name = file.relative_to(ROOT).as_posix()
        if file.suffix in forbidden_suffixes or file.name.startswith(".env") or any(part in {"data", "models", "request-intents"} for part in file.relative_to(ROOT).parts):
            issues.append(dict(file=name, reason="excluded artifact type"))
        staged = subprocess.run(["git", "show", ":" + name], cwd=ROOT, capture_output=True, check=True).stdout
        if len(staged) > 2_000_000:
            issues.append(dict(file=name, reason="unexpected large file"))
        content = staged.decode("utf-8")
        if token.search(content):
            issues.append(dict(file=name, reason="possible credential; value omitted"))
        if re.search(r"[CD]:[/\\](?:Users|agent memory challenge|models)[/\\]", content):
            issues.append(dict(file=name, reason="machine-specific local path"))
    if issues:
        print(json.dumps(dict(passed=False, issues=issues), indent=2))
        raise SystemExit(1)
    print(json.dumps(dict(passed=True, tracked_files=len(files), frozen_sources=len(manifest["copied_source_sha256"]),
                          no_model_database_or_credential_files=True), indent=2))


if __name__ == "__main__":
    main()
