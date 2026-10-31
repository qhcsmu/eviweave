"""One differentiable FP32/body/all32 encoder for both fit and inference."""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import string
import sys

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
ROOT = BASE.parents[3]
sys.path.insert(0, str(ROOT / 'models/qwen35_runtime'))
import torch
from torch import nn

MODEL = ROOT / 'models/colbertv2.0'
BASE_SHA = '3f58890b1dfdfec066ef12ba431fa9d56992da9e30a53489242c4156e37e9017'
FEATURES = 'raw-body-all32-fp32-unmerged-v29'
TARGETS = tuple(f'encoder.layer.{i}.attention.self.{name}' for i in (8,9,10,11) for name in ('query','value'))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def check_lock(token, pid):
    owner = json.loads((BASE.parent / 'local-model.lock/owner.json').read_text(encoding='utf-8'))
    if not token or owner.get('token') != token or owner.get('pid') != pid or owner.get('direction') != '03-token-retrieval':
        raise RuntimeError('Required parent GPU lock ownership is absent or changed')


def document_windows(raw, special):
    start = 0
    result = []
    while True:
        result.append([special['cls'], 2] + list(raw[start:start+177]) + [special['sep']])
        if start+177 >= len(raw):
            return result
        start += 145


def query_window(raw, special):
    if len(raw) > 29:
        raise ValueError('Query exceeds complete 32-position contract')
    ids = [special['cls'], 1] + list(raw) + [special['sep']]
    return ids + [special['mask']]*(32-len(ids)), [1]*len(ids) + [0]*(32-len(ids))


class LoRALinear(nn.Module):
    def __init__(self, original):
        super().__init__()
        self.base = original
        self.base.requires_grad_(False)
        self.A = nn.Parameter(torch.empty(8, original.in_features, device=original.weight.device, dtype=torch.float32))
        self.B = nn.Parameter(torch.zeros(original.out_features, 8, device=original.weight.device, dtype=torch.float32))
        nn.init.kaiming_uniform_(self.A, a=math.sqrt(5))

    def forward(self, x):
        return self.base(x) + nn.functional.linear(nn.functional.linear(x, self.A), self.B)*2.0


def score_one(query, document):
    if query.dtype != torch.float32 or document.dtype != torch.float32 or query.shape != (32,128) or document.ndim != 2 or document.shape[1] != 128 or not len(document):
        raise ValueError('Expected complete32 FP32 query and nonempty FP32 document')
    return (document @ query.T).max(dim=0).values.to(torch.float64).sum()


def positive_loss(logits, positive_mask):
    if logits.ndim != 2 or logits.dtype != torch.float64 or positive_mask.dtype != torch.bool or positive_mask.shape != logits.shape:
        raise ValueError('Loss contract mismatch')
    if not positive_mask.any(1).all() or positive_mask.all(1).any() or not torch.isfinite(logits).all():
        raise ValueError('Each query requires positive and negative finite logits')
    return -(torch.log_softmax(logits, dim=1)*positive_mask).sum(1).div(positive_mask.sum(1)).mean()


