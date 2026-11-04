"""Linux owner-liveness tests without model loading or production ports."""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace

here=Path(__file__).resolve().parent
tree=ast.parse((here/'rpc_server_resident.py').read_text())
main=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='main')
check=next(x for x in main.body if isinstance(x,ast.FunctionDef) and x.name=='check_lock')
tests={}
with tempfile.TemporaryDirectory(prefix='owner-check-',dir=here) as temp:
    root=Path(temp)
    lock=root/'cpu-service.lock'
    lock.mkdir()
    child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
    try:
        owner=dict(pid=child.pid,linux_start_ticks=int(Path('/proc/'+str(child.pid)+'/stat').read_text().rsplit(')',1)[1].split()[19]),linux_boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),runtime_platform='linux-resident')
        namespace=dict(os=SimpleNamespace(environ={'EVIWEAVE_OWNER_LOCK_ROOT':str(root)}),json=json,Path=Path,HERE=root,args=SimpleNamespace(owner_pid=child.pid),torch=SimpleNamespace(cuda=SimpleNamespace(is_initialized=lambda:False)))
        exec(compile(ast.Module(body=[check],type_ignores=[]),'original-linux-check','exec'),namespace)
        def run(value):
            (lock/'owner.json').write_text(json.dumps(value))
            try:namespace['check_lock']();return True
            except (AssertionError,FileNotFoundError,ProcessLookupError):return False
        tests['live_owner_accepted']=run(owner)
        tests['reused_pid_start_tick_rejected']=not run({**owner,'linux_start_ticks':owner['linux_start_ticks']+1})
        tests['other_boot_rejected']=not run({**owner,'linux_boot_id':'different-boot'})
        tests['other_pid_rejected']=not run({**owner,'pid':child.pid+1})
        tests['other_platform_rejected']=not run({**owner,'runtime_platform':'other'})
        child.terminate();child.wait(timeout=5)
        tests['dead_owner_rejected']=not run(owner)
        try:lock.mkdir();tests['atomic_duplicate_owner_rejected']=False
        except FileExistsError:tests['atomic_duplicate_owner_rejected']=True
    finally:
        if child.poll() is None:child.terminate();child.wait(timeout=5)
record=dict(passed=all(tests.values()),tests=tests,model_calls=0,production_writes=0,public_GPU_lock_touched=False)
(here/'PROCESS_CHECK_TEST_RESIDENT.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record))
if not record['passed']:raise SystemExit(1)
