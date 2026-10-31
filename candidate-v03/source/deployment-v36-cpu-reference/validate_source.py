"""Fresh CPU source128 ranking check, explicitly not old GPU equivalence."""
from datetime import datetime,timezone
import gc
import json
import os
from pathlib import Path
import time
from direct_scorer import DirectScorer,load,sha,read,np,torch

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
ROOT=BASE.parents[3]
V29=BASE/'metric-space-v29'


def main():
    began=time.monotonic()
    plan=read(HERE/'SOURCE_PROTOCOL.json')
    for name,expected in plan['dependencies_sha256'].items():assert sha(Path(name))==expected
    out=HERE/'SOURCE128'
    out.mkdir(exist_ok=False)
    data=read(V29/'prepared/DATA.json')
    cases=[c for c in data['cases'] if c['split']=='val']
    assert len(cases)==64
    source=ROOT/'competition/runs/sourcetrail-colbert-full-history-20261017'
    queries={c['id']:c for c in read(source/'training-cases.json')}
    banks=read(source/'training-banks.json')
    metrics=load('cpu_v36_metrics',V29/'metrics.py')
    rows=[]
    costs={}
    for arm,filename in [('pristine','baseline-validation.json'),('learned','learned-validation.json')]:
        start=time.monotonic()
        scorer=DirectScorer(arm)
        reference={r['id']:r for r in read(V29/'run-step80'/filename)['rows']}
        repeat_exact=[]
        for persona in sorted({c['persona'] for c in cases}):
            indices=data['retained_indices'][persona]
            bodies=[banks[persona][i]['content'] for i in indices]
            parents=[data['documents'][persona+':'+str(i)]['parent_digest'] for i in indices]
            for i,body in zip(indices,bodies):
                assert scorer.encoder.tokenizer.encode(body,add_special_tokens=False,verbose=False)==data['documents'][persona+':'+str(i)]['token_ids']
            for n,case in enumerate(c for c in cases if c['persona']==persona):
                query=queries[case['id']]['query']
                assert scorer.encoder.tokenizer.encode(query,add_special_tokens=False,verbose=False)==case['token_ids']
                before=time.monotonic()
                scores=scorer.score(query,bodies)
                seconds=time.monotonic()-before
                if n==0:
                    repeat_exact.append(bool(np.array_equal(scores,scorer.score(query,bodies))))
                old=reference[case['id']]
                current=metrics.summarize_case(scores,indices,case['positive_indices'],parents,case['chunk_recall_denominator'],case['annotated_messages'])
                rows.append(dict(arm=arm,id=case['id'],seconds=seconds,
                    same_chunk_top10=current['top10_original_indices']==old['top10_original_indices'],
                    same_source_top10=current['source_top10_parent_digests']==old['source_top10_parent_digests'],
                    same_metrics=all(current[m]==old[m] for m in metrics.METRICS),
                    GPU_reference_max_score_delta=float(np.max(np.abs(scores-np.asarray(old['scores_original_index_order'])))),
                    scores_original_index_order=scores.tolist(),metrics=current))
            print(json.dumps(dict(stage='direct_CPU_reference_source',arm=arm,completed=sum(r['arm']==arm for r in rows))),flush=True)
        costs[arm]=dict(identity=scorer.identity,wall_seconds=time.monotonic()-start,usage=dict(scorer.usage),
            encoder_usage=dict(scorer.encoder.usage),memory_cache_bytes=scorer.cache_bytes,repeat_probes_exact=all(repeat_exact),repeat_probes=len(repeat_exact))
        scorer.close()
        del scorer
        gc.collect()
    assert len(rows)==128 and not torch.cuda.is_initialized()
    passed=all(r[k] for r in rows for k in ('same_chunk_top10','same_source_top10','same_metrics')) and all(v['repeat_probes_exact'] for v in costs.values())
    for name,expected in plan['dependencies_sha256'].items():assert sha(Path(name))==expected
    (out/'all128-metadata.json').write_text(json.dumps(dict(rows=rows),indent=2)+'\n')
    result=dict(complete=True,CPU_reference_source_rank_qualified=passed,queries=128,
        changed_chunk_top10=sum(not r['same_chunk_top10'] for r in rows),changed_source_top10=sum(not r['same_source_top10'] for r in rows),
        changed_metrics=sum(not r['same_metrics'] for r in rows),GPU_reference_max_score_delta=max(r['GPU_reference_max_score_delta'] for r in rows),
        GPU_equivalence_qualified=False,old_frozen_1e5_gate_unchanged=True,costs=costs,wall_seconds=time.monotonic()-began,
        GPU_work=False,public_GPU_lock_touched=False,training_steps=0,Answer_Judge_calls=0,benchmark_or_holdout_records_read=0,
        protocol_sha256=sha(HERE/'SOURCE_PROTOCOL.json'),rows_sha256=sha(out/'all128-metadata.json'),
        limitation='Separate CPU original-reference exploration, not v30/v35 numerical qualification or final-answer/promotion evidence.')
    (out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
    (out/'completion.json').write_text(json.dumps(dict(result_sha256=sha(out/'RESULT.json')))+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='costs'}),flush=True)
    if not passed:raise SystemExit(1)


if __name__=='__main__':
    main()
