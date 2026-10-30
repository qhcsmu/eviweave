"""Pinned, local, non-generative ColBERTv2 token encodings and MaxSim.

Independent inference adapter for the MIT ColBERTv2 checkpoint. Query markers,
masked augmentation and document punctuation masking follow the upstream
implementation. We cover every document token with overlapping trained-length
windows rather than silently truncating original chunks. This is a bounded
reranker, not the upstream PLAID search engine or a trained verifier.
"""
from __future__ import annotations

import hashlib
import json
import re
import string
import threading
from collections import OrderedDict
from pathlib import Path

import numpy as np


MODEL_SHA='3f58890b1dfdfec066ef12ba431fa9d56992da9e30a53489242c4156e37e9017'
CJK=re.compile(r'[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]')


def maxsim(query,documents):
    """Exact variable-length token MaxSim; numpy reference for verification."""
    return np.asarray([(np.asarray(d,dtype=np.float32)@np.asarray(query,dtype=np.float32).T)
                       .max(axis=0).sum() for d in documents],dtype=np.float32)


class LocalColBERT:
    def __init__(self,path,*,device='cuda:0',batch_size=16,cache_bytes=134217728,
                 adapter_path=None,adapter_sha256=None):
        import torch
        from safetensors.torch import load_file
        from transformers import AutoTokenizer,BertConfig,BertModel
        self.torch=torch;self.path=Path(path);self.device=device
        self.batch_size=batch_size;self.limit=cache_bytes;self.lock=threading.RLock()
        self.cache=OrderedDict();self.cache_size=0
        self.usage={'query_encodings':0,'document_encodings':0,'document_windows':0,'cache_hits':0}
        if hashlib.sha256((self.path/'model.safetensors').read_bytes()).hexdigest()!=MODEL_SHA:
            raise ValueError('ColBERT checkpoint hash mismatch')
        config=BertConfig.from_json_file(str(self.path/'config.json'))
        settings=json.loads((self.path/'artifact.metadata').read_text())
        if (settings['dim'],settings['query_maxlen'],settings['doc_maxlen'],settings['attend_to_mask_tokens'])!=(128,32,180,False):
            raise ValueError('Unsupported ColBERT checkpoint configuration')
        self.tokenizer=AutoTokenizer.from_pretrained(self.path,local_files_only=True,trust_remote_code=False)
        weights=load_file(str(self.path/'model.safetensors'),device='cpu')
        self.bert=BertModel(config)
        bert_weights={k[5:]:v for k,v in weights.items() if k.startswith('bert.')}
        # Older Transformers persisted this deterministic buffer. Validate its
        # exact value; do not ignore an unmatched learned tensor or parameter.
        position_ids=bert_weights.pop('embeddings.position_ids',None)
        if position_ids is not None and not torch.equal(
                position_ids,torch.arange(config.max_position_embeddings).unsqueeze(0)):
            raise ValueError('Unexpected legacy position buffer')
        self.bert.load_state_dict(bert_weights,strict=True)
        self.linear=torch.nn.Linear(config.hidden_size,128,bias=False)
        self.linear.load_state_dict({'weight':weights['linear.weight']},strict=True)
        if set(weights)-{k for k in weights if k.startswith('bert.')}-{'linear.weight'}:
            raise ValueError('Unexpected checkpoint tensors')
        if adapter_path is not None:
            from .lora_adapter import apply_adapter
            apply_adapter(self.bert,self.linear,adapter_path,adapter_sha256)
        dtype=torch.float16 if device.startswith('cuda') else torch.float32
        self.dtype=dtype
        self.bert.to(device=device,dtype=dtype).eval();self.linear.to(device=device,dtype=dtype).eval()
        self.punctuation={self.tokenizer.encode(p,add_special_tokens=False)[0] for p in string.punctuation}
        self.identity=f'colbertv2:{MODEL_SHA}:query32:doc180-full-overlap32:d16-q{16 if dtype==torch.float16 else 32}'
        if adapter_path is not None:self.identity+=':adapter:'+adapter_sha256

    def eligible(self,query):
        # English-only pretrained model. Avoid silently discarding long queries.
        return not CJK.search(query) and len(self.tokenizer.encode(query,add_special_tokens=False))<=29

    def _forward(self,ids,attention):
        t=self.torch
        with t.inference_mode():
            hidden=self.bert(input_ids=ids.to(self.device),attention_mask=attention.to(self.device)).last_hidden_state
            return t.nn.functional.normalize(self.linear(hidden).float(),p=2,dim=-1).to(self.dtype)

    def _query(self,text):
        t=self.torch;tok=self.tokenizer
        raw=tok.encode(text,add_special_tokens=False)
        if len(raw)>29:raise ValueError('Long query must use the original retriever')
        ids=[tok.cls_token_id,1]+raw+[tok.sep_token_id]
        attention=[1]*len(ids)+[0]*(32-len(ids))
        ids += [tok.mask_token_id]*(32-len(ids))
        self.usage['query_encodings']+=1
        return self._forward(t.tensor([ids]),t.tensor([attention]))[0]

    def _documents(self,texts):
        t=self.torch;tok=self.tokenizer
        windows=[];owners=[]
        for number,text in enumerate(texts):
            raw=tok.encode(text,add_special_tokens=False)
            start=0
            while True:
                content=raw[start:start+177]
                windows.append([tok.cls_token_id,2]+content+[tok.sep_token_id]);owners.append(number)
                if start+177>=len(raw):break
                start+=145
        parts=[[] for _ in texts]
        for start in range(0,len(windows),self.batch_size):
            batch=windows[start:start+self.batch_size];length=max(map(len,batch))
            ids=t.tensor([x+[tok.pad_token_id]*(length-len(x)) for x in batch])
            attention=(ids!=tok.pad_token_id).long()
            vectors=self._forward(ids,attention).cpu()
            for n,raw in enumerate(batch):
                keep=[i for i,x in enumerate(raw) if x!=tok.pad_token_id and x not in self.punctuation]
                parts[owners[start+n]].append(vectors[n,keep].numpy().astype(np.float16))
        self.usage['document_encodings']+=len(texts);self.usage['document_windows']+=len(windows)
        return [np.concatenate(p,axis=0) for p in parts]

    def score(self,query,documents):
        if not self.eligible(query):raise ValueError('Unsupported query must retain baseline behavior')
        with self.lock:
            keys=[hashlib.sha256(x.encode('utf8')).hexdigest() for x in documents]
            missing={key:text for key,text in zip(keys,documents) if key not in self.cache}
            # Keep current-call values even if this call exceeds the cache cap.
            current={key:self.cache[key] for key in keys if key in self.cache}
            self.usage['cache_hits']+=len(keys)-len(missing)
            values=self._documents(list(missing.values())) if missing else []
            for key,value in zip(missing,values):
                current[key]=value
                self.cache[key]=value;self.cache_size+=value.nbytes
            for key in keys:
                if key in self.cache:self.cache.move_to_end(key)
            while self.cache_size>self.limit and self.cache:
                _,value=self.cache.popitem(last=False);self.cache_size-=value.nbytes
            q=self._query(query);t=self.torch;result=[]
            for start in range(0,len(keys),24):
                batch=[current[k] for k in keys[start:start+24]]
                length=max(len(x) for x in batch)
                padded=np.zeros((len(batch),length,128),dtype=np.float16)
                valid=np.zeros((len(batch),length),dtype=bool)
                for i,value in enumerate(batch):padded[i,:len(value)]=value;valid[i,:len(value)]=True
                with t.inference_mode():
                    scores=t.as_tensor(padded,device=self.device,dtype=self.dtype)@q.T
                    scores.masked_fill_(~t.as_tensor(valid,device=self.device).unsqueeze(-1),-9999)
                    result.extend(scores.max(dim=1).values.float().sum(dim=1).cpu().tolist())
            return np.asarray(result,dtype=np.float32)
