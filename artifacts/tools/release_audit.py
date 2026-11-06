"""Verify source identity and scan the reorganized publication for unsafe additions."""
import hashlib
import json
from pathlib import Path
import re
import runpy

ROOT = Path(__file__).resolve().parents[2]


def main():
    runpy.run_path(str(Path(__file__).with_name('verify_layout.py')), run_name='__main__')
    layout = json.loads((ROOT/'DEVELOPMENT_LAYOUT.json').read_text(encoding='utf-8'))
    source = json.loads((ROOT/'docs/source-manifest.json').read_text(encoding='utf-8'))
    for name, expected in source['copied_source_sha256'].items():
        current = layout['original_files'][name]['path']
        if hashlib.sha256((ROOT/current).read_bytes()).hexdigest() != expected:
            raise SystemExit('Frozen source hash differs: '+current)
    credential = re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)')
    forbidden = {'.sqlite3', '.sqlite', '.db', '.gguf', '.safetensors', '.bin', '.log'}
    for name in layout['files_sha256']:
        path = ROOT/name
        original_artifact = name in layout['protected_files'] and name.startswith('candidate-v03/')
        if (path.suffix in forbidden or path.stat().st_size > 2_000_000) and not original_artifact:
            raise SystemExit('Unexpected artifact: '+name)
        if path.name.startswith('.env') or any(part in {'data', 'models', 'request-intents'} for part in path.relative_to(ROOT).parts):
            raise SystemExit('Excluded path: '+name)
        try:
            content = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            if not original_artifact:
                raise SystemExit('Unregistered binary: '+name)
            continue
        if credential.search(content):
            raise SystemExit('Possible credential; value omitted: '+name)
        if re.search(r'[CD]:[/\\](?:Users|agent memory challenge|models)[/\\]', content):
            raise SystemExit('Machine-specific local path: '+name)
    print(json.dumps(dict(publication_audit_passed=True, copied_sources=len(source['copied_source_sha256']),
                         registered_frozen_artifacts_only=True)))


if __name__=='__main__':
    main()
