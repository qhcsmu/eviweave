"""Prepare independent release; switch m02 only after qualified model readiness."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
ROOT=BASE.parents[3]
sys.path.insert(0,str(BASE/'eviweave-v03-hourly'))
import official_probe as probe


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ssh(code):
    connection=read(BASE/'eviweave-v03-hourly/private/ssh-connection.json')
    result=subprocess.run(['ssh.exe','-i',connection['private_key'],'-p','22','-o','BatchMode=yes',
        '-o','IdentitiesOnly=yes','-o','ConnectTimeout=12','-o','StrictHostKeyChecking=yes',
        '-o','UserKnownHostsFile='+connection['hostkey_file'],'root@101.201.226.162',
        '/opt/memory-lab/venv/bin/python -'],input=code.encode(),capture_output=True,timeout=180)
    if result.returncode:
        raise RuntimeError('Remote deployment step failed; code '+str(result.returncode)+'; no secret output forwarded')
    return json.loads(result.stdout)


def account_idle(config):
    receipt=probe.get('/api/v1/evaluations?limit=100&offset=0',config)
    assert receipt['http_status']==200
    value=receipt['response']
    assert not value.get('next_offset')
    assert not any(j['status'] in probe.ACTIVE for j in value['evaluations'])
    legacy=probe.get('/eval-jobs/active',config)
    assert legacy['http_status']==200 and legacy['response'].get('jobs')==[]
    return dict(jobs_http_status=200,legacy_http_status=200,active_jobs=0)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['prepare','switch','rollback'])
    args=parser.parse_args()
    manifest=read(HERE/'MANIFEST.json')
    for name,expected in manifest['local_files_sha256'].items():
        assert sha(ROOT/name)==expected
    digest=sha(HERE/'MANIFEST.json')
    remote='/opt/memory-lab/releases/eviweave-v03-v36cpu-'+digest[:12]
    out=HERE/'deployments'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out.mkdir(parents=True,exist_ok=False)
    config=probe.credentials()
    receipt=dict(utc=datetime.now(timezone.utc).isoformat(),action=args.action,remote_release=remote,
                 manifest_sha256=digest,shared_source_modified=False,shared_venv_modified=False)
    if args.action=='prepare':
        incumbent=read(ROOT/'competition/runs/best32-incumbent-20261021/incumbent.json')
        frozen=read(ROOT/incumbent['historical_freeze'])
        files={name:(BASE/'exact32-source'/name).read_bytes() for name in frozen['source_files']}
        assert all(hashlib.sha256(files[name]).hexdigest()==expected for name,expected in frozen['source_files'].items())
        files.update({name:(HERE/name).read_bytes() for name in ('runtime_store.py','server.py')})
        encoded={name:base64.b64encode(value).decode() for name,value in files.items()}
        payload=dict(remote=remote,files=encoded,shared_expected=frozen['source_files'],manifest_sha256=digest)
        code='''import base64,hashlib,json,os,subprocess,sys,sysconfig
from pathlib import Path
p=PAYLOAD
root=Path(p['remote'])
assert root.is_absolute() and root.parent==Path('/opt/memory-lab/releases')
for name,expected in p['shared_expected'].items():
 assert hashlib.sha256((Path('/opt/memory-lab/source')/name).read_bytes()).hexdigest()==expected
root.mkdir(parents=True,exist_ok=True)
checks={}
for name,encoded in p['files'].items():
 path=(root/'source'/name).resolve()
 assert path.is_relative_to(root/'source')
 raw=base64.b64decode(encoded)
 path.parent.mkdir(parents=True,exist_ok=True)
 if path.exists():
  assert path.read_bytes()==raw
 else:
  with path.open('xb') as stream:stream.write(raw)
 checks[name]=hashlib.sha256(path.read_bytes()).hexdigest()
env=root/'venv'
if not env.exists():subprocess.run([sys.executable,'-m','venv','--without-pip',str(env)],check=True,capture_output=True)
pure=subprocess.run([str(env/'bin/python'),'-c','import sysconfig; print(sysconfig.get_paths()["purelib"])'],check=True,capture_output=True,text=True).stdout.strip()
pth=Path(pure)/'eviweave-readonly-dependencies.pth'
expected=sysconfig.get_paths()['purelib']+'\\n'
if pth.exists():assert pth.read_text()==expected
else:pth.write_text(expected)
test=subprocess.run([str(env/'bin/python'),'-c','import fastapi,numpy,uvicorn; print("ok")'],check=True,capture_output=True,text=True)
state=subprocess.run(['systemctl','show','memory-lab@m02.service','--property=MainPID','--property=ActiveState','--property=User','--property=Group','--property=WorkingDirectory'],check=True,capture_output=True,text=True).stdout
(root/'PREPARED.json').write_text(json.dumps(dict(manifest_sha256=p['manifest_sha256'],files_sha256=checks,dependencies_readonly_path=sysconfig.get_paths()['purelib']),indent=2)+'\\n')
print(json.dumps(dict(prepared=True,files=len(checks),independent_venv=True,dependencies_importable=test.stdout.strip()=='ok',shared_dependencies_readonly=True,systemd_metadata=dict(x.split('=',1) for x in state.splitlines() if '=' in x),service_restarted=False)))
'''.replace('PAYLOAD',repr(payload))
        receipt.update(ssh(code))
    elif args.action=='switch':
        receipt['idle_check']=account_idle(config)
        assert read(BASE/'deployment-v34/CPU_RUNTIME_CONTRACT/RESULT.json')['passed']
        assert read(BASE/'deployment-v34/CPU_RUNTIME_CONTRACT/PROCESS_EXIT.json')['exit_code']==0
        # The remote checks actual model/tunnel identity before touching m02.
        token=(HERE/'private/rpc-token.txt').read_text().strip()
        payload=dict(remote=remote,manifest_sha256=digest,token=token)
        code='''import hashlib,json,os,subprocess,time,urllib.request
from pathlib import Path
p=PAYLOAD
root=Path(p['remote'])
assert root.parent==Path('/opt/memory-lab/releases')
prepared=json.loads((root/'PREPARED.json').read_text())
assert prepared['manifest_sha256']==p['manifest_sha256']
for name,expected in prepared['files_sha256'].items():assert hashlib.sha256((root/'source'/name).read_bytes()).hexdigest()==expected
req=urllib.request.Request('http://127.0.0.1:18403/health',headers={'Authorization':'Bearer '+p['token']})
with urllib.request.urlopen(req,timeout=15) as response:model=json.load(response)
assert model['status']=='ok' and model['candidate_id']=='eviweave-v03-search-credit-v34-cpu-reference-v36'
assert model['manifest_sha256']==p['manifest_sha256'] and model['model']['device']=='cpu'
private=root/'private'
private.mkdir(mode=0o700,exist_ok=True)
env=private/'candidate.env'
content='EVIWEAVE_RPC_URL=http://127.0.0.1:18403/transform\\nEVIWEAVE_RPC_TOKEN='+p['token']+'\\n'
if env.exists():assert env.read_text()==content
else:
 with env.open('x') as stream:stream.write(content)
os.chmod(env,0o600)
override=Path('/etc/systemd/system/memory-lab@m02.service.d/90-eviweave-v36-cpu.conf')
content='[Service]\\nWorkingDirectory='+str(root/'source')+'\\nEnvironmentFile='+str(env)+'\\nExecStart=\\nExecStart='+str(root/'venv/bin/python')+' -m uvicorn server:app --host 127.0.0.1 --port 18102\\n'
if override.exists():assert override.read_text()==content,'Refuse to replace an unrelated override'
else:
 override.parent.mkdir(parents=True,exist_ok=True)
 with override.open('x') as stream:stream.write(content)
record=dict(override_path=str(override),override_sha256=hashlib.sha256(content.encode()).hexdigest(),manifest_sha256=p['manifest_sha256'])
(root/'SWITCH_INTENT.json').write_text(json.dumps(record,indent=2)+'\\n')
subprocess.run(['systemctl','daemon-reload'],check=True,capture_output=True)
subprocess.run(['systemctl','restart','memory-lab@m02.service'],check=True,capture_output=True,timeout=60)
for attempt in range(30):
 try:
  with urllib.request.urlopen('http://127.0.0.1:18102/health',timeout=15) as response:health=json.load(response)
  assert health['candidate_manifest_sha256']==p['manifest_sha256']
  assert health['candidate_model']['device']=='cpu'
  break
 except Exception:
  if attempt==29:raise
  time.sleep(1)
print(json.dumps(dict(switched=True,systemd_unit='memory-lab@m02.service',backend_port=18102,health=health,override_sha256=record['override_sha256'],shared_source_modified=False,shared_venv_modified=False)))
'''.replace('PAYLOAD',repr(payload))
        receipt.update(ssh(code))
    else:
        receipt['idle_check']=account_idle(config)
        code='''import hashlib,json,subprocess
from pathlib import Path
root=Path(REMOTE)
assert root.parent==Path('/opt/memory-lab/releases')
record=json.loads((root/'SWITCH_INTENT.json').read_text())
override=Path(record['override_path'])
assert override==Path('/etc/systemd/system/memory-lab@m02.service.d/90-eviweave-v36-cpu.conf')
assert hashlib.sha256(override.read_bytes()).hexdigest()==record['override_sha256']
override.unlink()
subprocess.run(['systemctl','daemon-reload'],check=True,capture_output=True)
subprocess.run(['systemctl','restart','memory-lab@m02.service'],check=True,capture_output=True,timeout=60)
print(json.dumps(dict(rolled_back=True,only_owned_override_removed=True,shared_source_modified=False,shared_venv_modified=False)))
'''.replace('REMOTE',repr(remote))
        receipt.update(ssh(code))
    (out/'RECEIPT.json').write_text(json.dumps(probe.sanitized(receipt,config.values()),indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(path=str(out/'RECEIPT.json'),**receipt),ensure_ascii=False))


if __name__=='__main__':
    main()
