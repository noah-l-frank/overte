"""Explicit device-free CLI factory model, used only by owning stdio tests."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import atexit
import hashlib
import os
from pathlib import Path
import sys
import time
import subprocess
import threading
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'tests/device')]
from adapters.android import adapter as cli
from adapters.pico4.operation_host import serve
from adapters.native_binding import create_adapter
from adapters.pico4.operation_protocol import STRIPPED_ENV

fault=sys.argv[sys.argv.index('--fault')+1];trace=Path(sys.argv[sys.argv.index('--trace')+1]);count=0
def source_receipt():
    sources={}
    for module in list(sys.modules.values()):
        name=getattr(module,'__file__',None)
        if not name:continue
        path=Path(name).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():continue
        info=path.lstat();sources[str(path)]=dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),physical=[info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_nlink,info.st_size,info.st_mtime_ns,info.st_ctime_ns])
    trace.with_name(trace.name+'.sources.json').write_text(json.dumps(sources,sort_keys=True))
atexit.register(source_receipt)

args=SimpleNamespace(kind='phone' if fault=='legacy-phone' else 'pico',native_binding=fault!='legacy-phone',action='invoke' if fault=='legacy-phone' else 'operation-host',target='explicit-host-model',operation='app.process' if fault=='legacy-phone' else None,arguments='{}')

def record(kind):
    with trace.open('a') as output:output.write(json.dumps(dict(kind=kind,pid=os.getpid()))+'\n');output.flush();os.fsync(output.fileno())

class FakeAdapter(cli.AndroidAdapter):
    def __init__(self):self.kind=args.kind;self.profile=cli.PROFILES[args.kind];self.calls=0
    def selected_target(self,target,action):return target
    def invoke(self,target,operation,values):
        record('dispatch');self.calls+=1
        if fault=='timeout':time.sleep(.4)
        if fault=='unsolicited':threading.Timer(.05,lambda:os.write(1,b'unsolicited\n')).start()
        if fault=='mutate-args':args.operation='foreign'
        if fault=='stderr':
            for _ in range(40):os.write(2,b'x'*4096)
        if fault=='invalid-json':os.write(1,b'{"broken":]\n');raise ValueError('Explicit invalid raw reply')
        if fault=='partial':os.write(1,b'{"broken":');raise ValueError('Explicit partial raw reply')
        if fault=='raw-cap':
            for _ in range(1024):os.write(1,b'\0'*4096)
            time.sleep(.4);raise ValueError('Explicit exact raw-window boundary')
        if fault=='wrong-id':os.write(1,b'{"picoOperationReplyVersion":1,"requestId":"00000000000000000000000000000000","hostProcessIdentity":"x","parentHostProcessIdentity":"x","result":{}}\n');raise ValueError('Explicit wrong request')
        return dict(running=True,identity=str(os.getpid()),calls=self.calls,factories=count,absentKeys=[key for key in STRIPPED_ENV if key not in os.environ],**({'raw':'x'*(3*1024*1024)} if fault=='large' else {}))
    def cleanup(self,target):record('FORBIDDEN cleanup');raise AssertionError('No automatic product cleanup')

class Binding:
    @staticmethod
    def create_adapter(namespace,base):
        global count
        count+=1;record('factory')
        if fault=='factory-timeout':time.sleep(.4)
        return FakeAdapter()

if __name__=='__main__' and '--parent-controller' in sys.argv:
    from adapters.pico4.operation_protocol import dto_bytes,REQUEST_LIMIT
    import uuid
    child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--fault',fault,'--trace',str(trace),'operation-host','--target','explicit-host-model'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    raw=dto_bytes(dict(picoOperationRequestVersion=1,requestId=uuid.uuid4().hex,operation='app.process',arguments={},deadlineMonotonic=time.monotonic()+10),REQUEST_LIMIT)
    child.stdin.write(raw);child.stdin.flush()
    if fault=='factory-timeout':
        until=time.monotonic()+5
        while not trace.exists() and time.monotonic()<until:time.sleep(.001)
    else:child.stdout.readline()
    os.write(1,(str(child.pid)+'\n').encode());os._exit(0)


if __name__=='__main__':
    # Actual existing CLI main/construct route, with only its source-owned
    # argument producer and candidate factory explicitly replaced in this model.
    cli.cli=lambda argv=None:(args,Binding)
    try:
        raise SystemExit(cli.main([]))
    except Exception:
        record('rejected');raise SystemExit(2)
