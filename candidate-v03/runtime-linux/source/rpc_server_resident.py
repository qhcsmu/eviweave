"""Local original-reference CPU learned retrieval; never initializes GPU."""
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import argparse
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading
import time

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
ROOT=BASE.parents[3]


def module(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--owner-pid',type=int,required=True)
    parser.add_argument('--private',type=Path,required=True)
    parser.add_argument('--run',type=Path,required=True)
    args=parser.parse_args()
    assert args.private.resolve().is_relative_to(HERE.resolve()) and args.run.resolve().is_relative_to(HERE.resolve())
    result=json.loads((HERE/'SOURCE128/RESULT.json').read_text())
    assert result['CPU_reference_source_rank_qualified'] and not result['GPU_equivalence_qualified']
    assert json.loads((HERE/'SOURCE128/PROCESS_EXIT.json').read_text())['exit_code']==0
    assert json.loads((HERE/'SOURCE128/INDEPENDENT_AUDIT.json').read_text())['passed']
    manifest=json.loads((HERE/'MANIFEST.json').read_text())
    for path,expected in manifest['local_files_sha256'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==expected
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false',
                      CUBLAS_WORKSPACE_CONFIG=':4096:8',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
    sys.path.insert(0,str(ROOT/'models/qwen35_runtime'))
    from direct_scorer import DirectScorer,torch
    def check_lock():
        owner=json.loads((Path(os.environ['EVIWEAVE_OWNER_LOCK_ROOT'])/'cpu-service.lock/owner.json').read_text())
        assert owner['pid']==args.owner_pid
        # Same owner-liveness check on Linux, including PID reuse and boot identity.
        fields = (Path('/proc') / str(args.owner_pid) / 'stat').read_text().rsplit(')', 1)[1].split()
        assert fields[0] not in ('Z', 'X')
        assert int(fields[19]) == owner['linux_start_ticks']
        assert owner['linux_boot_id'] == Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        assert owner['runtime_platform'] == 'linux-resident'
        assert not torch.cuda.is_initialized()
    check_lock()
    scorer=DirectScorer('learned')
    from transformers import AutoTokenizer
    from transform import CANDIDATE, transform
    tokenizer=AutoTokenizer.from_pretrained(ROOT/'models/Qwen3.5-4B',local_files_only=True,trust_remote_code=False)
    token=(args.private/'rpc-token.txt').read_text().strip()
    assert len(token)>=40
    mutex=threading.Lock()
    stats=dict(requests=0,neural_queries=0,changed=0,errors=0,seconds=0.0)
    identity=dict(candidate_id=CANDIDATE,model=scorer.identity,
                  manifest_sha256=hashlib.sha256((HERE/'MANIFEST.json').read_bytes()).hexdigest(),
                  qualification_sha256=hashlib.sha256((HERE/'SOURCE128/RESULT.json').read_bytes()).hexdigest())

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass

        def respond(self,status,value):
            raw=json.dumps(value,ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def authorized(self):
            return hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+token)

        def do_GET(self):
            if not self.authorized():
                return self.respond(401,dict(error='unauthorized'))
            if self.path!='/health':
                return self.respond(404,dict(error='unknown_route'))
            try:
                check_lock()
                self.respond(200,dict(status='ok',**identity,stats=stats))
            except Exception:
                self.respond(503,dict(status='unavailable'))

        def do_POST(self):
            if not self.authorized():
                return self.respond(401,dict(error='unauthorized'))
            if self.path not in ('/transform','/self-test'):
                return self.respond(404,dict(error='unknown_route'))
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=16*1024*1024:
                    return self.respond(413,dict(error='invalid_length'))
                payload=json.loads(self.rfile.read(length))
                if self.path=='/self-test':
                    if payload!={}:
                        raise ValueError('Self-test accepts no external records')
                    units=[dict(source_id=str(i),doc_id=str(i),session='self-test',ordinal=i,start=0,
                        end=len('The morning trail is beside the river.'),
                        header='[user | 2026-01-01T00:00:00+00:00] ',body='The morning trail is beside the river.') for i in range(32)]
                    payload=dict(protocol='search-credit-v34',query='Where is the morning trail?',native_units=units,
                        native_hits=[dict(id=str(i),content=u['header']+u['body'],score=1/(i+1)) for i,u in enumerate(units)],
                        source_pool=[dict(unit=units[24],native_rank=25)],top_k=100,context_chars=24000)
                with mutex:
                    check_lock()
                    start=time.monotonic()
                    result=transform(payload,tokenizer,scorer)
                    elapsed=time.monotonic()-start
                    stats['requests']+=1
                    stats['neural_queries']+=result['neural_queries']
                    stats['changed']+=int(result['changed'])
                    stats['seconds']+=elapsed
                    with (args.run/'requests-metadata.jsonl').open('a',encoding='utf-8') as stream:
                        stream.write(json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(),seconds=elapsed,
                            **{k:v for k,v in result.items() if k not in ('hits','detail')}))+'\n')
                if self.path=='/self-test':
                    if result['neural_queries']!=1 or not result['changed']:
                        raise ValueError('Real learned selection not exercised')
                    result={k:v for k,v in result.items() if k not in ('hits','detail')}
                    result['self_test_passed']=True
                self.respond(200,result)
            except Exception as error:
                stats['errors']+=1
                self.respond(503,dict(error=type(error).__name__))

    # Process activation only: load the qualified model before releasing SSH.
    # No alternate port, altered model parameter or retrieval logic is used.
    (args.run/'PREWARMED.json').write_text(json.dumps(dict(
        utc=datetime.now(timezone.utc).isoformat(),pid=os.getpid(),owner_pid=args.owner_pid,
        model_loaded=True,production_listener_active=False,**identity),indent=2)+'\n')
    while not (HERE/'LINUX_RESIDENT_ACTIVATED.json').is_file():
        check_lock()
        time.sleep(0.02)
    bind_deadline=time.monotonic()+30
    while True:
        try:
            http=ThreadingHTTPServer(('127.0.0.1',18403),Handler)
            break
        except OSError as error:
            if error.errno!=98 or time.monotonic()>=bind_deadline:
                raise
            check_lock()
            time.sleep(0.02)
    ready=dict(utc=datetime.now(timezone.utc).isoformat(),pid=os.getpid(),owner_pid=args.owner_pid,**identity)
    (args.run/'READY.json').write_text(json.dumps(ready,indent=2)+'\n')
    print(json.dumps(dict(stage='learned_CPU_reference_RPC_ready',pid=os.getpid(),port=18403,identity=identity)),flush=True)
    try:
        http.serve_forever(poll_interval=0.5)
    finally:
        http.server_close()
        scorer.close()


if __name__=='__main__':
    main()
