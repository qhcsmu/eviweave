"""Fetch/verify frozen v0.3 artifacts in a new workspace; never start services."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import urllib.request
import zipfile

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / 'candidate-v03/artifacts/ARTIFACTS.json'


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def verify(path, row):
    if not path.is_file() or path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
        raise ValueError('Artifact missing or hash mismatch: ' + path.name)


def destination(root, name):
    rel = PurePosixPath(name)
    if rel.is_absolute() or '..' in rel.parts or '\\' in name or ':' in name:
        raise ValueError('Invalid archive path')
    target = (root / name).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError('Path escapes workspace')
    return target


def fetch(row, cache, offline):
    path = cache / row['filename']
    bundled = REPO / 'candidate-v03/artifacts' / row['filename']
    if not path.exists() and bundled.is_file():
        verify(bundled, row)
        shutil.copyfile(bundled, path)
    if not path.exists():
        if offline:
            raise ValueError('Offline artifact missing: ' + row['filename'])
        temporary = path.with_suffix(path.suffix + '.part')
        request = urllib.request.Request(row['url'], headers={'User-Agent': 'EviWeave-artifact-fetch/1'})
        with urllib.request.urlopen(request, timeout=60) as response, temporary.open('xb') as output:
            size = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > row['bytes']:
                    raise ValueError('Download exceeded frozen size')
                output.write(chunk)
        verify(temporary, row)
        temporary.rename(path)
    verify(path, row)
    return path


def unpack(archive, root, rows):
    expected = {row['path']: row for row in rows}
    license_names = {'licenses/' + name for name in ('CC-BY-4.0.txt', 'COLBERT-MIT.txt', 'QWEN-APACHE-2.0.txt', 'EVIWEAVE-MIT.txt')}
    with zipfile.ZipFile(archive) as source:
        members = source.infolist()
        names = [member.filename for member in members]
        if len(names) != len(set(names)) or set(names) != set(expected) | license_names:
            raise ValueError('Unexpected, missing or duplicate archive members')
        # Validate the entire archive before writing any workspace file.
        for member in members:
            destination(root, member.filename)
            if member.is_dir() or stat.S_ISLNK(member.external_attr >> 16):
                raise ValueError('Only regular files are accepted')
            if member.filename in expected:
                row = expected[member.filename]
                if member.file_size != row['bytes']:
                    raise ValueError('Unexpected uncompressed size')
                raw = source.read(member)
                if hashlib.sha256(raw).hexdigest() != row['sha256']:
                    raise ValueError('Archive member hash mismatch')
            elif member.file_size > 65536:
                raise ValueError('Unexpected license size')
        for member in members:
            path = destination(root, member.filename)
            raw = source.read(member)
            if path.exists():
                if path.read_bytes() != raw:
                    raise ValueError('Refusing to overwrite a different file')
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as output:
                output.write(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--controlled-bundle', type=Path)
    parser.add_argument('--base-file', type=Path, help='Existing exact base weight; copied only after hash verification')
    parser.add_argument('--public-only', action='store_true', help='Fetch public bundle and adapter, omit base and controlled records')
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--verify-only', action='store_true', help='Check catalog files in an existing destination without loading models')
    args = parser.parse_args()
    catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
    root = args.destination.resolve()
    if args.verify_only:
        selected = [r for r in catalog['files'] if not args.public_only or r['acquisition'] in ('adapter', 'public_bundle')]
        for row in selected:
            verify(destination(root, row['path']), row)
        print(json.dumps(dict(passed=True, files=len(selected), complete_startup_files=not args.public_only, model_calls=0, services_started=0)))
        return
    # Require the real controlled package up front; never replace it with stubs.
    if not args.public_only:
        if args.controlled_bundle is None:
            raise ValueError('Full file reconstruction requires --controlled-bundle; see ARTIFACT_ACCESS.md')
        verify(args.controlled_bundle, catalog['controlled_bundle'])
        if args.base_file is not None:
            verify(args.base_file, catalog['upstream_base'])
    if root.exists():
        raise ValueError('Destination must be a new directory; existing installations are never overwritten')
    root.mkdir(parents=True, exist_ok=False)
    cache = root / '.artifact-cache'
    cache.mkdir()
    public = fetch(catalog['public_bundle'], cache, args.offline)
    unpack(public, root, [r for r in catalog['files'] if r['acquisition'] == 'public_bundle'])
    adapter = fetch(catalog['adapter'], cache, args.offline)
    row = next(r for r in catalog['files'] if r['acquisition'] == 'adapter')
    target = destination(root, row['path'])
    target.parent.mkdir(parents=True, exist_ok=True)
    with adapter.open('rb') as source, target.open('xb') as output:
        shutil.copyfileobj(source, output)
    if not args.public_only:
        unpack(args.controlled_bundle, root, [r for r in catalog['files'] if r['acquisition'] == 'controlled_bundle'])
        base = args.base_file or fetch(catalog['upstream_base'], cache, args.offline)
        target = root / 'models/colbertv2.0/model.safetensors'
        target.parent.mkdir(parents=True, exist_ok=True)
        with base.open('rb') as source, target.open('xb') as output:
            shutil.copyfileobj(source, output)
    selected = [r for r in catalog['files'] if not args.public_only or r['acquisition'] in ('adapter', 'public_bundle')]
    for row in selected:
        verify(destination(root, row['path']), row)
    print(json.dumps(dict(passed=True, files=len(selected), complete_startup_files=not args.public_only, model_calls=0, services_started=0,
        next_step='Prepare isolated Python runtime, private configuration and operator activation, then repeat fixed synthetic parity before routing requests.')))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, zipfile.BadZipFile) as error:
        print('Artifact preparation stopped: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
