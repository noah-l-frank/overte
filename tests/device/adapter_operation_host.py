"""Explicit scoped client for one original Pico CLI process; never a daemon."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from contextvars import ContextVar
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import stat
import subprocess
import sys
import time
import uuid

from adapters.native_fd_owner import OriginalDescriptor
from adapters.chat_journey.archive_file import signature
from adapters.host_process_identity import host_identity
from adapters.pico4.operation_host import process_identity
from adapters.pico4.operation_protocol import (need,dto_bytes,decode,request,timeout_for,STRIPPED_ENV,REQUEST_LIMIT,RESPONSE_LIMIT,STDERR_LIMIT,PART_LIMIT)
from adapters.pico4.operation_archive import OperationArchive

ACTIVE=ContextVar('overte_pico_operation_host',default=None)
UNCERTAIN=[]
ENTRY=Path(__file__).resolve().parent/'adapters/android/adapter.py'


class PinnedFile:
    def __init__(self,path,limit):
        self.path=Path(path);need(self.path.is_absolute() and self.path.resolve(strict=True)==self.path)
        self.owner=OriginalDescriptor(self.path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC);info=os.fstat(self.owner.fd)
        need(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and not info.st_mode&0o022 and 0<info.st_size<=limit)
        self.stamp=signature(info);self.raw=os.pread(self.owner.fd,limit+1,0);need(len(self.raw)==info.st_size);self.digest=hashlib.sha256(self.raw).hexdigest();self.check()
    def check(self):
        self.owner.require(self.owner.fd);need(signature(os.fstat(self.owner.fd))==signature(self.path.lstat())==self.stamp
            and os.pread(self.owner.fd,len(self.raw)+1,0)==self.raw)
        self.owner.require(self.owner.fd)
    def close(self):self.check();return self.owner.close()


class PipeOwner:
    def __init__(self,stream):
        self.stream=stream;self.fd=stream.fileno();self.anchor=fcntl.fcntl(self.fd,fcntl.F_DUPFD_CLOEXEC,0);self.node=signature(os.fstat(self.fd))[:2];self.lost=False
        self.check();os.set_blocking(self.fd,False)
    def check(self):
        try:need(not self.lost and self.stream.fileno()==self.fd and signature(os.fstat(self.fd))[:2]==self.node and fcntl.fcntl(self.fd,fcntl.F_DUPFD_QUERY,self.anchor)==1)
        except BaseException:self.lost=True;UNCERTAIN.append(self);raise
    def close(self):
        self.check();self.stream.close();os.close(self.anchor)


def pico_command(manifest):
    # This opt-in accepts the reviewed source-owned route only. Other adapters
    # continue through adapter_client's ordinary one-operation subprocess.
    from adapter_client import load_command
    def pairs(items):
        result={}
        for key,value in items:need(key not in result);result[key]=value
        return result
    def invalid(_):need(False)
    payload=json.loads(Path(manifest).read_bytes(),object_pairs_hook=pairs,parse_constant=invalid)
    dto_bytes(payload,65536)
    need(type(payload) is dict and type(payload.get('schemaVersion')) is int and payload['schemaVersion']==1)
    command=load_command(manifest)
    need(len(command)>=5 and Path(command[0]).resolve(strict=True)==Path(sys.executable).resolve(strict=True)
        and Path(command[1]).resolve(strict=True)==ENTRY.resolve(strict=True)
        and command.count('--kind')==1 and command[command.index('--kind')+1]=='pico' and command.count('--native-binding')==1
        and not any(part in {'invoke','cleanup','discover','describe','operation-host','--operation','--arguments','--target'} for part in command[2:]))
    return command


class PicoOperationHost:
    def __init__(self,manifest,target,artifacts):
        need(type(target) is str and 0<len(target)<=256 and all(33<=ord(c)<127 for c in target))
        self.manifest=Path(manifest).absolute();self.target=target;self.artifacts=Path(artifacts)
        self.host=host_identity();self.environment=dict(os.environ);self.cwd=os.getcwd()
        self.child_environment={k:v for k,v in self.environment.items() if k not in STRIPPED_ENV}
        self._original_scope=(str(self.manifest),self.target,dict(self.environment),self.cwd,self.host,dict(self.child_environment))
        self.failed=self.closed=False;self.process=None;self.pins=[];self.pipes=[];self.archive=None;self.count=0
        self.process_identity=None;self.command=None;self.wait_status=None;self.last=time.monotonic();self.lifetime=None;self.first_started=None
        self.acquired_response=bytearray();self.acquired_stderr=bytearray();self.pending_request=None;self.sent_bytes=0
    def guard(self):
        need(not self.failed and not self.closed and host_identity()==self.host and dict(os.environ)==self.environment and os.getcwd()==self.cwd
            and (str(self.manifest),self.target,self.environment,self.cwd,self.host,self.child_environment)==self._original_scope)
        for pin in self.pins:pin.check()
        for pipe in self.pipes:pipe.check()
        if self.process is not None:
            need(process_identity(self.process.pid)==self.process_identity)
            root=Path('/proc')/str(self.process.pid)
            fields=(root/'stat').read_text().rsplit(')',1)[1].split();need(int(fields[1])==os.getpid())
            need((root/'cmdline').read_bytes().split(b'\0')==[os.fsencode(item) for item in self.command]+[b''])
            need(signature(os.stat(root/'exe'))==self.pins[1].stamp)
    def remaining(self,deadline):
        now=time.monotonic();need(self.last<=now<deadline);self.last=now;return min(.1,deadline-now)
    def start(self,deadline):
        need(self.process is None);self.lifetime=self.first_started+1560;self.archive=OperationArchive(self.artifacts,dict(parentHostProcessIdentity=self.host,targetFingerprint=hashlib.sha256(self.target.encode()).hexdigest(),contextSha256=hashlib.sha256(dto_bytes(list(self._original_scope),4*1024*1024)).hexdigest()))
        self.pins.append(PinnedFile(self.manifest,65536));prefix=pico_command(self.manifest);need(self.pins[0].raw==self.manifest.read_bytes())
        self.pins.extend([PinnedFile(Path(prefix[0]).resolve(strict=True),128*1024*1024),PinnedFile(Path(prefix[1]).resolve(strict=True),1024*1024)])
        self.guard();self.remaining(deadline);self.command=[*prefix,'operation-host','--target',self.target]
        self.process=subprocess.Popen(self.command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=self.child_environment,cwd=self.cwd,bufsize=0)
        self.process_identity=process_identity(self.process.pid)
        self.pipes=[PipeOwner(self.process.stdin),PipeOwner(self.process.stdout),PipeOwner(self.process.stderr)]
        # Exec can still be in progress after Popen returns. Only the same PID
        # start/boot and direct parent may wait for its exact original program.
        while True:
            self.remaining(deadline)
            try:self.guard();break
            except (OSError,ValueError):
                need(process_identity(self.process.pid)==self.process_identity)
                time.sleep(min(.001,self.remaining(deadline)))
        self.archive.bind(dict(hostProcessIdentity=self.process_identity,argvSha256=hashlib.sha256(dto_bytes(self.command,REQUEST_LIMIT)).hexdigest(),
            sources=[dict(path=str(pin.path),sha256=pin.digest,physical=pin.stamp) for pin in self.pins]))
    def invoke(self,manifest,target,operation,arguments=None):
        started=time.monotonic();deadline=started+timeout_for(operation)
        held=getattr(self,'_create_action_budget',None)
        if held is not None:deadline=min(deadline,held['deadlineMonotonic'])
        fields=dict(picoOperationRequestVersion=1,requestId=uuid.uuid4().hex,operation=operation,arguments={} if arguments is None else arguments,deadlineMonotonic=deadline)
        return self._exchange(manifest,target,fields,started,deadline)

    def create_component(self,run,fixture_url,operation,arguments=None,*,budget=None):
        now=time.monotonic();held=getattr(self,'_create_action_budget',None)
        selected=budget if budget is not None else held if held is not None else dict(id=uuid.uuid4().hex,startedMonotonic=now,deadlineMonotonic=now+60)
        fields=dict(picoCreateOperationRequestVersion=1,requestId=uuid.uuid4().hex,runId=run,fixtureUrl=fixture_url,operation=operation,budget=selected,arguments=arguments)
        return self._exchange(self.manifest,self.target,fields,selected['startedMonotonic'],selected['deadlineMonotonic'],private=True)

    @contextmanager
    def create_input_context(self,run,fixture_url,operation,arguments):
        need(getattr(self,'_create_action_budget',None) is None)
        started=time.monotonic();budget=dict(id=uuid.uuid4().hex,startedMonotonic=started,deadlineMonotonic=started+60)
        self._create_action_budget=budget;entered=False;original_error=None
        try:
            self.create_component(run,fixture_url,'input.begin',dict(operation=operation,arguments=arguments),budget=budget);entered=True
            yield budget
        except BaseException as error:
            original_error=error;raise
        finally:
            try:
                if entered and not self.failed:self.create_component(run,fixture_url,'input.end',None,budget=budget)
            except BaseException:
                self.failed=True;self.abort()
                if original_error is None:raise
            finally:
                self._create_action_budget=None
                if self.failed:self.abort()

    def _exchange(self,manifest,target,fields,started,deadline,*,private=False):
        operation=fields['operation']
        try:
            self.guard();need(Path(manifest).absolute()==self.manifest and target==self.target)
            if private:
                from adapters.pico4.create_operation_protocol import validate
                validate(fields)
            else:request(fields)
            raw=dto_bytes(fields,REQUEST_LIMIT)
            if self.process is None:self.first_started=started;self.start(deadline)
            self.guard();self.remaining(deadline)
            self.pending_request=raw;self.sent_bytes=0
            self.archive.reserve(dict(requestId=fields['requestId'],operation=operation,startedMonotonic=started,deadlineMonotonic=deadline))
            index=self.count;request_original=self.archive.put(f'request-{index:03d}.bin',raw)
            incoming=self.acquired_response=bytearray();stderr=self.acquired_stderr=bytearray();response_parts=[];error_parts=[];sent=0;offset=0;error_offset=0;stderr_open=True
            while True:
                self.guard();interval=self.remaining(deadline)
                readable,writable,_=select.select([self.pipes[1].fd]+([self.pipes[2].fd] if stderr_open else []),[] if sent==len(raw) else [self.pipes[0].fd],[],interval)
                for descriptor in readable:
                    output=descriptor==self.pipes[1].fd;pipe=self.pipes[1 if output else 2];pipe.check()
                    body=incoming if output else stderr;limit=RESPONSE_LIMIT if output else STDERR_LIMIT
                    need(len(body)<limit)
                    # Bound before read; every byte acquired is durable before
                    # the next read, including malformed/partial responses.
                    position=offset if output else error_offset;size=min(65536-position,limit-len(body))
                    chunk=os.read(descriptor,size)
                    if not chunk:
                        if not output:stderr_open=False;continue
                        need(False)
                    name=(f'response-{index:03d}-{len(response_parts):03d}.bin' if output else f'stderr-{index:03d}-{len(error_parts):03d}.bin')
                    body.extend(chunk);self.archive.append(name,chunk);position+=len(chunk)
                    if output:need(sent==len(raw))
                    if position==65536 or output and b'\n' in chunk:
                        receipt=self.archive.seal(name);(response_parts if output else error_parts).append(receipt);position=0
                    if output:offset=position
                    else:error_offset=position
                if writable:
                    self.pipes[0].check();written=os.write(self.pipes[0].fd,raw[sent:sent+4096]);need(written>0);sent+=written;self.sent_bytes=sent
                if b'\n' in incoming:
                    need(sent==len(raw));break
            if error_offset:error_parts.append(self.archive.seal(f'stderr-{index:03d}-{len(error_parts):03d}.bin'))
            acquired=bytes(incoming)
            # Complete immutable receipt/CAS BEFORE decoding an acquired reply.
            self.archive.finish(dict(picoOperationReceiptVersion=1,request=request_original,response=response_parts,stderr=error_parts,
                responseBytes=len(acquired),responseSha256=hashlib.sha256(acquired).hexdigest(),requestId=fields['requestId']))
            reply=decode(acquired,RESPONSE_LIMIT)
            version='picoCreateOperationReplyVersion' if private else 'picoOperationReplyVersion'
            need(set(reply)=={version,'requestId','hostProcessIdentity','parentHostProcessIdentity','result'}|({'componentOnly','completeCommonObservation'} if private else set())
                and type(reply[version]) is int and reply[version]==1 and reply['requestId']==fields['requestId']
                and reply['hostProcessIdentity']==self.process_identity and reply['parentHostProcessIdentity']==self.host)
            if private:
                need(reply['componentOnly'] is True and reply['completeCommonObservation'] is False);value=reply['result']
            else:
                from contracts import validate_operation_result
                value=validate_operation_result(operation,reply['result'])
            self.guard();self.archive.guard();self.remaining(deadline);self.count+=1;self.pending_request=None
            return value
        except BaseException:
            self.failed=True;UNCERTAIN.append(self)
            raise RuntimeError('Pico operation host unresolved; no replay or further operation permitted') from None
    def close(self):
        if self.closed:return
        try:
            need(not self.failed)
            if self.process is None:self.closed=True;return
            self.guard();self.archive.guard();deadline=min(time.monotonic()+60,self.lifetime)
            closing=dict(requestId=uuid.uuid4().hex,operation='host.close',startedMonotonic=time.monotonic(),deadlineMonotonic=deadline)
            self.archive.reserve(closing)
            close_raw=dto_bytes(dict(picoOperationCloseVersion=1,requestId=closing['requestId'],deadlineMonotonic=deadline),REQUEST_LIMIT)
            self.archive.put('shutdown-request.bin',close_raw);self.pipes[0].check();self.remaining(deadline)
            _,writable,_=select.select([],[self.pipes[0].fd],[],self.remaining(deadline));need(writable)
            need(os.write(self.pipes[0].fd,close_raw)==len(close_raw))
            self.pipes[0].close();self.pipes=self.pipes[1:]
            readable_pipes=list(self.pipes);late=[];status=None
            while True:
                self.remaining(deadline)
                ready,_,_=select.select([pipe.fd for pipe in readable_pipes],[],[],.01)
                for pipe in list(readable_pipes):
                    if pipe.fd not in ready:continue
                    pipe.check();chunk=os.read(pipe.fd,65536)
                    if not chunk:readable_pipes.remove(pipe);continue
                    # Even unsolicited shutdown bytes are retained BEFORE a
                    # refusal. No parser or further adapter input can follow.
                    original=self.archive.put(f'late-{len(late):03d}.bin',chunk);late.append(original)
                    need(False)
                if status is None:
                    pid,observed=os.waitpid(self.process.pid,os.WNOHANG)
                    if pid:status=observed;self.wait_status=status;self.process.returncode=os.waitstatus_to_exitcode(status)
                if status is not None and not readable_pipes:break
            self.wait_status=status;self.process.returncode=os.waitstatus_to_exitcode(status);need(pid==self.process.pid and status==0)
            self.archive.finish(dict(picoOperationHostExitVersion=1,hostProcessIdentity=self.process_identity,waitStatus=status,late=late))
            for _ in range(2):
                try:os.kill(pid,0)
                except ProcessLookupError as error:need(error.errno==errno.ESRCH)
                else:need(False)
                need(not (Path('/proc')/str(pid)).exists())
            for pipe in self.pipes:pipe.close()
            self.pipes=[];self.archive.close();need(all(pin.close() for pin in self.pins));self.closed=True
        except BaseException:
            self.failed=True;UNCERTAIN.append(self);raise RuntimeError('Pico operation host closure unresolved') from None
    def abort(self):
        """Stop ONLY this proven original child. Never app/peer cleanup."""
        if self.process is None:return
        try:
            pid,status=os.waitpid(self.process.pid,os.WNOHANG)
            if pid:self.wait_status=status;self.process.returncode=os.waitstatus_to_exitcode(status);return
            # failed forbids normal reuse, but original program/file/pipe facts
            # still must match before a nonzero signal to our exact OS child.
            failed=self.failed;self.failed=False
            try:self.guard()
            finally:self.failed=failed
            os.kill(self.process.pid,signal.SIGTERM)
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                pid,status=os.waitpid(self.process.pid,os.WNOHANG)
                if pid:self.wait_status=status;self.process.returncode=os.waitstatus_to_exitcode(status);return
                time.sleep(.01)
        except Exception:pass
        UNCERTAIN.append(self)


@contextmanager
def scoped_host(manifest,target,artifacts):
    need(ACTIVE.get() is None);owner=PicoOperationHost(manifest,target,artifacts);token=ACTIVE.set(owner)
    try:
        yield owner
        owner.close()
    except BaseException:
        owner.failed=True;owner.abort();raise
    finally:ACTIVE.reset(token)
