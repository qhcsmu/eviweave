"""Search-only transformation; never accepts a benchmark case or reader budget."""
from hashlib import sha256
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'metric-space-v33-timestamp-credit'))
from temporal_headers import compact_units, expand_units


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def token_view(tokenizer, units):
    text = '\n\n'.join(u['header']+u['body'] for u in units)
    encoded = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True,
                        truncation=False, verbose=False)
    offsets = encoded['offset_mapping']
    first = [None]*len(text)
    last = [None]*len(text)
    for number, (start, end) in enumerate(offsets):
        for char in range(start, end):
            if first[char] is None:
                first[char] = number
            last[char] = number
    spans = []
    position = 0
    for unit in units:
        start = position+len(unit['header'])
        end = start+len(unit['body'])
        spans.append((start, end))
        position = end+2
    return dict(tokens=len(encoded['input_ids']), text=text, first=first, last=last, body_spans=spans)


def no_body_later(before, after, origins):
    original = 0
    for index, origin in enumerate(origins):
        if origin is None:
            continue
        if origin != original:
            return False
        a, b = before['body_spans'][original]
        c, d = after['body_spans'][index]
        if b-a != d-c:
            return False
        for old, new in zip(range(a,b), range(c,d)):
            for key in ('first','last'):
                if before[key][old] is None or after[key][new] is None or after[key][new] > before[key][old]:
                    return False
        original += 1
    return original == len(before['body_spans'])


def proposal(native, witness, boundary):
    canonical = native[:boundary]+[witness]+native[boundary:]
    compact = compact_units(canonical)
    if expand_units(compact) != canonical:
        raise ValueError('Canonical source/header round trip failed')
    origins = list(range(boundary))+[None]+list(range(boundary,len(native)))
    return canonical, compact, origins


def as_hits(native_hits, compact, boundary):
    """The anchor and witness are one actual Search hit; never flatten for packing."""
    hits = []
    lineage = []
    for native_index, old in enumerate(native_hits):
        index = native_index if native_index < boundary else native_index+1
        unit = compact[index]
        content = unit['header']+unit['body']
        parts = [dict(segment=index, start=0, end=len(content))]
        item = {**old,'content':content}
        if native_index == boundary-1:
            copy = compact[boundary]
            copy_text = copy['header']+copy['body']
            parts.append(dict(segment=boundary,start=len(content)+2,end=len(content)+2+len(copy_text)))
            item['content'] += '\n\n'+copy_text
            item['id'] = 'eviweave-composite-'+digest(dict(anchor=old['id'],segments=[unit,copy]))
        hits.append(item)
        lineage.append(parts)
    assert len(hits) == len(native_hits) and len({h['id'] for h in hits}) == len(hits)
    assert '\n\n'.join(h['content'] for h in hits) == '\n\n'.join(u['header']+u['body'] for u in compact)
    return hits,lineage


def feasible(native, native_hits, source_pool, tokenizer, top_k=100, context_chars=24000):
    """Each source gets one ledger-selected boundary and one global check."""
    if len(native) != len(native_hits):
        raise ValueError('Original Search trace length mismatch')
    if not native:
        return [],dict(reason='empty_native_Search',proposal_tests=0)
    for unit,hit in zip(native,native_hits):
        if unit['header']+unit['body'] != hit['content']:
            raise ValueError('Native unit is not the real Search hit')
    before = token_view(tokenizer,native)
    compact = compact_units(native)
    credit = token_view(tokenizer,compact)
    if credit['tokens'] >= before['tokens']:
        return [],dict(reason='no_timestamp_token_credit',proposal_tests=0,
                       original_tokens=before['tokens'],compact_tokens=credit['tokens'])
    # A fixed per-hit ledger chooses a boundary without testing candidate positions.
    # Whole-memory checks below reject any boundary interaction the ledger misses.
    ledger = []
    saved = 0
    for original,short in zip(native,compact):
        old = tokenizer.encode(original['header']+original['body']+'\n\n',add_special_tokens=False,verbose=False)
        new = tokenizer.encode(short['header']+short['body']+'\n\n',add_special_tokens=False,verbose=False)
        saved += len(old)-len(new)
        ledger.append(saved)
    first = {}
    for i,u in enumerate(native):
        first.setdefault(u['source_id'],i)
    admitted = []
    tests = 0
    rejects = {}
    def reject(reason):
        rejects[reason]=rejects.get(reason,0)+1
    # Each source is evaluated once in its fixed native128 order.
    seen = set()
    for source in source_pool:
        witness = source['unit']
        sid = witness['source_id']
        if sid in seen:
            raise ValueError('Source pool must contain distinct original sources')
        seen.add(sid)
        if sid not in first or first[sid] == 0:
            reject('source_has_no_earlier_Search_boundary')
            continue
        assert witness['start']==0 and witness['end']==len(witness['body'])
        cost = len(tokenizer.encode(witness['header']+witness['body']+'\n\n',add_special_tokens=False,verbose=False))
        boundary = next((i+1 for i,saved in enumerate(ledger[:first[sid]]) if saved>=cost),None)
        if boundary is None:
            reject('no_earlier_self_funded_boundary')
            continue
        tests += 1
        canonical,parts,origins = proposal(native,witness,boundary)
        # A composite requires one internal separator that counts as Search content.
        chars = sum(len(u['header'])+len(u['body']) for u in parts)+2
        if len(native_hits)>top_k or chars>context_chars:
            reject('Search_char_or_hit_limit')
            continue
        after = token_view(tokenizer,parts)
        if after['tokens']>before['tokens']:
            reject('memory_token_length_increase')
            continue
        if not no_body_later(before,after,origins):
            reject('original_body_character_moves_to_later_token')
            continue
        assert [u for u,origin in zip(canonical,origins) if origin is not None] == native
        hits,lineage = as_hits(native_hits,parts,boundary)
        admitted.append(dict(source_id=sid,native_rank=source['native_rank'],boundary=boundary,
             witness=witness,compact_segments=parts,origins=origins,hits=hits,hit_lineage=lineage,
             memory_tokens=after['tokens'],Search_chars=chars,Search_hit_count=len(hits),
             all_original_body_characters_no_later=True,all_original_raw_body_metadata_order_retained=True,
             Search_sha256=digest(hits)))
    return admitted,dict(proposal_tests=tests,rejections=rejects,original_tokens=before['tokens'],
                         compact_tokens=credit['tokens'],fixed_Source128_pool=len(source_pool))
