"""Full native-chunk learned candidate generation; no evaluation metadata access."""
import threading
import numpy as np

TOP_SOURCES=10
OLD_POOL=128

def nominate(ranked,rows,scores):
    values=np.asarray(scores,dtype=np.float32)
    if len(values)!=len(rows) or not np.isfinite(values).all():raise ValueError('Invalid full-index score vector')
    rank={i:p for p,i in enumerate(ranked)}
    order=sorted(ranked,key=lambda i:(-float(values[i]),rank[i]))
    seen=set();champions=[]
    for i in order:
        sid=rows[i]['source_id']
        if sid in seen:continue
        seen.add(sid);champions.append(i)
        if len(champions)==TOP_SOURCES:break
    existing={rows[i]['source_id'] for i in ranked[:OLD_POOL]}
    novel=[i for i in champions if rows[i]['source_id'] not in existing]
    result=[];inserted=set()
    for p,i in enumerate(ranked):
        if i not in inserted:result.append(i);inserted.add(i)
        if p<len(novel) and novel[p] not in inserted:result.append(novel[p]);inserted.add(novel[p])
    return result,dict(learned_source_champions=champions,novel=novel,native_best_ranks=[rank[i]+1 for i in novel])

def memory_store_class(base,multi,rule,standing_rule):
    class CorpusStore(base.MemoryStore):
        def __init__(self,*args,scorer=None,**kwargs):
            self.scorer=scorer;self.local=threading.local();super().__init__(*args,**kwargs)
        def search(self,*,user_id,query,top_k=100,options=None,mode='hybrid_window'):
            self.local.probe=True
            try:original=super().search(user_id=user_id,query=query,top_k=top_k,options=options,mode=mode)
            finally:self.local.probe=False
            new=super().search(user_id=user_id,query=query,top_k=top_k,options=options,mode=mode)
            required={(x['id'],x['content']) for x in original if standing_rule.search(x['content'])}
            present={(x['id'],x['content']) for x in new}
            self.local.trace['preserved_native_rule_hits']=len(required)
            if not required<=present:
                self.local.trace.update(applied=False,reason='rule_span_preservation_fallback')
                return original
            return new
        def ranked(self,index,query,options,mode,*,return_document_prior=False):
            result=super().ranked(index,query,options,mode,return_document_prior=True)
            ranked,document=result;trace=dict(applied=False,rows=len(index.rows),reason='native_mode')
            if getattr(self.local,'probe',False):trace['reason']='native_probe'
            elif mode=='query_document_evidence':
                if document:trace['reason']='native_document'
                elif multi.search(query):trace['reason']='multi_event_query'
                elif rule.search(query):trace['reason']='rule_query'
                elif not self.scorer.eligible(query):trace['reason']='unsupported_query'
                else:
                    scores=self.scorer.token_scores(query,[x['content'] for x in index.rows])
                    if scores.shape[1]<2:trace['reason']='short_query'
                    else:
                        ranked,detail=nominate(ranked,index.rows,scores.mean(axis=1))
                        trace.update(detail,reason='independent_candidates' if detail['novel'] else 'no_novel_champion',applied=bool(detail['novel']))
            self.local.trace=trace
            return (ranked,document) if return_document_prior else ranked
    return CorpusStore

def disk_scorer_class(parent,run):
    import hashlib
    import sqlite3
    class DiskScorer(parent):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            self.disk=sqlite3.connect(run/'token-index.sqlite3')
            self.disk.execute('create table if not exists metadata(identity text primary key)')
            rows=self.disk.execute('select identity from metadata').fetchall()
            if rows and rows!=[(self.identity,)]:raise ValueError('Index model identity mismatch')
            self.disk.execute('insert or ignore into metadata values(?)',(self.identity,))
            self.disk.execute('create table if not exists tokens(hash text primary key,length integer,data blob)');self.disk.commit()
            self.index_hits=0
        def _documents(self,texts):
            found={};missing={}
            for text in texts:
                key=hashlib.sha256(text.encode()).hexdigest()
                row=self.disk.execute('select length,data from tokens where hash=?',(key,)).fetchone()
                if row:found[key]=np.frombuffer(row[1],np.float16).reshape(row[0],128).copy();self.index_hits+=1
                else:missing[key]=text
            keys=list(missing)
            for start in range(0,len(keys),64):
                batch=keys[start:start+64]
                for key,value in zip(batch,super()._documents([missing[k] for k in batch])):
                    found[key]=value
                    self.disk.execute('insert into tokens values(?,?,?)',(key,len(value),value.astype(np.float16).tobytes()))
                self.disk.commit()
            return [found[hashlib.sha256(text.encode()).hexdigest()] for text in texts]
    return DiskScorer
