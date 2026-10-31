"""Original v29 CPU inference. No serialized vectors, device bridge or dot repair."""
from collections import Counter,OrderedDict
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
ROOT=BASE.parents[3]
V29=BASE/'metric-space-v29'
os.environ.update(CUDA_VISIBLE_DEVICES='-1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
                  TOKENIZERS_PARALLELISM='false',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
sys.path.insert(0,str(ROOT/'models/qwen35_runtime'))
import numpy as np
import torch


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def verify_dependencies(manifest):
    for name,expected in manifest.items():
        path=(ROOT/name).resolve()
        assert path.is_relative_to(ROOT.resolve()) and sha(path)==expected


class DirectScorer:
    def __init__(self,arm):
        assert arm in ('pristine','learned') and not torch.cuda.is_initialized()
        recipe=read(V29/'RECIPE.json')
        assert sha(V29/'RECIPE.json')=='8dcd11744b0620a75cd40ca03446e08e13f7a0b92b34389c2fc951575fa9365a'
        verify_dependencies(recipe['dependencies_sha256'])
        verify_dependencies(read(V29/'prepared/SOURCE_FREEZE.json')['dependencies_sha256'])
        import transformers
        assert sys.version_info[:2]==(3,10)
        assert (torch.__version__,np.__version__,transformers.__version__)==tuple(recipe['runtime'][k] for k in ('torch','numpy','transformers'))
        torch.set_num_threads(2)
        torch.use_deterministic_algorithms(True)
        self.model_module=load('cpu_v36_original_metric_model',V29/'metric_model.py')
        self.encoder=self.model_module.MetricEncoder(device='cpu')
        adapter=None
        if arm=='pristine':
            torch.manual_seed(recipe['seed'])
            self.encoder.inject()
            self.encoder.bert.requires_grad_(False)
            self.encoder.linear.requires_grad_(False)
        else:
            result=read(V29/'run-step80/RESULT.json')
            assert result['source_gate']['passed']
            assert read(V29/'run-step80/completion.json')['result_sha256']==sha(V29/'run-step80/RESULT.json')
            adapter=result['model_identity']['adapter_sha256']
            assert adapter=='d86e773035f920b9d5dc23ba91e4c802dfcbf6d897813029b012057d62316619'
            self.encoder.load(V29/'run-step80/adapter-step80.safetensors',adapter,
                recipe_sha256=sha(V29/'RECIPE.json'),prepared_sha256=sha(V29/'prepared/RESULT.json'))
        self.cache=OrderedDict()
        self.cache_bytes=0
        self.usage=Counter()
        self.identity=dict(profile='original-FP32-CPU-reference-v36',arm=arm,device='cpu',
            base_sha256=self.model_module.BASE_SHA,adapter_sha256=adapter,model_source_sha256=sha(V29/'metric_model.py'),
            direct_scorer_sha256=sha(Path(__file__)),dot_dtype='float32',sum_dtype='float64',query_positions=32,
            document_window=177,document_stride=145,attention='eager',adapter_form='unmerged',threads=2,
            document_cache='process-only original CPU tensors; no serialization or foreign cache import',cache_byte_limit=256*1024**2,
            GPU_equivalence_qualified=False,prior_GPU_equivalence_failure_preserved=True,
            torch=torch.__version__,numpy=np.__version__,transformers=transformers.__version__)

    def eligible(self,query):
        return isinstance(query,str) and not re.search(r'[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]',query) and len(self.encoder.tokenizer.encode(query,add_special_tokens=False,verbose=False))<=29

    def score(self,query,bodies):
        assert self.eligible(query) and not torch.cuda.is_initialized()
        unique=list(dict.fromkeys(bodies))
        values={}
        missing=[]
        for body in unique:
            key=hashlib.sha256(body.encode()).hexdigest()
            if key in self.cache:
                values[body]=self.cache[key]
                self.cache.move_to_end(key)
                self.usage['memory_hits']+=1
            else:
                missing.append(body)
        with torch.inference_mode():
            query_vectors,documents=self.encoder.encode_texts(query,missing)
            for body,vectors in zip(missing,documents):
                assert vectors.device.type=='cpu' and vectors.dtype==torch.float32 and torch.isfinite(vectors).all()
                values[body]=vectors
                size=vectors.numel()*vectors.element_size()
                if size<=self.identity['cache_byte_limit']:
                    while self.cache and self.cache_bytes+size>self.identity['cache_byte_limit']:
                        unused,old=self.cache.popitem(last=False)
                        self.cache_bytes-=old.numel()*old.element_size()
                    self.cache[hashlib.sha256(body.encode()).hexdigest()]=vectors
                    self.cache_bytes+=size
                self.usage['new_document_encodings']+=1
            scores=[self.model_module.score_one(query_vectors,values[body]) for body in bodies]
            result=torch.stack(scores).numpy() if scores else np.zeros(0,dtype=np.float64)
        assert result.dtype==np.float64 and result.shape==(len(bodies),) and np.isfinite(result).all()
        assert not torch.cuda.is_initialized()
        self.usage['queries']+=1
        self.usage['requested_documents']+=len(bodies)
        return result

    def close(self):
        self.cache.clear()
        self.cache_bytes=0
