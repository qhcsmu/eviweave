"""Independent m02 API entry point; shared exact32 tree is never edited."""
import hashlib
import json
import os
import urllib.request
from pathlib import Path
from fastapi.responses import JSONResponse
from adaptive_evidence import api
from runtime_store import CandidateStore, CandidateUnavailable

api.MemoryStore = CandidateStore
app = api.app
_health = api.health


def candidate_health(store=api.Depends(api.get_store)):
    try:
        request=urllib.request.Request('http://127.0.0.1:18403/health',
            headers={'Authorization':'Bearer '+os.environ['EVIWEAVE_RPC_TOKEN']})
        with urllib.request.urlopen(request,timeout=10) as response:
            model_health=json.load(response)
        assert model_health['status']=='ok' and model_health['candidate_id']=='eviweave-v03-search-credit-v34-cpu-reference-v36'
    except Exception:
        return JSONResponse(status_code=503,content={'status':'unavailable','system':'EviWeave',
            'candidate_id':'eviweave-v03-search-credit-v34-cpu-reference-v36','detail':'Learned retrieval service unavailable'})
    value = _health(store)
    value.update(system='EviWeave', registered_version='v0.3',
                 candidate_id='eviweave-v03-search-credit-v34-cpu-reference-v36',
                 candidate_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                 runtime_store_sha256=hashlib.sha256(Path(__file__).with_name('runtime_store.py').read_bytes()).hexdigest(),
                 candidate_counts=dict(store.candidate_counts),
                 candidate_device='cpu', candidate_numeric_qualification='GPU_equivalence_failed_preserved',
                 candidate_source_qualification='passed_CPU_reference_source128',
                 candidate_model=model_health['model'],candidate_manifest_sha256=model_health['manifest_sha256'],
                 candidate_qualification_sha256=model_health['qualification_sha256'])
    return value


for route in app.router.routes:
    if getattr(route, 'path', None) == '/health':
        app.router.routes.remove(route)
        break
app.get('/health')(candidate_health)


@app.exception_handler(CandidateUnavailable)
async def candidate_unavailable(request, exc):
    return JSONResponse(status_code=503, content={'detail': 'Learned retrieval unavailable; no baseline fallback'})
