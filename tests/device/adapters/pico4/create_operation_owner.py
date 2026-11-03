"""Private warm Create Parent; component sources never become Common facts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import threading
import time

from adapters.host_process_identity import host_identity
from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.pico4.operation_protocol import dto_bytes
from feature_journeys.contract import typed_equal,identifier

VERSION=1
COMPONENTS=('prepare','act','sample','reconcile','cleanup')


class CreatePeerReturnPending(NativeUIError):
    """The actual issued peer, not another failed guard, blocks retirement."""


class CreateActionBudget:
    def __init__(self,value,*,monotonic=time.monotonic):
        exact(value,{'id','startedMonotonic','deadlineMonotonic'});identifier(value['id'])
        need(number(value['startedMonotonic'],0,1e15) and number(value['deadlineMonotonic'],value['startedMonotonic'],1e15)
            and 0<value['deadlineMonotonic']-value['startedMonotonic']<=60)
        self.value=deepcopy(value);self.clock=monotonic;self.previous=value['startedMonotonic'];self.host=host_identity();self.thread=threading.get_ident();self.check()
    def check(self):
        now=self.clock();need(number(now,self.previous,self.value['deadlineMonotonic']) and now<self.value['deadlineMonotonic']
            and self.host==host_identity() and self.thread==threading.get_ident());self.previous=now;return now
    def same(self,value):need(typed_equal(self.value,value));self.check()


def owner_path(adapter,target,run):
    identifier(run);key=hashlib.sha256(('org.overte.pico\0'+target).encode()).hexdigest()[:32]
    return Path(adapter.pico_configuration[1])/('normal-create-operation-'+key+'-'+run+'.json')


def retained(adapter,target):
    """Bounded target-derived names only, before any native/input/base stop."""
    configuration=adapter.pico_configuration
    if configuration is None:return False
    directory=Path(configuration[1]);key=hashlib.sha256(('org.overte.pico\0'+target).encode()).hexdigest()[:32]
    prefix='normal-create-operation-'+key+'-';count=0
    with os.scandir(directory) as entries:
        for entry in entries:
            count+=1;need(count<=4096)
            if entry.name.startswith(prefix):return True
    return False


class PicoCreateOperationOwner:
    def __init__(self,adapter,target,run,fixture_url):
        identifier(run);need(type(target) is str and target and type(fixture_url) is str and fixture_url.endswith('/runs/'+run+'/'))
        self.adapter,self.target,self.run,self.url=adapter,target,run,fixture_url
        self.host=host_identity();self.thread=threading.get_ident();self.path=owner_path(adapter,target,run)
        need(not retained(adapter,target));self.store=PrivateFeatureState(self.path);need(self.store.read() is None)
        self.file=LifecycleProcessFile(self.store);self.state=None
        self.parent=self._parent=None;self.factory=adapter._create_journey;self.factory_calls=0
        self.failed=False;self.active=None;self.context=None;self.entered=False;self.budget=None;self.worker=None;self.worker_owner=None;self.peer_config=None
        self.pending_gate=self._peer_pending
        self._write(dict(picoCreateOperationOwnerVersion=VERSION,runId=run,fixtureUrl=fixture_url,parentHostProcessIdentity=self.host,
            targetFingerprint=hashlib.sha256(target.encode()).hexdigest(),phase='new',calls=[],pending=None,peer=None))
    def guard(self,*,failed=False):
        need((failed or not self.failed) and self.host==host_identity() and self.thread==threading.get_ident()
            and self.path==owner_path(self.adapter,self.target,self.run) and self.parent is self._parent)
        self.file.guard();need(typed_equal(self.store.read(),self.state))
        if self.parent is not None:
            from adapters.pico4.create_journey import PicoCreateJourney
            need(isinstance(self.parent,PicoCreateJourney) and self.parent.adapter is self.adapter and self.parent.target==self.target
                and self.parent.run==self.run and self.parent.source.fixture_url==self.url
                and self.parent._operation_pending_peer is self.pending_gate)
    def _write(self,value):
        dto_bytes(value,65536);self.file.write(value,self.state);need(typed_equal(self.store.read(),value));self.state=deepcopy(value)
    def admit(self,budget):
        self.guard();budget.check()
        if self.parent is None:
            need(self.factory_calls==0);self.factory_calls+=1
            parent=self.factory(self.target,self.run)
            need(parent.source.fixture_url==self.url and not hasattr(parent,'_operation_pending_peer'))
            parent._operation_pending_peer=self.pending_gate;self.parent=self._parent=parent
        self.guard();budget.check();return self.parent
    def begin(self,value):
        self.guard();need(self.active is None and self.context is None)
        exact(value,{'budget','operation','arguments'});need(value['operation'] in ('prepare','act','cleanup'))
        budget=CreateActionBudget(value['budget']);parent=self.admit(budget)
        if value['operation']=='act':
            from feature_journeys.contract import arguments
            arguments('feature.create.act',value['arguments']);need(value['arguments']['runId']==self.run and value['arguments']['fixtureUrl']==self.url)
        else:need(value['arguments'] is None)
        self._write(dict(self.state,phase='begin-issued',pending=deepcopy(value)))
        self.active=deepcopy(value);self.budget=budget
        if self.worker_owner is None:
            need(parent.peer_state() is None or parent.peer_state()['phase']=='returned');context=parent.lock.held()
        else:context=parent.peer_input_boundary(self.peer_config.path,self.worker_owner)
        self.context=context
        try:
            context.__enter__();self.entered=True;self.guard();budget.check()
            self._write(dict(self.state,phase='begun'));return dict(picoCreateInputBoundaryVersion=VERSION,entered=True,peerLocked=self.worker_owner is not None)
        except BaseException:self.failed=True;raise
    def component(self,operation,arguments,budget_value):
        self.guard();need(operation in COMPONENTS)
        budget=self.budget if self.active is not None else CreateActionBudget(budget_value);budget.same(budget_value);parent=self.admit(budget)
        if self.active is not None:
            need(self.entered and operation==self.active['operation'] and typed_equal(arguments,self.active['arguments']) and self.state['phase']=='begun')
            parent.lock.assert_held()
        else:
            need(operation in ('prepare','sample','reconcile') or operation=='cleanup' and self.state['phase']=='peer-accepted'
                and parent.state()['cleanupStarted'] and parent.peer_state()['phase']=='returned')
        call=dict(operation=operation,arguments=deepcopy(arguments),budget=deepcopy(budget.value));dto_bytes(call,65536,arguments=True)
        self._write(dict(self.state,phase='component-issued',pending=call,calls=self.state['calls']+[call]))
        from adapters.pico4.create_journey import PicoCreateJourney
        try:
            result=PicoCreateJourney.cleanup(parent) if operation=='cleanup' and self.entered else PicoCreateJourney.invoke(parent,operation,arguments);self.guard();budget.check()
            self._write(dict(self.state,phase='retired' if operation=='cleanup' and parent.previous is None else 'component-returned',pending=None));return result
        except CreatePeerReturnPending:
            need(operation=='cleanup' and self.worker_owner is not None and self.entered)
            self._write(dict(self.state,phase='peer-return-pending'));return dict(picoCreateCleanupPendingVersion=VERSION,peerReturnPending=True,completedCleanup=False)
        except BaseException:self.failed=True;raise
    def end(self,budget_value):
        # Releasing the ACTUAL context is host-only and unconditional, even
        # after expiry. Its expired checks never become a green End receipt.
        need(self.host==host_identity() and self.thread==threading.get_ident() and self.active is not None and self.context is not None)
        original=self.budget;context=self.context;error=None
        try:
            self.guard(failed=True);need(typed_equal(original.value,budget_value));original.check()
        except BaseException as failure:error=failure
        try:
            if self.entered:context.__exit__(None,None,None)
        except BaseException as failure:
            if error is None:error=failure
        finally:self.context=None;self.entered=False
        if error is not None or self.failed:
            self.failed=True
            if error is not None:raise error
            need(False)
        original.check();phase=self.state['phase'];need(phase in ('component-returned','peer-return-pending'))
        self._write(dict(self.state,phase='awaiting-peer' if phase=='peer-return-pending' else 'ready',pending=None))
        self.active=self.budget=None;self.guard();original.check()
        return dict(picoCreateInputBoundaryVersion=VERSION,released=True)
    def _peer_pending(self,value):
        self.guard();need(self.entered and self.active['operation']=='cleanup' and self.worker_owner is not None
            and value['phase']=='issued' and value['scope']['parentHostProcessIdentity']==self.host and self.parent.state()['cleanupStarted'])
        self.budget.check();self.worker_owner.guard()
        from adapters.pico4.create_peer_actor import configuration
        config=configuration(self.peer_config.read())
        need(typed_equal(config,value) and self.worker_owner.configuration==self.peer_config.path)
        phase=self.parent.phase_fence();need(phase['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
        self.budget.check();raise CreatePeerReturnPending('Original live Create worker must return before Parent retirement')

    def start_peer(self,spec,budget_value,*,entry=None):
        """Original Parent launches the existing worker; no sibling ownership."""
        import subprocess
        import sys
        from adapters.pico4.create_peer_actor import configuration
        from adapters.observer_return import state as physical_state
        from adapters.pico4.operation_host import process_identity
        from fixture.chat_observer_process import LinuxChatObserverProcess
        from adapter_operation_host import PinnedFile,PipeOwner
        from adapters.pico4.operation_protocol import STRIPPED_ENV
        self.guard();need(self.active is None and self.worker is None and self.worker_owner is None)
        exact(spec,{'target','candidateArguments','fixtureUrl','actorToken','durationSeconds','artifactRoot'})
        dto_bytes(spec,65536,arguments=True);need(spec['fixtureUrl']+'/runs/'+self.run+'/'==self.url and number(spec['durationSeconds'],30,120))
        budget=CreateActionBudget(budget_value);parent=self.admit(budget)
        self._write(dict(self.state,phase='peer-start-issued'))
        scope=parent.issue_peer_scope();budget.check()
        owner_store=parent.source_store('peer');_header,raw,physical=physical_state(owner_store)
        selected=Path(__file__).resolve().with_name('feature_observer.py') if entry is None else Path(entry)
        executable=Path(sys.executable).resolve(strict=True)
        self.worker_entry=PinnedFile(selected,1024*1024);self.worker_executable=PinnedFile(executable,128*1024*1024)
        config=dict(spec,picoFeatureObserverVersion=5,area='create',peerOwner=str(owner_store.path),peerOwnerSha256=hashlib.sha256(raw).hexdigest(),
            peerOwnerStamp=physical,runId=self.run,originalRequestId=scope['requestId'],workerExecutableSha256=self.worker_executable.digest,workerEntrySha256=self.worker_entry.digest)
        self.peer_config=PrivateFeatureState(self.path.with_name(self.path.stem+'.peer-config.json'));need(self.peer_config.read() is None)
        self.peer_config.write(config,None);need(typed_equal(configuration(self.peer_config.read()),_header))
        self.worker_entry.check();self.worker_executable.check();budget.check()
        environment={key:value for key,value in os.environ.items() if key not in STRIPPED_ENV}
        self.worker=subprocess.Popen([str(executable),str(selected),'--config',str(self.peer_config.path)],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=environment)
        self.worker_pipes=[PipeOwner(self.worker.stdout),PipeOwner(self.worker.stderr)]
        self.worker_output=bytearray();self.worker_errors=bytearray()
        identity=process_identity(self.worker.pid);pid=self.worker.pid
        def owned(current):
            need(current==pid and process_identity(current)==identity)
            fields=(Path('/proc')/str(current)/'stat').read_text().rsplit(')',1)[1].split()
            return int(fields[1])==os.getpid() and host_identity()==self.host
        self.worker_owner=LinuxChatObserverProcess(identity,selected,self.peer_config.path,self.worker_executable.digest,self.worker_entry.digest,owned)
        self.peer_scope=scope;self.worker_owner.guard();budget.check()
        from adapters.script_journey.lock import ScriptSourceLock
        directory=Path(config['artifactRoot'])
        while True:
            self.worker_owner.guard();budget.check()
            with ScriptSourceLock(directory/'script-sources.lock').held():
                journal=PrivateFeatureState(directory/'create-peer-worker.json').read()
                source=PrivateFeatureState(directory/'create-peer-originals.json').read()
                if journal is not None and journal['phase']=='watching' and source is not None and source['pending'] is None and source['records']:break
            time.sleep(.01)

        self._write(dict(self.state,phase='peer-watching',peer=dict(hostProcessIdentity=identity,configuration=str(self.peer_config.path),requestId=scope['requestId'])))
        return dict(picoCreatePeerHostVersion=VERSION,hostProcessIdentity=identity,originalRequestId=scope['requestId'])

    def accept_peer(self,budget_value):
        """Read original return, echo once, then let SAME Parent own waitpid."""
        import select
        from adapters.observer_return import ObserverReturnReceiver
        from adapters.pico4.create_peer_parent import admit_return
        from adapters.pico4.create_peer_source import FAMILY
        from adapters.pico4.create_peer_actor import READY
        self.guard();need(self.active is None and self.context is None and self.state['phase']=='awaiting-peer' and self.worker_owner is not None)
        budget=CreateActionBudget(budget_value);self.worker_owner.guard()
        until=budget.value['deadlineMonotonic'];output=self.worker_output;errors=self.worker_errors
        while b'\n' not in output:
            budget.check();self.worker_owner.guard()
            ready,_,_=select.select([self.worker.stdout,self.worker.stderr],[],[],min(.05,max(0,until-time.monotonic())))
            for stream in ready:
                self.worker_pipes[0 if stream is self.worker.stdout else 1].check()
                available=128-len(output) if stream is self.worker.stdout else min(4096,16384-len(errors));need(available>0)
                data=os.read(stream.fileno(),available)
                need(data)
                if stream is self.worker.stdout:output.extend(data);need(len(output)<=128)
                else:errors.extend(data);need(len(errors)<=16384)
                # Fixed notification/diagnostics only, retained before parsing
                # or another read. No native acquisition or input is issued.
                self._write(dict(self.state,peerNotification=bytes(output).hex(),peerDiagnostics=bytes(errors).hex()))
        need(bytes(output)==(READY+'\n').encode())
        directory=Path(self.peer_config.read()['artifactRoot']);expected=dict(runId=self.run,family=FAMILY,
            producerHostProcessIdentity=self.worker_owner.process_identity,originalRequestId=self.peer_scope['requestId'])
        receiver=ObserverReturnReceiver(self.worker_owner,PrivateFeatureState(directory/'return.json'),PrivateFeatureState(directory/'consumption.json'),expected,
            admit=lambda raw,physical:admit_return(raw,physical,self.peer_scope))
        self._write(dict(self.state,phase='peer-consume-issued'));budget.check();receiver.acknowledge()
        while True:
            budget.check();event=os.waitid(os.P_PID,self.worker.pid,os.WEXITED|os.WNOWAIT|os.WNOHANG)
            if event is not None:break
            time.sleep(.01)
        need(event.si_status==0);budget.check();receipt=self.parent.accept_peer_return(receiver)
        need(self.parent._peer_worker_wait[1]==(self.worker.pid,0));self.worker.returncode=0;self.worker_owner=None
        for pipe in self.worker_pipes:pipe.close()
        need(self.worker_entry.close() and self.worker_executable.close())
        self._write(dict(self.state,phase='peer-accepted',peerReceipt=receipt,peerWaitStatus=0));budget.check();return deepcopy(receipt)

    def control(self):
        self.guard()
        if self.active is not None:
            try:self.budget.check()
            except BaseException:
                self.failed=True;self.unwind();raise

    def unwind(self):
        """Only original local context release, including after expiry/error."""
        need(self.host==host_identity() and self.thread==threading.get_ident())
        context=self.context;self.context=None
        try:
            if context is not None and self.entered:context.__exit__(None,None,None)
        finally:self.entered=False

    def dispatch(self,value):
        from adapters.pico4.create_operation_protocol import validate
        validate(value);need(value['runId']==self.run and value['fixtureUrl']==self.url)
        operation=value['operation'];fields=value['arguments'];budget=value['budget']
        try:
            if operation=='input.end':return self.end(budget)
            self.control()
            if operation=='input.begin':return self.begin(dict(fields,budget=budget))
            if operation=='peer.start':return self.start_peer(fields,budget)
            if operation=='peer.accept':return self.accept_peer(budget)
            return self.component(operation,fields,budget)
        except BaseException:
            self.failed=True
            try:self.unwind()
            except Exception:pass
            raise

    def close_host(self):
        self.guard();need(self.context is None and self.active is None and self.parent is not None
            and self.parent.previous is None and self.parent.store.read() is None and self.worker_owner is None
            and self.state['phase']=='retired' and (self.worker is None or self.worker.returncode==0))
        self._write(dict(self.state,phase='closed'));self.guard();need(self.file.close_host())
