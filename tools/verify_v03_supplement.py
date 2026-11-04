"""Verify the v0.3 public runtime supplement without loading models or data."""
import argparse
import ast
import hashlib
import json
import math
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--index", action="store_true", help="Verify staged Git blobs")
    group.add_argument("--git-object", help="Verify a fixed Git commit/ref")
    args = parser.parse_args()

    def content(name):
        path = (ROOT / name).resolve()
        assert path.is_relative_to(ROOT), "Path escapes repository"
        if args.index or args.git_object:
            blob = (":" if args.index else args.git_object + ":") + name
            return subprocess.check_output(["git", "show", blob], cwd=ROOT)
        return path.read_bytes()

    def read(name):
        return json.loads(content(name))

    base = "candidate-v03/runtime-linux/"
    manifest = read(base + "SUPPLEMENT_MANIFEST.json")
    assert hashlib.sha256(content("candidate-v03/DEPLOYED_MANIFEST.json")).hexdigest() == manifest["initial_manifest_sha256"]
    seen = set()
    for row in manifest["files"]:
        name = row["repository_path"]
        assert name.startswith(base) and name not in seen
        seen.add(name)
        raw = content(name)
        assert len(raw) == row["bytes"], name
        assert hashlib.sha256(raw).hexdigest() == row["sha256"], name
        if name.endswith(".py"):
            ast.parse(raw.decode("utf-8-sig"))
    overlay = manifest["API_overlay"]
    assert overlay["query_only"] and overlay["target"] == "adaptive_evidence/remote_encoder.py"
    assert hashlib.sha256(content(base + "source/remote_encoder.py")).hexdigest() == overlay["deployed_sha256"]
    archive = manifest["API_source_archive_verification"]
    assert archive["all_match"] and archive["compared_API_runtime_Python_files"] == len(archive["files"]) == 13
    for row in archive["files"]:
        assert hashlib.sha256(content(row["repository_path"])).hexdigest() == row["sha256"], row["repository_path"]
    validation = read(base + "VALIDATION.json")
    assert validation["passed"] and validation["owner_checks"]["passed"]
    delta = validation["maximum_absolute_score_delta"]
    assert math.isfinite(delta) and delta <= validation["existing_gate"]["maximum_absolute_score_delta"] == 1e-5
    assert len(validation["inputs"]) == 5
    assert all(row["passed"] and all(row["checks"].values()) for row in validation["inputs"])
    full = read("candidate-v03/FULL_RESULT.json")
    assert full["status"] == "succeeded" and full["phase"] == "full"
    result = full["aggregate"]
    assert result["completed"] == result["total"] == 9602
    assert math.isfinite(result["score"]) and 0 <= result["score"] <= 1
    assert all(b["status"] == "succeeded" and b["done"] == b["total"] for b in full["branch_completion"].values())
    print(json.dumps(dict(passed=True, supplemental_artifacts=len(seen),
        archive_hashes_and_ASTs_valid=True, API_archive_source_files=13, fixed_synthetic_parity_record_valid=True,
        Full_complete_aggregate_record_valid=True, verification_scope="Git index" if args.index else args.git_object or "working files",
        model_calls=0, live_deployment_verified_by_this_tool=False)))


if __name__ == "__main__":
    main()
