"""Small supervised retrieval adapters; no generator or source rewriting."""
import hashlib,math
from pathlib import Path
import torch
from torch import nn
from safetensors import safe_open
from safetensors.torch import load_file,save_file

TARGETS=tuple(f'encoder.layer.{layer}.attention.self.{name}' for layer in (8,9,10,11) for name in ('query','value'))
BASE_SHA='3f58890b1dfdfec066ef12ba431fa9d56992da9e30a53489242c4156e37e9017'


class LoRALinear(nn.Module):
    def __init__(self,base,rank=8,alpha=16):
        super().__init__();self.base=base;self.scale=alpha/rank
        self.A=nn.Parameter(torch.empty(rank,base.in_features,device=base.weight.device,dtype=torch.float32))
        self.B=nn.Parameter(torch.zeros(base.out_features,rank,device=base.weight.device,dtype=torch.float32))
        nn.init.kaiming_uniform_(self.A,a=math.sqrt(5))
        self.base.requires_grad_(False)
    def forward(self,x):
        update=nn.functional.linear(nn.functional.linear(x.float(),self.A),self.B)
        return self.base(x)+update.to(x.dtype)*self.scale


def inject(bert):
    bert.requires_grad_(False)
    for name in TARGETS:
        parent,attribute=name.rsplit('.',1);owner=bert.get_submodule(parent)
        setattr(owner,attribute,LoRALinear(getattr(owner,attribute)))


def save_adapter(path,bert,linear,*,step):
    values={'projection.weight':linear.weight.detach().cpu().float().contiguous()}
    for name in TARGETS:
        module=bert.get_submodule(name)
        values[name+'.A']=module.A.detach().cpu().float().contiguous()
        values[name+'.B']=module.B.detach().cpu().float().contiguous()
    save_file(values,str(path),metadata={'base_sha256':BASE_SHA,'rank':'8','alpha':'16',
                                        'step':str(step),'features':'original-role-header-v1',
                                        'training_source':'PersonaMem-v2native public train/val; benchmark personas excluded'})
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def apply_adapter(bert,linear,path,expected_sha):
    if not expected_sha or hashlib.sha256(Path(path).read_bytes()).hexdigest()!=expected_sha:
        raise ValueError('Retrieval adapter hash mismatch')
    with safe_open(str(path),framework='pt',device='cpu') as f:metadata=f.metadata()
    if (metadata.get('base_sha256'),metadata.get('rank'),metadata.get('alpha'),metadata.get('features'))!=(BASE_SHA,'8','16','original-role-header-v1'):
        raise ValueError('Unsupported retrieval adapter identity')
    values=load_file(str(path),device='cpu')
    expected={'projection.weight'}|{name+suffix for name in TARGETS for suffix in ('.A','.B')}
    if set(values)!=expected or not all(torch.isfinite(v).all() for v in values.values()):
        raise ValueError('Invalid retrieval adapter tensors')
    if values['projection.weight'].shape!=linear.weight.shape:
        raise ValueError('Invalid retrieval projection shape')
    with torch.no_grad():
        linear.weight.copy_(values['projection.weight'])
        for name in TARGETS:
            target=bert.get_submodule(name);a,b=values[name+'.A'],values[name+'.B']
            if tuple(a.shape)!=(8,target.in_features) or tuple(b.shape)!=(target.out_features,8):
                raise ValueError('Invalid retrieval adapter shape')
            target.weight.add_(b@a,alpha=2.0)