class MetricEncoder:
    def __init__(self, *, device='cpu', lock_token=None, owner_pid=None):
        from safetensors.torch import load_file
        from transformers import AutoTokenizer, BertConfig, BertModel
        if device.startswith('cuda'):
            check_lock(lock_token, owner_pid)
        self.device = device
        self.lock_token = lock_token
        self.owner_pid = owner_pid
        if sha(MODEL/'model.safetensors') != BASE_SHA:
            raise ValueError('Pristine base hash mismatch')
        settings = json.loads((MODEL/'artifact.metadata').read_text())
        assert (settings['dim'], settings['query_maxlen'], settings['doc_maxlen'], settings['attend_to_mask_tokens']) == (128,32,180,False)
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL, local_files_only=True, trust_remote_code=False)
        config = BertConfig.from_json_file(str(MODEL/'config.json'))
        config._attn_implementation = 'eager'
        self.bert = BertModel(config)
        weights = load_file(str(MODEL/'model.safetensors'), device='cpu')
        bert = {k[5:]: v for k,v in weights.items() if k.startswith('bert.')}
        positions = bert.pop('embeddings.position_ids', None)
        if positions is not None:
            assert torch.equal(positions, torch.arange(config.max_position_embeddings).unsqueeze(0))
        self.bert.load_state_dict(bert, strict=True)
        self.linear = nn.Linear(config.hidden_size,128,bias=False)
        self.linear.load_state_dict({'weight': weights['linear.weight']}, strict=True)
        assert set(weights) == {k for k in weights if k.startswith('bert.')} | {'linear.weight'}
        self.bert.to(device=device, dtype=torch.float32).eval().requires_grad_(False)
        self.linear.to(device=device, dtype=torch.float32).eval().requires_grad_(False)
        self.special = {n: getattr(self.tokenizer,n+'_token_id') for n in ['cls','sep','mask','pad']}
        self.punctuation = {self.tokenizer.encode(p,add_special_tokens=False)[0] for p in string.punctuation}
        self.usage = Counter()
        self.injected = False
        self.adapter_sha256 = None

    def inject(self):
        if self.injected:
            raise RuntimeError('Adapter already injected')
        for name in TARGETS:
            parent, attr = name.rsplit('.',1)
            owner = self.bert.get_submodule(parent)
            setattr(owner, attr, LoRALinear(getattr(owner,attr)))
        self.injected = True

    def trainable(self):
        if not self.injected:
            raise RuntimeError('Inject before enabling training')
        self.linear.requires_grad_(True)
        lora = [p for p in self.bert.parameters() if p.requires_grad]
        projection = list(self.linear.parameters())
        assert sum(p.numel() for p in lora+projection) == 196608
        return lora, projection

    def forward(self, ids, attention):
        if self.device.startswith('cuda'):
            check_lock(self.lock_token, self.owner_pid)
        ids = torch.tensor(ids, device=self.device, dtype=torch.long)
        attention = torch.tensor(attention, device=self.device, dtype=torch.long)
        hidden = self.bert(input_ids=ids, attention_mask=attention).last_hidden_state
        result = nn.functional.normalize(self.linear(hidden), p=2, dim=-1)
        assert result.dtype == torch.float32
        return result

    def queries(self, token_rows):
        result = []
        dummy = query_window([], self.special)
        for start in range(0,len(token_rows),4):
            batch = [query_window(raw,self.special) for raw in token_rows[start:start+4]]
            valid = len(batch)
            batch += [dummy]*(4-valid)
            result.extend(self.forward([x[0] for x in batch],[x[1] for x in batch])[:valid].unbind())
            self.usage['query_forward_batches'] += 1
            self.usage['query_padded_sequences'] += 4-valid
        self.usage['query_encodings'] += len(token_rows)
        return result

    def documents(self, token_rows):
        windows, owners = [], []
        for n,raw in enumerate(token_rows):
            part = document_windows(raw,self.special)
            windows.extend(part)
            owners.extend([n]*len(part))
        parts = [[] for _ in token_rows]
        dummy = [self.special['cls'],2,self.special['sep']]
        for start in range(0,len(windows),8):
            batch = windows[start:start+8]
            valid = len(batch)
            batch += [dummy]*(8-valid)
            ids = [x+[self.special['pad']]*(180-len(x)) for x in batch]
            attention = [[int(i != self.special['pad']) for i in row] for row in ids]
            vectors = self.forward(ids,attention)
            for j,raw in enumerate(batch[:valid]):
                keep = [i for i,t in enumerate(raw) if t != self.special['pad'] and t not in self.punctuation]
                parts[owners[start+j]].append(vectors[j,keep])
            self.usage['document_forward_batches'] += 1
            self.usage['document_padded_sequences'] += 8-valid
        self.usage['document_encodings'] += len(token_rows)
        self.usage['document_windows'] += len(windows)
        return [torch.cat(p,dim=0) for p in parts]

    def encode_texts(self, query, bodies):
        if not isinstance(query,str) or re.search(r'[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]',query):
            raise ValueError('Unsupported complete-query contract')
        raw = self.tokenizer.encode(query,add_special_tokens=False,verbose=False)
        if len(raw)>29:
            raise ValueError('Unsupported complete-query contract')
        q = self.queries([raw])[0]
        docs = self.documents([self.tokenizer.encode(body,add_special_tokens=False,verbose=False) for body in bodies])
        return q, docs

    def save(self, path, *, step, recipe_sha256, prepared_sha256):
        from safetensors.torch import save_file
        assert self.injected
        values = {'projection.weight': self.linear.weight.detach().cpu().contiguous()}
        for n in TARGETS:
            m = self.bert.get_submodule(n)
            values.update({n+'.A':m.A.detach().cpu().contiguous(),n+'.B':m.B.detach().cpu().contiguous()})
        assert all(x.dtype == torch.float32 and torch.isfinite(x).all() for x in values.values())
        save_file(values,str(path),metadata=dict(base_sha256=BASE_SHA,rank='8',alpha='16',step=str(step),features=FEATURES,
                  recipe_sha256=recipe_sha256,prepared_sha256=prepared_sha256,training_source='v9-retained-only-pristine-init'))
        return sha(path)

    def load(self,path,expected_sha,*,recipe_sha256,prepared_sha256):
        from safetensors import safe_open
        from safetensors.torch import load_file
        if sha(path) != expected_sha:
            raise ValueError('Adapter hash mismatch')
        with safe_open(str(path), framework='pt',device='cpu') as f:
            meta = f.metadata()
        expected_meta = dict(base_sha256=BASE_SHA,rank='8',alpha='16',step='80',features=FEATURES,
                             recipe_sha256=recipe_sha256,prepared_sha256=prepared_sha256,training_source='v9-retained-only-pristine-init')
        if meta != expected_meta:
            raise ValueError('Adapter metadata mismatch')
        if not self.injected:
            self.inject()
        values = load_file(str(path),device='cpu')
        targets = {'projection.weight':self.linear.weight}
        for n in TARGETS:
            m = self.bert.get_submodule(n)
            targets.update({n+'.A':m.A,n+'.B':m.B})
        if set(values) != set(targets) or any(v.dtype!=torch.float32 or v.shape!=targets[n].shape or not torch.isfinite(v).all() for n,v in values.items()):
            raise ValueError('Adapter tensor contract mismatch')
        with torch.no_grad():
            for n,v in values.items():
                targets[n].copy_(v)
        self.bert.requires_grad_(False)
        self.linear.requires_grad_(False)
        self.adapter_sha256 = expected_sha
