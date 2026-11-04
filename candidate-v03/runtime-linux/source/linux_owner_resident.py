"""Linux process ownership adapter for the unchanged v0.3 scoring/RPC logic."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import runpy
import secrets
import signal
import sys


def main():
    here=Path(__file__).resolve().parent
    owner=dict(pid=os.getpid(),token=secrets.token_hex(16),utc=datetime.now(timezone.utc).isoformat(),
               GPU_work=False,runtime_platform='linux-resident',
               linux_start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),
               linux_boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    lock=Path(os.environ['EVIWEAVE_OWNER_LOCK_ROOT'])/'cpu-service.lock'
    lock.mkdir(mode=0o700)  # atomic ownership; never delete another owner's directory
    (lock/'owner.json').write_text(json.dumps(owner)+'\n')
    out=here/'resident-runs'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out.mkdir(parents=True,exist_ok=False)
    def stop(signum,frame):raise SystemExit(0)
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    try:
        identity=json.loads((here/'LINUX_RESIDENT_RUNTIME_SUPPLEMENT.json').read_text())
        root=here.parents[4]
        for name,expected in identity['migration_files_sha256'].items():
            assert hashlib.sha256((root/name).read_bytes()).hexdigest()==expected
        sys.argv=[str(here/'rpc_server_resident.py'),'--owner-pid',str(os.getpid()),'--private',str(here/'private'),'--run',str(out)]
        runpy.run_path(str(here/'rpc_server_resident.py'),run_name='__main__')
    finally:
        assert json.loads((lock/'owner.json').read_text())==owner
        (lock/'owner.json').unlink()
        lock.rmdir()
        (out/'CLEANUP.json').write_text(json.dumps(dict(own_lock_released=True,public_GPU_lock_touched=False))+'\n')


if __name__=='__main__':main()
