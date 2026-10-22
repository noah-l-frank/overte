"""Control only a dedicated owned MessagesMixer process, never the whole domain."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from copy import deepcopy
import hashlib
import json
import re
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

from adapters.normal_ui import NativeUIError

from adapters.native_feature_observation import need


def start_identity(pid):
    fields=(Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split()
    need(fields[0] not in ('Z','X') and len(fields)>19 and fields[19].isdecimal())
    return fields[19]


def valid_control_command(command):
    return (type(command) is dict and set(command)=={'schemaVersion','commandId','runId','instance','observedGeneration','action'}
        and type(command['schemaVersion']) is int and command['schemaVersion']==2
        and all(type(command[key]) is str and re.fullmatch('[0-9a-f]{32}',command[key])
                for key in ('commandId','runId','instance'))
        and type(command['observedGeneration']) is int and command['observedGeneration']>0
        and command['action'] in ('offline','online'))


class MessagesMixer:
    """Process-state receipts are never native node/readiness/delivery receipts.

    spawn() must create a fresh -t 4 process for this fixture. write_intent records
    the original process before mutation. clear_intent runs only after observed
    completion; a failed write/stop/start must leave recovery intent intact.
    """
    def __init__(self,process,owned,spawn,write_intent,clear_intent,read_intent):
        need(sys.platform.startswith('linux') and all(callable(v) for v in (owned,spawn,write_intent,clear_intent,read_intent)))
        self.owned,self.spawn,self.write_intent,self.clear_intent=owned,spawn,write_intent,clear_intent
        self.read_intent=read_intent;need(self.read_intent() is None)
        self.process=process;self.start=start_identity(process.pid);self.generation=1
        self.intent=None;self.dispatched=False;self.last_stopped=None
        self._await_guard()

    def _await_guard(self):
        # A shebang launcher can exec again after Popen returns. Linux may
        # expose an empty cmdline/environment during that bounded exec window.
        # Keep the actual child/start pinned; never accept an unqualified child.
        started=time.monotonic()
        for _ in range(51):
            try:self._guard();return
            except NativeUIError:
                if self.process.poll() is not None or time.monotonic()-started>=1:raise
                need(start_identity(self.process.pid)==self.start)
                time.sleep(.02)
        raise NativeUIError('Owned MessagesMixer startup qualification timed out')

    def _guard(self):
        need(self.process is not None and self.process.poll() is None and self.owned(self.process.pid) is True
             and start_identity(self.process.pid)==self.start)
        raw=(Path('/proc')/str(self.process.pid)/'cmdline').read_bytes().split(b'\0')
        need(raw.count(b'-t')==1 and raw[raw.index(b'-t')+1]==b'4'
             and b'--pool' not in raw and b'--testScript' not in raw and b'--e2eChatActorDir' not in raw)

    def state(self):
        actual_intent=self.read_intent()
        need(actual_intent is None or self.intent is not None and actual_intent==self.intent)
        if self.process is not None:self._await_guard()
        elif self.last_stopped is not None:
            try:
                fields=(Path('/proc')/str(self.last_stopped[0])/'stat').read_text().rsplit(')',1)[1].split()
                need(len(fields)>19 and fields[19]!=self.last_stopped[1])
            except FileNotFoundError:pass
        return dict(mixerProcessVersion=1,running=self.process is not None,generation=self.generation,pending=self.intent is not None)

    def transition(self,action):
        need(action in ('offline','online'))
        before=self.state()
        if self.intent is not None:
            if before['running']==(self.intent['action']=='online') or not self.dispatched:
                # Finish a failed journal removal, or cancel an intent whose
                # persistence failed before any actual process input.
                self.clear_intent();need(self.read_intent() is None);self.intent=None;self.dispatched=False;before=self.state()
            else:raise RuntimeError('Owned MessagesMixer transition remains unresolved')
        if before['running']==(action=='online'):return before
        self.intent=dict(mixerProcessVersion=1,action=action,generation=self.generation,
            processId=self.process.pid if self.process is not None else None,startIdentity=self.start)
        self.write_intent(self.intent);need(self.read_intent()==self.intent)
        self.dispatched=True
        if action=='offline':
            original=self.process
            descriptor=os.pidfd_open(original.pid)
            try:
                # Pin before rechecking both original start identity and owner.
                # A reused PID must never retarget fixture control.
                self._guard()
                for number in (signal.SIGTERM,signal.SIGKILL):
                    try:signal.pidfd_send_signal(descriptor,number)
                    except ProcessLookupError:pass
                    try:original.wait(timeout=2);break
                    except subprocess.TimeoutExpired:continue
                need(original.poll() is not None)
            finally:os.close(descriptor)
            self.last_stopped=(original.pid,self.start);self.process=None
        else:
            actual=self.spawn()
            # Retain a just-created process even if qualification fails, so the
            # enclosing fixture can still stop its own failed startup child.
            self.process=actual;self.start=start_identity(actual.pid);self._await_guard()
        self.generation+=1
        actual=self.state();need(actual['running']==(action=='online'))
        self.clear_intent();need(self.read_intent() is None);self.intent=None;self.dispatched=False;return self.state()


class MessagesMixerObservation:
    """Read the existing mixer owner and all original other fixture processes.

    This creates no process and sends no signal. Its controller instance exists
    from the actual fixture stack startup, rather than an adapter's first read.
    Private kernel identities never expose PIDs, paths or the owner credential.
    """
    ROLES={'domain-server','assignment-0','assignment-1','assignment-3','assignment-5','assignment-6','domain-agent','peer-agent'}

    def __init__(self,mixer,processes,owned,domain_id,stack_generation):
        need(isinstance(mixer,MessagesMixer) and type(processes) is dict and set(processes)==self.ROLES
            and callable(owned) and type(domain_id) is str and str(uuid.UUID(domain_id))==domain_id
            and uuid.UUID(domain_id).int!=0 and type(stack_generation) is int and stack_generation>0
            and len({process.pid for process in processes.values()})==len(processes))
        self.mixer,self.processes,self.owned=mixer,dict(processes),owned
        self.domain_id,self.stack_generation=domain_id,stack_generation
        self.instance=uuid.uuid4().hex;self.sequence=0;self.epoch=0;self.last=None
        self.boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        need(str(uuid.UUID(self.boot))==self.boot)
        self.original={role:self._process(process) for role,process in self.processes.items()}
        self.run=None;self.offline_fenced=False;self.commands=[]

    def _process(self,process):
        need(process.poll() is None and self.owned(process.pid) is True)
        start=start_identity(process.pid);path=Path('/proc')/str(process.pid)
        before=os.stat(path/'exe');uid=path.stat().st_uid
        need(uid==os.geteuid() and before.st_size>0 and start_identity(process.pid)==start
            and process.poll() is None and self.owned(process.pid) is True)
        after=os.stat(path/'exe')
        def node(info):
            return [str(info.st_dev),str(info.st_ino),info.st_size,info.st_mode,info.st_nlink,info.st_mtime_ns,info.st_ctime_ns]
        need(node(before)==node(after))
        return [process.pid,start,uid,node(before)]

    def _hash(self,value):
        return hashlib.sha256(json.dumps([self.instance,self.boot,value],sort_keys=True,separators=(',',':')).encode()).hexdigest()

    def admit(self,command):
        """Called only under the existing fixture transition lock.

        Consume the original nonce before any process input. The online fence
        is irrevocable for this controller/run, even if that input fails or its
        response is lost. A delayed offline request cannot undo recovery.
        """
        need(valid_control_command(command)
            and command['instance']==self.instance and command['action'] in ('offline','online')
            and type(command['observedGeneration']) is int
            and command['observedGeneration']==self.mixer.state()['generation']
            and (self.run is None or self.run==command['runId'])
            and not any(row['commandId']==command['commandId'] or row['action']==command['action'] for row in self.commands)
            and not any(row['status']=='pending' for row in self.commands)
            and (command['action']=='online' or not self.offline_fenced))
        epoch=int(time.time()*1000);need(epoch>0 and epoch>=self.epoch
            and all(epoch>=row['completedEpochMs'] for row in self.commands))
        self.run=command['runId']
        if command['action']=='online':self.offline_fenced=True
        self.commands.append(dict(commandId=command['commandId'],action=command['action'],
            observedGeneration=command['observedGeneration'],admittedEpochMs=epoch,completedEpochMs=None,status='pending'))

    def complete(self,command,*,failed=False):
        need(type(failed) is bool and self.run==command['runId'] and self.commands
            and self.commands[-1]['commandId']==command['commandId'] and self.commands[-1]['status']=='pending')
        row=self.commands[-1];epoch=int(time.time()*1000);need(epoch>=row['admittedEpochMs'] and epoch>=self.epoch)
        row.update(completedEpochMs=epoch,status='failed' if failed else 'completed')

    def state(self):
        started=time.monotonic();epoch=int(time.time()*1000)
        need(epoch>0 and epoch>=self.epoch and Path('/proc/sys/kernel/random/boot_id').read_text().strip()==self.boot)
        before=self.mixer.state();actual={role:self._process(process) for role,process in self.processes.items()}
        need(actual==self.original)
        process=self.mixer.process
        mixer_identity=self._hash(self._process(process)) if process is not None else None
        need(self.mixer.state()==before and self.mixer.process is process)
        # Requalify original non-mixer processes after the mixer read as well.
        need({role:self._process(process) for role,process in self.processes.items()}==actual)
        finished=int(time.time()*1000)
        need(epoch<=finished<=epoch+1500 and 0<=time.monotonic()-started<=1.5 and self.sequence<9007199254740991
            and all(finished>=row['admittedEpochMs'] and (row['completedEpochMs'] is None or finished>=row['completedEpochMs']) for row in self.commands))
        if self.last is not None:
            need(before['generation']>=self.last['mixer']['generation'])
            if before['generation']==self.last['mixer']['generation']:
                need(before['running']==self.last['mixer']['running'] and mixer_identity==self.last['mixerIdentity'])
        self.sequence+=1;self.epoch=finished
        value=dict(mixerControlVersion=2,runId=self.run,offlineFenced=self.offline_fenced,commands=deepcopy(self.commands),instance=self.instance,sequence=self.sequence,capturedEpochMs=finished,
            domainId=self.domain_id,stackGeneration=self.stack_generation,
            processes={role:self._hash(row) for role,row in actual.items()},mixer=before,mixerIdentity=mixer_identity)
        self.last=deepcopy(value);return value
