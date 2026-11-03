"""Opt-in originals of the existing digital receive recorder and Pulse route.

This observes the actual Popen created by AudioRoutes.capture. It launches no
process, creates no route and supplies no target or physical-acoustic verdict.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import threading
import time

VERSION=1
_POPEN=subprocess.Popen


class PreviewSourceUnavailable(RuntimeError):pass


def require(value):
    if not value:raise PreviewSourceUnavailable('Original PC preview source is unavailable')


def identifier(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{32}',value) is not None)
    return value


def producer_sha256():
    root=Path(__file__).resolve().parent
    return hashlib.sha256(b''.join((root/name).read_bytes() for name in
        ('voice_peer.py','runtime.py','voice_signal.py','peer.js','preview_source.py'))).hexdigest()


def process(pid):
    """Fresh Linux birth, command and executable originals; no adopted owner."""
    require(type(pid) is int and pid>0)
    root=Path('/proc')/str(pid)
    before=(root/'stat').read_bytes();require(len(before)<=16384)
    fields=before.decode().rsplit(')',1)[1].split()
    require(int(before.split(b' ',1)[0])==pid and fields[0] in ('R','S','D')
        and fields[19].isdigit() and int(fields[19])>0 and root.stat().st_uid==os.getuid())
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    require(re.fullmatch('[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',boot) is not None)
    executable=(root/'exe').stat();command=(root/'cmdline').read_bytes()
    require(stat.S_ISREG(executable.st_mode) and 0<len(command)<=16384)
    after=(root/'stat').read_bytes();again=after.decode().rsplit(')',1)[1].split();last_executable=(root/'exe').stat()
    keys=('st_dev','st_ino','st_mode','st_uid','st_nlink','st_size','st_mtime_ns','st_ctime_ns')
    require(int(after.split(b' ',1)[0])==pid and again[19]==fields[19] and again[0] in ('R','S','D')
        and [getattr(last_executable,key) for key in keys]==[getattr(executable,key) for key in keys]
        and (root/'cmdline').read_bytes()==command)
    return dict(identity=str(pid)+':'+fields[19]+':'+boot,
        executable=[getattr(executable,key) for key in ('st_dev','st_ino','st_mode','st_uid','st_nlink','st_size','st_mtime_ns','st_ctime_ns')],
        commandSha256=hashlib.sha256(command).hexdigest())


def absent(pid):
    try:os.kill(pid,0)
    except ProcessLookupError:return True
    except PermissionError:raise PreviewSourceUnavailable('Original recorder absence is unavailable') from None
    raise PreviewSourceUnavailable('Original recorder process remains present')


class PreviewCaptureSource:
    """One actual recorder birth/route, retained after terminal PCM publication."""
    def __init__(self,owner,capture,request,seconds):
        self.owner=owner;self.capture=identifier(capture);self.request=identifier(request)
        self.generation=secrets.token_hex(16);self.seconds=seconds
        self.recorder=None;self.worker=self.route=self.exit=self.original=None
        self.state='issued';self.error=False;self.started=None;self.lock=threading.RLock()

    def routing(self,pid):
        rows=[]
        for value in self.owner.streams():
            if str(value.get('properties',{}).get('application.process.id'))!=str(pid):continue
            require(type(value.get('index')) is int and value['index']>=0 and type(value.get('source')) is int
                and value['source']==self.owner.source_index and value.get('corked') is False)
            rows.append(dict(index=value['index'],source=value['source'],corked=False))
        rows.sort(key=lambda value:value['index'])
        require(rows and len({row['index'] for row in rows})==len(rows))
        return dict(monitorSha256=self.owner.monitor_sha,sourceIndex=self.owner.source_index,streams=rows)

    def armed(self,recorder):
        require(type(recorder) is _POPEN and recorder.poll() is None)
        worker=process(recorder.pid);route=self.routing(recorder.pid)
        require(recorder.poll() is None and process(recorder.pid)==worker)
        with self.lock:
            require(self.state=='starting' and self.recorder is recorder and self.worker==worker)
            self.route=route
            self.started=self.owner.clock();self.state='capturing'

    def created(self,recorder):
        require(type(recorder) is _POPEN)
        with self.lock:
            require(self.state=='issued' and self.recorder is None)
            self.recorder=recorder;self.state='starting'
        require(recorder.poll() is None);worker=process(recorder.pid)
        with self.lock:require(self.recorder is recorder and self.state=='starting');self.worker=worker

    def closed(self):
        with self.lock:recorder=self.recorder;worker=deepcopy(self.worker)
        require(recorder is not None and worker is not None and recorder.poll() is not None and type(recorder.returncode) is int)
        absent(recorder.pid)
        require(not any(str(row.get('properties',{}).get('application.process.id'))==str(recorder.pid) for row in self.owner.streams()))
        with self.lock:
            require(self.recorder is recorder and self.worker==worker)
            self.exit=dict(returnCode=recorder.returncode,processAbsent=True,streamAbsent=True,capturedEpochMs=self.owner.clock())
            self.state='failed' if self.error else 'closed'

    def completed(self,original):
        with self.lock:
            require(self.state=='closed' and self.exit is not None and original['captureId']==self.capture)
            self.original=deepcopy(original);self.state='completed'

    def failed(self):
        with self.lock:self.error=True;self.state='failed'

    def release_guard(self):
        with self.lock:
            require(self.state in ('completed','failed','retired') and (self.recorder is None or self.worker is not None and self.exit is not None))
        self.read()

    def retired(self):
        self.release_guard()
        with self.lock:self.state='retired'

    def read(self):
        with self.lock:
            state=self.state;recorder=self.recorder;worker=deepcopy(self.worker);route=deepcopy(self.route)
            result=dict(generation=self.generation,armRequestId=self.request,seconds=self.seconds,state=state,
                worker=worker,route=route,startedEpochMs=self.started,exit=deepcopy(self.exit),original=deepcopy(self.original))
        if state=='capturing':
            require(recorder is not None and recorder.poll() is None and process(recorder.pid)==worker)
            require(self.routing(recorder.pid)==route and recorder.poll() is None and process(recorder.pid)==worker)
        elif self.exit is not None:
            require(recorder is not None and recorder.poll() is not None);absent(recorder.pid)
            require(not any(str(row.get('properties',{}).get('application.process.id'))==str(recorder.pid) for row in self.owner.streams()))
        with self.lock:require(state==self.state and self.recorder is recorder)
        return result


class PreviewSources:
    """Read-only query DTO for opt-in captures of this exact provider process."""
    def __init__(self,streams,monitor,source_index,clock,client,client_file):
        require(callable(streams) and callable(clock) and type(monitor) is str and type(source_index) is int and source_index>=0)
        self.streams,self.clock,self.source_index=streams,clock,source_index
        self.monitor_sha=hashlib.sha256(monitor.encode()).hexdigest();self.pid=os.getpid();self.provider=process(self.pid)
        require(type(client) is _POPEN and client.poll() is None)
        self.client=client;self.client_origin=process(client.pid)
        require(self.client_origin['executable']==list(client_file))
        self.instance=secrets.token_hex(16);self.sequence=0;self.records={};self.requests=set();self.lock=threading.RLock()
        self.producer_sha=producer_sha256()

    def claim(self,capture,request,seconds):
        identifier(capture);identifier(request)
        with self.lock:
            require(self.pid==os.getpid() and capture not in self.records and len(self.records)<128 and process(self.pid)==self.provider)
            record=PreviewCaptureSource(self,capture,request,seconds);self.records[capture]=record;return record

    def query(self,capture,request,*,used=False):
        identifier(capture);identifier(request);started=time.monotonic();requested=self.clock()
        with self.lock:
            require(request not in self.requests and len(self.requests)<4096);self.requests.add(request)
        require(self.pid==os.getpid() and producer_sha256()==self.producer_sha and process(self.pid)==self.provider and self.client.poll() is None and process(self.client.pid)==self.client_origin)
        with self.lock:record=self.records.get(capture)
        require(record is not None or not used)
        require(record is None or type(record) is PreviewCaptureSource and record.owner is self and record.capture==capture)
        value=record.read() if record is not None else None
        require(producer_sha256()==self.producer_sha and process(self.pid)==self.provider and self.client.poll() is None and process(self.client.pid)==self.client_origin)
        captured=self.clock();elapsed=time.monotonic()-started
        require(type(requested) is int and type(captured) is int and 0<=captured-requested<=1500 and 0<=elapsed<=1.5)
        with self.lock:
            require(record is self.records.get(capture));self.sequence+=1
            return dict(audioPreviewSourceVersion=VERSION,producerSha256=self.producer_sha,requestId=request,instance=self.instance,sequence=self.sequence,
                provider=deepcopy(self.provider),clientProcess=deepcopy(self.client_origin),captureId=capture,requestedEpochMs=requested,capturedEpochMs=captured,source=value,
                physicalAudioHardwareTested=False)
