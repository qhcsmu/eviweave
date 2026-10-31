"""Verify the byte identity of the published v0.3 deployment source snapshot."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parent.parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--index',action='store_true',help='Verify staged Git blobs')
    group.add_argument('--git-object',help='Verify one fixed Git commit/ref instead of working files')
    args=parser.parse_args()

    def content(name):
        path=(ROOT/name).resolve()
        assert path.is_relative_to(ROOT),'Source path escapes repository'
        if args.index or args.git_object:
            blob=(':' if args.index else args.git_object+':')+name
            return subprocess.check_output(['git','show',blob],cwd=ROOT)
        return path.read_bytes()

    mapping=json.loads(content('candidate-v03/SOURCE_MAP.json'))
    assert mapping['runtime_source_files']==len(mapping['files'])==24
    for row in mapping['files'].values():
        raw=content(row['repository_path'])
        assert hashlib.sha256(raw).hexdigest()==row['sha256'],row['repository_path']
        ast.parse(raw.decode('utf-8-sig'))
    raw=content('candidate-v03/DEPLOYED_MANIFEST.json')
    assert hashlib.sha256(raw).hexdigest()==mapping['deployed_manifest_sha256']
    manifest=json.loads(raw)
    model=json.loads(content('candidate-v03/MODEL_IDENTITY.json'))
    assert model['candidate_id']==manifest['candidate_id']==mapping['candidate_id']
    assert all(model[name]==value for name,value in manifest['model'].items())
    print(json.dumps(dict(passed=True,source_files=24,Python_ASTs_valid=True,
        all_source_bytes_and_deployed_manifest_match=True,
        candidate_manifest_sha256=mapping['deployed_manifest_sha256'],
        verification_scope='Git index' if args.index else args.git_object or 'working files',
        live_deployment_verified_by_this_tool=False,model_quality_or_originality_proven=False)))


if __name__=='__main__':main()
