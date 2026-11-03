"""Read an explicitly configured existing AssetServer's private originals.

Runs on that server's host. No discovery, process/service start, signal, backend
mutation, domain creation or HTTP gateway activation is provided here. Native
producer data can be modeled in host tests; kernel/file authority remains real.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import fcntl
import hashlib
import math
import os
from pathlib import Path
import stat
import time

from adapters.native_fd_owner import OriginalDescriptor,require_directory
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_ui import NativeUIError
from adapters.chat_journey.archive_file import signature
from adapters.pico4.assets_backend import backend_original
from feature_journeys.contract import identifier,json_document
from fixture.chat_actor_process import LinuxChatActorProcess

LIMIT=1024*1024
RAW_LIMIT=4*1024*1024
UNRESOLVED=[]


class LinuxAssetsBackendProcess(LinuxChatActorProcess):
    """Reuse original PID/start/boot/executable OFD authority, with own argv."""
    def _arguments(self):
        root=Path('/proc')/str(self.pid)
        raw=(root/'cmdline').read_bytes();need(len(raw)<=65536)
        argv=raw.split(b'\0');need(argv.count(b'-t')==1)
        index=argv.index(b'-t');need(index+1<len(argv) and argv[index+1]==b'3'
            and b'--pool' not in argv and b'--testScript' not in argv)
        environment=(root/'environ').read_bytes();need(len(environment)<=4*1024*1024)
        rows=environment.split(b'\0')
        need(rows.count(b'OVERTE_E2E_PICO_ASSETS_ORIGINALS_ENABLE=1')==1
            and rows.count(b'OVERTE_E2E_PICO_ASSETS_ORIGINALS='+os.fsencode(self.path))==1)


class PicoAssetsBackendOriginals:
    """An existing configured process/file source, not a client GetAll reader.

    `owned(pid)` and the exact executable hash are supplied by its actual live
    fixture authority. Neither a caller's claimed PID nor file JSON alone can
    supply that authority. No cold source/producer adoption API exists.
    """
    def __init__(self,directory,pid,executable_sha256,owned,domain,*,guard,
                 retain,capacity,clock_ms=lambda:time.time_ns()//1000000,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(fn) for fn in (owned,guard,retain,capacity,clock_ms,monotonic,sleep)))
        self.directory=Path(directory);self.process=self.parent=self.file=None
        self.guard_external,self.retain,self.capacity=guard,retain,capacity
        self.clock_ms,self.monotonic,self.sleep=clock_ms,monotonic,sleep
        self.domain=domain;self.last=None;self.history=[];self.failed=False;self.closed=False;self.pending=None;self.acquired=None
        try:
            self.process=LinuxAssetsBackendProcess(pid,self.directory,executable_sha256,owned)
            self.parent=OriginalDescriptor(self.directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
            self.path=self.directory/'assets-bakes.json'
            self.file=OriginalDescriptor(self.path,os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW|os.O_CLOEXEC)
            self._held=(self.process,self.parent,self.file,self.process.fd_owner)
            self.guard(allow_pending=True)
        except BaseException:
            self.failed=True;UNRESOLVED.append(self);raise

    def guard(self,*,allow_pending=False):
        need(not self.closed and not self.failed and self.guard_external() is not False)
        need((self.process,self.parent,self.file,self.process.fd_owner)==self._held
            and self.path==self.directory/'assets-bakes.json' and self.process.path==self.directory)
        need(self.process.guard() is True);require_directory(self.parent,self.directory)
        self.file.require(self.file.fd)
        named=self.path.lstat();held=os.fstat(self.file.fd)
        need(stat.S_ISREG(named.st_mode) and named.st_uid==os.geteuid()
            and stat.S_IMODE(named.st_mode)==0o600 and named.st_nlink==1
            and (named.st_dev,named.st_ino)==(held.st_dev,held.st_ino)==self.file.node)
        try:pending=(self.directory/'assets-bakes.pending').lstat()
        except FileNotFoundError:pass
        else:need(allow_pending and stat.S_ISREG(pending.st_mode) and stat.S_IMODE(pending.st_mode)==0o600
                  and pending.st_uid==os.geteuid() and pending.st_nlink==1 and pending.st_size==0)
        return True

    def age(self,started,epoch):
        self.guard(allow_pending=True);now=self.monotonic();native=self.clock_ms();ended=self.monotonic()
        need(number(now,started,started+1.5) and number(ended,now,started+1.5)
            and integer(native,epoch,epoch+1500))
        return max(native,epoch+math.ceil((ended-started)*1000))

    def read(self,run):
        identifier(run);need(self.pending is None and len(self.history)<128)
        started=self.monotonic();epoch=self.clock_ms();command=dict(schemaVersion=1,runId=run)
        self.pending=deepcopy(command)
        locked=False
        try:
            self.guard(allow_pending=True);need(number(started,0,1e15) and integer(epoch,1))
            # The owner persists query/reservation before this actual file read.
            self.capacity();self.age(started,epoch)
            for attempt in range(51):
                self.age(started,epoch);self.file.require(self.file.fd)
                try:fcntl.flock(self.file.fd,fcntl.LOCK_SH|fcntl.LOCK_NB)
                except BlockingIOError:
                    need(attempt<50);self.sleep(.01);continue
                locked=True;break
            need(locked);self.guard()  # Pending after acquiring SH is uncertain, not an empty ready source.
            self.age(started,epoch);before=os.fstat(self.file.fd)
            need(stat.S_ISREG(before.st_mode) and 0<before.st_size<=RAW_LIMIT)
            raw=os.pread(self.file.fd,RAW_LIMIT+1,0)
            self.acquired=raw
            # Even malformed/oversized (up to the unchanged raw reservation)
            # bytes are durably retained before parsing or semantic refusal.
            self.retain(raw)
            self.file.require(self.file.fd);after=os.fstat(self.file.fd)
            need(signature(before)==signature(after)==signature(self.path.lstat()) and len(raw)==before.st_size)
            self.file.require(self.file.fd);fcntl.flock(self.file.fd,fcntl.LOCK_UN);locked=False
            need(len(raw)<=LIMIT)
            value=json_document(raw);exact(value,{'assetsBakeOriginalsVersion','instance','sequence','processId','processStart',
                'domainId','assetServerId','capturedEpochMs','contextCapturedEpochMs','valid','jobs','mappings','blobs','pending'})
            actual=backend_original(value,domain=self.domain,process=self.process,epoch=self.age(started,epoch))
            if self.last is not None:
                old=self.last['source']
                need(all(actual[k]==old[k] for k in ('instance','processId','processStart','domainId','assetServerId'))
                    and actual['sequence']>=old['sequence'] and actual['capturedEpochMs']>=old['capturedEpochMs']
                    and len(actual['jobs'])>=len(old['jobs']))
                for old_job,new_job in zip(old['jobs'],actual['jobs']):
                    need(all(new_job[k]==v for k,v in old_job.items() if v is not None))
            result=dict(schemaVersion=1,runId=run,source=deepcopy(actual))
            frame=dict(command=command,rawSha256=hashlib.sha256(raw).hexdigest(),rawBytes=len(raw),
                       sequence=actual['sequence'],capturedEpochMs=actual['capturedEpochMs'])
            history=self.history+[frame];retained=deepcopy(result);self.age(started,epoch)
            self.last=retained;self.history=history;self.pending=None;self.acquired=None
            return result
        except BaseException:
            self.failed=True;UNRESOLVED.append(self)
            # Unlock only this verified original description; uncertainty is
            # retained, never force-unlocked/closed through a recycled number.
            if locked:
                try:self.file.require(self.file.fd);fcntl.flock(self.file.fd,fcntl.LOCK_UN)
                except BaseException:pass
            raise

    def close_host(self):
        # A replaced public holder is foreign even when its inode matches.
        # Retain the actual originals and never close the replacement's OFD.
        if hasattr(self,'_held') and (self.process,self.parent,self.file,self.process.fd_owner)!=self._held:
            self.failed=True
            if self not in UNRESOLVED:UNRESOLVED.append(self)
            return False
        closed=[owner.close() for owner in (self.file,self.parent) if owner is not None]
        if self.process is not None:closed.append(self.process.close())
        self.closed=all(closed)
        if not self.closed and self not in UNRESOLVED:UNRESOLVED.append(self)
        return self.closed
