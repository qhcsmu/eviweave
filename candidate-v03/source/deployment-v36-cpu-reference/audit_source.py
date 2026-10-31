"""Independent scalar/ranking audit of every fresh CPU source result."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent


def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    out=HERE/'SOURCE128'
    result=read(out/'RESULT.json')
    assert read(out/'PROCESS_EXIT.json')['exit_code']==0
    assert read(out/'completion.json')['result_sha256']==sha(out/'RESULT.json')
    assert result['rows_sha256']==sha(out/'all128-metadata.json')
    assert result['protocol_sha256']==sha(HERE/'SOURCE_PROTOCOL.json')
    spec=importlib.util.spec_from_file_location('source_independent_scalar',BASE/'metric-space-v30-inference/audit_gpu_validation.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    data=read(BASE/'metric-space-v29/prepared/DATA.json')
    cases={c['id']:c for c in data['cases'] if c['split']=='val'}
    references={arm:{r['id']:r for r in read(BASE/'metric-space-v29/run-step80'/filename)['rows']}
        for arm,filename in [('pristine','baseline-validation.json'),('learned','learned-validation.json')]}
    rows=read(out/'all128-metadata.json')['rows']
    assert len(rows)==128 and len({(r['arm'],r['id']) for r in rows})==128
    maximum=0.0
    for row in rows:
        case=cases[row['id']]
        persona=case['persona']
        indices=data['retained_indices'][persona]
        parents=[data['documents'][persona+':'+str(i)]['parent_digest'] for i in indices]
        scores=row['scores_original_index_order']
        assert len(scores)==len(indices) and all(type(v)==float and math.isfinite(v) for v in scores)
        actual=module.independent_metrics(scores,indices,case['positive_indices'],parents,case['chunk_recall_denominator'],case['annotated_messages'])
        expected=references[row['arm']][row['id']]
        for field in module.METRICS+('top10_original_indices','source_top10_parent_digests'):
            assert actual[field]==expected[field]==row['metrics'][field]
        delta=max(abs(a-b) for a,b in zip(scores,expected['scores_original_index_order']))
        assert delta==row['GPU_reference_max_score_delta']
        maximum=max(maximum,delta)
    assert maximum==result['GPU_reference_max_score_delta']
    assert all(c['repeat_probes_exact'] and c['repeat_probes']==8 for c in result['costs'].values())
    assert result['CPU_reference_source_rank_qualified'] and result['GPU_equivalence_qualified'] is False
    proof=dict(passed=True,vectors_checked=128,scalar_metrics_checked=128*7,source_result_sha256=sha(out/'RESULT.json'),
        GPU_reference_max_score_delta=maximum,GPU_equivalence_qualified=False,old_numerical_gates_unchanged=True,
        neural_calls=0,benchmark_or_holdout_records_read=0)
    with (out/'INDEPENDENT_AUDIT.json').open('x') as stream:json.dump(proof,stream,indent=2);stream.write('\n')
    print(json.dumps(proof))


if __name__=='__main__':main()
