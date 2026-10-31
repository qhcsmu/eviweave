"""Production Search boundary. Raw source provenance, no benchmark adapters."""
from contextlib import closing
import json
import os
import threading
import time
import urllib.request

from adaptive_evidence.core import MemoryStore, digest


class CandidateUnavailable(RuntimeError):
    pass


def source_unit(store, source, start=0, end=None):
    end = len(source['content']) if end is None else end
    return dict(source_id=source['id'], doc_id=source['id'],
                session=source['session_id'], ordinal=source['position'],
                start=start, end=end, header=store.render({**source, 'content': ''}),
                body=source['content'][start:end])


def trace_native(store, hits, originals):
    units = []
    for hit in hits:
        found = None
        for source in originals.values():
            header = store.render({**source, 'content': ''})
            if not hit['content'].startswith(header):
                continue
            body = hit['content'][len(header):]
            start = source['content'].find(body)
            while start >= 0:
                end = start + len(body)
                if digest([source['id'], start, end]) == hit['id']:
                    found = source_unit(store, source, start, end)
                    break
                start = source['content'].find(body, start+1)
            if found:
                break
        if found is None:
            raise CandidateUnavailable('Native evidence provenance cannot be reproduced')
        units.append(found)
    return units


def rpc_transform(payload):
    endpoint = os.environ['EVIWEAVE_RPC_URL']
    if endpoint != 'http://127.0.0.1:18403/transform':
        raise CandidateUnavailable('Only the private loopback tunnel is supported')
    token = os.environ['EVIWEAVE_RPC_TOKEN']
    request = urllib.request.Request(endpoint, data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={'Content-Type': 'application/json', 'Authorization': 'Bearer '+token}, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            result = json.load(response)
    except Exception as error:
        raise CandidateUnavailable('Learned retrieval service is unavailable') from error
    if result.get('candidate_id') != 'eviweave-v03-search-credit-v34-cpu-reference-v36':
        raise CandidateUnavailable('Unexpected retrieval implementation')
    hits = result.get('hits')
    if not isinstance(hits, list) or len(hits) != len(payload['native_hits']):
        raise CandidateUnavailable('Invalid candidate Search response')
    return result


class CandidateStore(MemoryStore):
    transform = staticmethod(rpc_transform)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._candidate_trace = threading.local()
        self._candidate_count_lock = threading.Lock()
        self.candidate_counts = dict(requests=0, native_document=0, transformed=0,
                                     unchanged_no_pool=0, unavailable=0, seconds=0.0)

    def ranked(self, index, query, options, mode, *, return_document_prior=False):
        result = super().ranked(index, query, options, mode,
                                return_document_prior=return_document_prior)
        if getattr(self._candidate_trace, 'capture', False):
            ranks, document = result if return_document_prior else (result, False)
            self._candidate_trace.value = (index, list(ranks), document)
        return result

    def search(self, *, user_id, query, top_k=100, options=None, mode='hybrid_window'):
        began = time.monotonic()
        self._candidate_trace.capture = True
        self._candidate_trace.value = None
        try:
            hits = super().search(user_id=user_id, query=query, top_k=top_k,
                                  options=options, mode=mode)
        finally:
            self._candidate_trace.capture = False
        captured = self._candidate_trace.value
        self._candidate_trace.value = None
        reason = 'unchanged_no_pool'
        try:
            if not hits or captured is None:
                return hits
            index, ranked, document = captured
            if document:
                reason = 'native_document'
                return hits
            # Sources are immutable originals. The native index snapshot binds IDs
            # and ranks; a later concurrent Add cannot change an existing source.
            source_ids = {r['source_id'] for r in index.rows}
            with closing(self.connect()) as db:
                originals = {r['id']: dict(r) for r in db.execute(
                    'SELECT id,session_id,position,role,timestamp,content FROM sources WHERE user_id=?', (user_id,))
                    if r['id'] in source_ids}
            native = trace_native(self, hits, originals)
            pool, seen = [], set()
            for rank, row_index in enumerate(ranked[:128], 1):
                sid = index.rows[row_index]['source_id']
                if sid in seen:
                    continue
                seen.add(sid)
                pool.append(dict(unit=source_unit(self, originals[sid]), native_rank=rank))
            payload = dict(protocol='search-credit-v34', query=query, native_units=native,
                native_hits=hits, source_pool=pool, top_k=top_k, context_chars=self.config.context_chars)
            result = self.transform(payload)
            reason = 'transformed' if result['changed'] else 'unchanged_no_pool'
            return result['hits']
        except Exception as error:
            reason = 'unavailable'
            if isinstance(error, CandidateUnavailable):
                raise
            raise CandidateUnavailable('Candidate provenance or transformation failed') from error
        finally:
            with self._candidate_count_lock:
                self.candidate_counts['requests'] += 1
                self.candidate_counts[reason] += 1
                self.candidate_counts['seconds'] += time.monotonic()-began
