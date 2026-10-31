"""Same frozen Search-only mechanism for RPC and local contract verification."""
from hashlib import sha256
import json
import math
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE/'metric-space-v34-search-credit'))
from search_credit import feasible

CANDIDATE = 'eviweave-v03-search-credit-v34-cpu-reference-v36'
FIELDS = {'protocol','query','native_units','native_hits','source_pool','top_k','context_chars'}


def transform(payload, tokenizer, scorer):
    if not isinstance(payload, dict) or set(payload) != FIELDS or payload['protocol'] != 'search-credit-v34':
        raise ValueError('Only the native Search boundary is accepted')
    if not 1 <= payload['top_k'] <= 100 or payload['context_chars'] != 24000:
        raise ValueError('Original Search limits required')
    query = payload['query']
    if not isinstance(query, str) or not query.strip():
        raise ValueError('Complete Search query required')
    hits = payload['native_hits']
    if len(hits)>payload['top_k'] or sum(len(h['content']) for h in hits)>24000:
        raise ValueError('Native hit limit violated')
    if len(payload['source_pool'])>128:
        raise ValueError('Native128 pool exceeded')
    if not scorer.eligible(query):
        return dict(candidate_id=CANDIDATE, hits=hits, changed=False, reason='unsupported_complete_query', neural_queries=0)
    admitted, detail = feasible(payload['native_units'], hits, payload['source_pool'], tokenizer,
                                top_k=payload['top_k'], context_chars=24000)
    if not admitted:
        return dict(candidate_id=CANDIDATE, hits=hits, changed=False, reason='no_self_funded_source', neural_queries=0, detail=detail)
    scores = [float(x) for x in scorer.score(query, [p['witness']['body'] for p in admitted])]
    if len(scores) != len(admitted) or not all(math.isfinite(s) for s in scores):
        raise ValueError('Complete finite source score vector required')
    winner = max(range(len(admitted)), key=lambda i:(scores[i], -admitted[i]['native_rank']))
    chosen = admitted[winner]
    # Hashes/cost only: do not log user queries, memories, options or answer text.
    return dict(candidate_id=CANDIDATE, hits=chosen['hits'], changed=True,
                reason='learned_complete_source', neural_queries=1,
                selected_source_sha256=sha256(chosen['source_id'].encode()).hexdigest(),
                source_count=len(admitted), native_rank=chosen['native_rank'], boundary=chosen['boundary'],
                Search_sha256=chosen['Search_sha256'], scores_sha256=sha256(json.dumps(scores).encode()).hexdigest())
