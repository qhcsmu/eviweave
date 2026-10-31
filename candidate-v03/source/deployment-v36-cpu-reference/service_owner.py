"""Own CPU service/tunnel only. No acquisition, release or initialization of GPU."""
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import urllib.request

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
ROOT=BASE.parents[3]


def read(path):return json.loads(path.read_text())


def main():
    result=read(HERE/'SOURCE128/RESULT.json')
    assert result['CPU_reference_source_rank_qualified'] and not result['GPU_equivalence_qualified']
    assert read(HERE/'SOURCE128/PROCESS_EXIT.json')['exit_code']==0
    assert read(HERE/'SOURCE128/INDEPENDENT_AUDIT.json')['passed']
    owner=dict(pid=os.getpid(),token=secrets.token_hex(16),utc=datetime.now(timezone.utc).isoformat(),GPU_work=False)
    lock=HERE/'cpu-service.lock'
    lock.mkdir()
    (lock/'owner.json').write_text(json.dumps(owner))
    out=HERE/'service-runs'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out.mkdir(parents=True,exist_ok=False)
    private=HERE/'private';private.mkdir(exist_ok=True)
    token_path=private/'rpc-token.txt'
    if not token_path.exists():
        with token_path.open('x') as stream:stream.write(secrets.token_urlsafe(48)+'\n')
    token=token_path.read_text().strip()
    children=[];handles=[]
    def save(name,value):(out/name).write_text(json.dumps(value,indent=2)+'\n')
    try:
        stdout=(out/'model-stdout.log').open('xb');stderr=(out/'model-stderr.log').open('xb');handles.extend([stdout,stderr])
        model=subprocess.Popen([sys.executable,'-B','-X','utf8',str(HERE/'rpc_server.py'),
            '--owner-pid',str(os.getpid()),'--private',str(private),'--run',str(out)],cwd=str(ROOT),
            stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
        children.append(model)
        save('MODEL_CHILD.json',dict(pid=model.pid,owner_pid=os.getpid(),GPU_work=False))
        for unused in range(120):
            if model.poll() is not None:raise RuntimeError('Own CPU model failed before readiness')
            if (HERE/'STOP_REQUESTED').exists():return
            if (out/'READY.json').is_file():break
            time.sleep(1)
        else:raise RuntimeError('CPU startup timeout')
        request=urllib.request.Request('http://127.0.0.1:18403/self-test',data=b'{}',method='POST',
            headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=90) as response:self_test=json.load(response)
        assert self_test['self_test_passed'] and self_test['neural_queries']==1
        save('REAL_MODEL_SELF_TEST.json',self_test)
        connection=read(BASE/'eviweave-v03-hourly/private/ssh-connection.json')
        log=(out/'tunnel-stderr.log').open('xb');handles.append(log)
        tunnel=subprocess.Popen(['ssh.exe','-i',connection['private_key'],'-p','22','-o','BatchMode=yes','-o','IdentitiesOnly=yes',
            '-o','ConnectTimeout=12','-o','ExitOnForwardFailure=yes','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=3',
            '-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+connection['hostkey_file'],'-N','-T','-R',
            '127.0.0.1:18403:127.0.0.1:18403','root@101.201.226.162'],stdout=subprocess.DEVNULL,stderr=log,
            cwd=str(ROOT),creationflags=subprocess.CREATE_NO_WINDOW)
        children.append(tunnel);time.sleep(2)
        if tunnel.poll() is not None:raise RuntimeError('Own CPU reverse tunnel failed')
        pointer=dict(run=str(out.relative_to(HERE)),owner_pid=os.getpid(),model_pid=model.pid,tunnel_pid=tunnel.pid,GPU_work=False)
        (HERE/'CURRENT_SERVICE.json').write_text(json.dumps(pointer,indent=2)+'\n')
        print(json.dumps(dict(status='own_CPU_reference_model_and_tunnel_running',**pointer)),flush=True)
        while not (HERE/'STOP_REQUESTED').exists():
            assert read(lock/'owner.json')==owner
            if any(child.poll() is not None for child in children):raise RuntimeError('Own CPU service or tunnel exited')
            time.sleep(1)
    finally:
        exits=[]
        for child in reversed(children):
            if child.poll() is None:child.terminate()
            exits.append(dict(pid=child.pid,exit_code=child.wait()))
        for handle in handles:handle.close()
        save('CHILD_EXITS.json',exits)
        assert read(lock/'owner.json')==owner
        (lock/'owner.json').unlink();lock.rmdir()
        save('CLEANUP.json',dict(own_children_exited=True,own_CPU_lock_released=True,public_GPU_lock_touched=False))


if __name__=='__main__':main()
