"""Freeze the explicit CPU candidate; never reclassify old GPU fidelity failures."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
ROOT=BASE.parents[3]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    files=list(HERE.glob('*.py'))+[HERE/'SOURCE_PROTOCOL.json',
        BASE/'metric-space-v34-search-credit/search_credit.py',BASE/'metric-space-v33-timestamp-credit/temporal_headers.py',
        BASE/'metric-space-v29/metric_model.py',BASE/'metric-space-v29/RECIPE.json',BASE/'metric-space-v29/MODEL_CARD.json',
        BASE/'deployment-v34/CPU_RUNTIME_CONTRACT/RESULT.json',BASE/'deployment-v34/CPU_RUNTIME_CONTRACT/PROCESS_EXIT.json']
    for name in ('runtime_store.py','transform.py'):
        new=(HERE/name).read_text().replace('eviweave-v03-search-credit-v34-cpu-reference-v36','eviweave-v03-search-credit-v34-gpu')
        assert new==(BASE/'deployment-v34'/name).read_text()
    assert json.loads((BASE/'deployment-v34/CPU_RUNTIME_CONTRACT/RESULT.json').read_text())['passed']
    files += [p for p in (ROOT/'models/Qwen3.5-4B').iterdir() if p.is_file() and p.suffix in {'.json','.txt','.model'}]
    files += [p for p in (ROOT/'models/colbertv2.0').iterdir() if p.is_file() and p.suffix in {'.json','.txt'}]
    manifest=dict(utc=datetime.now(timezone.utc).isoformat(),candidate_id='eviweave-v03-search-credit-v34-cpu-reference-v36',
        local_files_sha256={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in files},
        model=dict(base_sha256='3f58890b1dfdfec066ef12ba431fa9d56992da9e30a53489242c4156e37e9017',
        adapter_sha256='d86e773035f920b9d5dc23ba91e4c802dfcbf6d897813029b012057d62316619',profile='original-FP32-CPU-reference-v36',
        device='cpu',dot_dtype='float32',sum_dtype='float64',query_positions=32,document_window=177,document_stride=145),
        qualification='Fresh CPU source128 ranking and memory-cache exact-repeat, observed exit0, independent scalar audit required before launch. This manifest does not assert completion.',
        GPU_equivalence_qualified=False,old_v30_v35_numerical_gates_unchanged=True,
        CPU_contract_equivalence='Runtime store/transform are byte-identical to audited v34 after candidate identity string normalization; model scoring is separately identified CPU original reference.',
        official_classification='exploratory-current-candidate',local_final_answer_gates_passed=False,
        source_archive_sha256=json.loads((ROOT/'competition/runs/best32-incumbent-20261021/incumbent.json').read_text())['archive_sha256'],
        public_GPU_lock_touched=False,training_steps=0,Answer_Judge_calls=0,Full_authorized=False,promotion_authorized=False)
    with (HERE/'MANIFEST.json').open('x') as stream:json.dump(manifest,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(status='CPU_candidate_manifest_frozen',manifest_sha256=sha(HERE/'MANIFEST.json'),files=len(files),GPU_equivalence_qualified=False)))


if __name__=='__main__':main()
