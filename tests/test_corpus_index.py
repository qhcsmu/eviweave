import unittest
from eviweave.experimental import corpus_index as m
import re
from types import SimpleNamespace
import numpy as np

class NominationTest(unittest.TestCase):
    def test_independent_source_recall_and_stable_native_order(self):
        rows=[dict(source_id=str(i)) for i in range(160)]
        scores=[0.0]*160;scores[155]=2;scores[20]=1
        ranked=list(range(160));out,trace=m.nominate(ranked,rows,scores)
        self.assertEqual(out[:3],[0,155,1]);self.assertEqual(trace['novel'],[155])
        self.assertEqual([i for i in out if i!=155],[i for i in ranked if i!=155])
        self.assertEqual(set(out),set(ranked));self.assertEqual(len(out),len(ranked))
    def test_source_is_not_novel_if_another_chunk_already_in_pool(self):
        rows=[dict(source_id=str(i)) for i in range(160)];rows[155]['source_id']='20'
        scores=[0.0]*160;scores[155]=2
        ranked=list(range(160));out,trace=m.nominate(ranked,rows,scores)
        self.assertEqual(out,ranked);self.assertEqual(trace['novel'],[])
    def test_invalid_scores_fail_closed(self):
        with self.assertRaises(ValueError):m.nominate([0],[dict(source_id='a')],[float('nan')])
    def test_native_rule_is_restored_when_packing_would_displace_it(self):
        rows=[dict(source_id=str(i),content='RULE' if i==1 else 'text',role='user') for i in range(160)]
        class Parent:
            def __init__(self):pass
            def ranked(self,index,query,options,mode,*,return_document_prior=False):return (list(range(160)),False)
            def search(self,*,user_id,query,top_k,options,mode):
                order,_=self.ranked(SimpleNamespace(rows=rows),query,options,mode,return_document_prior=True)
                return [dict(id=str(i),content=rows[i]['content']) for i in order[:2]]
        class Scorer:
            def eligible(self,query):return True
            def token_scores(self,query,texts):
                values=np.zeros((160,2),np.float32);values[155]=1;return values
        cls=m.memory_store_class(SimpleNamespace(MemoryStore=Parent),re.compile('MULTI'),re.compile('RULEQUERY'),re.compile('RULE'))
        store=cls(scorer=Scorer())
        hits=store.search(user_id='synthetic',query='query',mode='query_document_evidence')
        self.assertEqual([x['id'] for x in hits],['0','1'])
        self.assertFalse(store.local.trace['applied'])
        self.assertEqual(store.local.trace['reason'],'rule_span_preservation_fallback')

if __name__=='__main__':unittest.main()
