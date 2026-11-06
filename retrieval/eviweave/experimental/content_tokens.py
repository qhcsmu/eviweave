"""Reuse the pinned historical ColBERT encoder; expose content-token MaxSim."""
import hashlib
import time
import numpy as np


def scorer_class(historical, stopwords):
    class ResidualColBERT(historical.LocalColBERT):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            self.calls=[]

        def token_scores(self,query,documents):
            start=time.monotonic()
            if not self.eligible(query):
                raise ValueError('Unsupported query')
            raw=self.tokenizer.encode(query,add_special_tokens=False)
            columns=[p+2 for p,token in enumerate(raw)
                     if token not in self.punctuation
                     and self.tokenizer.convert_ids_to_tokens(token).removeprefix('##').casefold() not in stopwords]
            # Repeated query wordpieces get one dimension; no answer/option view.
            seen=set(); columns=[p for p in columns if not (raw[p-2] in seen or seen.add(raw[p-2]))]
            if len(columns)<2:
                return np.zeros((len(documents),len(columns)),np.float32)
            with self.lock:
                keys=[hashlib.sha256(text.encode()).hexdigest() for text in documents]
                missing={k:v for k,v in zip(keys,documents) if k not in self.cache}
                current={k:self.cache[k] for k in keys if k in self.cache}
                self.usage['cache_hits']+=len(keys)-len(missing)
                for key,value in zip(missing,self._documents(list(missing.values())) if missing else []):
                    current[key]=value; self.cache[key]=value; self.cache_size+=value.nbytes
                for key in keys:
                    if key in self.cache:self.cache.move_to_end(key)
                while self.cache_size>self.limit and self.cache:
                    _,value=self.cache.popitem(last=False);self.cache_size-=value.nbytes
                query_vectors=self._query(query)[columns]
                t=self.torch; result=[]
                for offset in range(0,len(keys),24):
                    batch=[current[k] for k in keys[offset:offset+24]]
                    length=max(len(x) for x in batch)
                    padded=np.zeros((len(batch),length,128),np.float16)
                    valid=np.zeros((len(batch),length),bool)
                    for p,value in enumerate(batch):
                        padded[p,:len(value)]=value;valid[p,:len(value)]=True
                    with t.inference_mode():
                        scores=t.as_tensor(padded,device=self.device,dtype=self.dtype)@query_vectors.T
                        scores.masked_fill_(~t.as_tensor(valid,device=self.device).unsqueeze(-1),-9999)
                        result.extend(scores.max(dim=1).values.float().cpu().tolist())
                self.calls.append(dict(documents=len(documents),dimensions=len(columns),seconds=time.monotonic()-start))
                return np.asarray(result,dtype=np.float32)
    return ResidualColBERT
