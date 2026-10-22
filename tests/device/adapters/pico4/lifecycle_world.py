"""Durable ordinary Pico world input, original consumption/feet and neutral quiet.

Partial Lifecycle owner only. No editor generation, peer, stale callback or
complete cleanup verdict can be inferred from this component's reports.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
from adapters.native_feature_observation import decode,exact,integer,need,number
from adapters.native_chat_view import measured_keyboard
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.pico4 import lifecycle_drive as drive,lifecycle_gesture as gesture,lifecycle_source as ui
from adapters.pico4.lifecycle_back import frame
from adapters.script_journey.history import pack,unpack
from adapters.script_journey.lock import ScriptSourceLock
from openxr_input.adapter_session import PicoOpenXrAdapterSession
from openxr_input.controller_protocol import validate_envelope

VERSION=1
MOVE=dict(direction='forward',durationSeconds=2.0,strength=.2)
PHASES=('reserved','enveloped','consumed','release-issued','quiet')
MAX_FRAMES=128


def envelope(value,profile):
    validate_envelope(value,profile)
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and len(value['commands'])==1)
    need(value['commands'][0]==dict(id='input-move-'+str(value['sequence']),operation='input.move',arguments=MOVE))


def neutral(packet):
    source=packet['source']
    need(source['known'] and not source['activeGesture'] and gesture.known(source['current']) and not gesture.nonzero(source['current']))


class PicoLifecycleWorld:
    def __init__(self,source,axes,avatar,session,path,run,binding,guard,source_lock,*,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(source,ui.PicoLifecycleSource) and isinstance(axes,gesture.PicoLifecycleGesture)
            and isinstance(avatar,drive.PicoLifecycleDrive) and isinstance(session,PicoOpenXrAdapterSession)
            and isinstance(source_lock,ScriptSourceLock) and ui.nonce(run) and all(callable(f) for f in (guard,monotonic,sleep)))
        self.source,self.axes,self.avatar,self.session=source,axes,avatar,session
        self.run,self.binding,self.guard=run,deepcopy(context(binding)),guard
        self.pid=source.pid;self.identity=self.binding['processIdentity'];need(axes.pid==avatar.pid==self.pid==int(self.identity.split(':')[0]))
        self.store=PrivateFeatureState(path);self.lock=source_lock
        need(self.lock.path==self.store.path.with_name('script-sources.lock'))
        for reader in (source,axes,avatar):
            need(reader.source_lock is None or reader.source_lock is self.lock);reader.source_lock=self.lock
        self.monotonic,self.sleep=monotonic,sleep;self.disk=self.state=self.anchor=self.last_clock=self.acquired_start=self.fresh_anchor=None
        with self.lock.held():self.load()

    def now(self):
        need(self.guard() is not False);value=self.monotonic()
        need(number(value,0,1e15) and (self.last_clock is None or value>=self.last_clock));self.last_clock=value;return value

    def fresh_current(self):
        # Pure host check, safe inside the locked pre-transport intent callback.
        need(self.fresh_anchor is not None);start,requested,captured=self.fresh_anchor;now=self.monotonic()
        need(number(now,0,1e15) and self.last_clock<=now and requested-captured+(now-start)*1000<=1500)

    def originals(self,row):
        exact(row,{'ui','gesture','drive','hostMonotonic'})
        need(number(row['hostMonotonic'],0,1e15));result={}
        for name,validator in (('ui',ui.validate),('gesture',gesture.validate),('drive',drive.validate)):
            original=row[name];exact(original,{'raw','sha256'});need(frame(original['raw'])==original)
            value=decode(original['raw']);need(value['runId']==self.run)
            validator(value,value,self.pid,value['capturedEpochMs']);result[name]=value
        return result

    @staticmethod
    def editor_gate(packet,index):
        current=ui.current_editor(packet);source=packet['source']
        if index==0:
            need(current is not None and current['kind']=='create' and current['focused'] and current['visible']
                and source['tabletShown'] and not source['onHomeScreen'] and measured_keyboard(source['keyboard']) is True)
        else:need(current is None and not source['tabletShown'] and measured_keyboard(source['keyboard']) is False
            and not any(row['focused'] for row in source['editors']))

    def save(self,state):
        # Host-only intent callbacks run under the exact native session cursor.
        self.lock.assert_held();need(self.store.read()==self.disk)
        disk=dict(lifecycleWorldOwnerVersion=VERSION,runId=self.run,binding=self.binding,payload=pack([state]))
        self.store.write(disk,self.disk);need(self.store.read()==disk);self.disk,self.state=deepcopy(disk),deepcopy(state)

    def load(self):
        self.lock.assert_held();self.now();disk=self.store.read()
        if self.disk is not None:need(disk==self.disk)
        if disk is None:need(self.state is None);return
        history=LifecycleWorldHistory(self.run,self.binding,self.pid,self.session.profile)
        state,previous,self.anchor=history.validate(disk)
        for reader,name in ((self.source,'ui'),(self.axes,'gesture'),(self.avatar,'drive')):
            value=ui.summary(previous[name]) if name=='ui' else previous[name]
            if reader.previous is None:reader.restore(value)
            else:need(reader.previous==value)
        self.disk,self.state=deepcopy(disk),deepcopy(state)

    def acquire(self):
        start=self.now();requested=self.axes.clock_ms();need(integer(requested,1));rows={};packets={}
        for name,reader in (('gesture',self.axes),('drive',self.avatar),('ui',self.source)):
            packets[name]=reader.capture(self.run);rows[name]=frame(reader.last_raw)
            need(rows[name]['sha256']==reader.last_sha256 and decode(rows[name]['raw'])==packets[name])
        rows['hostMonotonic']=self.now();need(rows['hostMonotonic']-start<=1.5)
        epoch=self.axes.clock_ms();need(integer(epoch,1))
        stamps=[value['capturedEpochMs'] for value in packets.values()]
        if packets['gesture']['source']['known']:stamps.append(packets['gesture']['source']['frameEpochMs'])
        for stamp in stamps:need(-250<=epoch-stamp<=1500)
        self.originals(rows);self.acquired_start=start;self.fresh_anchor=(start,requested,min(stamps));self.fresh_current()
        return rows,packets,start

    def current(self):
        self.lock.assert_held();need(self.state is not None and len(self.state['frames'])<MAX_FRAMES)
        rows,packets,start=self.acquire();state=deepcopy(self.state);state['frames'].append(rows);self.save(state)
        self.now();self.fresh_current();return packets

    def attempts(self,state,current,*,through=None):
        baseline=self.originals(state['frames'][0])['gesture'];gesture.accept(baseline,current)
        old=len(baseline['source']['events']);events=[row for row in current['source']['events'][old:] if row['kind']=='started']
        attempts=state['attempts'] if through is None else state['attempts'][:through]
        need(len(events)==len(attempts))
        for event,attempt in zip(events,attempts):
            need(attempt['envelope'] is not None);gesture.consumed(event,attempt['envelope'])
            need(abs(event['sample']['raw'][0])<=1e-6 and abs(event['sample']['raw'][1]-MOVE['strength'])<=1e-6)
            before=self.originals(state['frames'][attempt['before']])['gesture']
            need(event['frameSequence']>before['source']['frameSequence'] and event['occurredEpochMs']>=before['capturedEpochMs'])
        return events

    def prepare(self):
        with self.lock.held():
            self.load();need(self.state is None);rows,packets,start=self.acquire()
            neutral(packets['gesture']);drive.AvatarDisplacement(packets['drive'])
            need(ui.current_editor(packets['ui']) is None and measured_keyboard(packets['ui']['source']['keyboard']) is False
                and not any(row['focused'] for row in packets['ui']['source']['editors']))
            self.save(dict(frames=[rows],attempts=[]));self.anchor=drive.AvatarDisplacement(packets['drive']);need(self.now()-start<=1.5)
            self.fresh_current();return self.report(packets,0)

    def report(self,packets,count):
        actual=self.anchor.measure(packets['drive'])
        result=dict(worldAttempts=count,heldInputs=actual['heldInputs'],worldDisplacement=actual['worldDisplacement'],
            positionDelta=dict(zip(('x','y','z'),actual['positionDelta'])),originals=deepcopy(packets))
        self.now();self.fresh_current();return result

    def world_input(self):
        try:
            with self.lock.held():
                self.load();need(self.state is not None and len(self.state['attempts'])<2
                    and (not self.state['attempts'] or self.state['attempts'][-1]['phase']=='quiet'))
                packets=self.current();neutral(packets['gesture']);need(not self.anchor.measure(packets['drive'])['heldInputs'])
                self.editor_gate(packets['ui'],len(self.state['attempts']))
                state=deepcopy(self.state);state['attempts'].append(dict(phase='reserved',before=len(state['frames'])-1,
                    envelope=None,receiptFrame=None,receiptId=None,quiet=None));self.save(state)
                self.now()
                def intent(original):
                    envelope(original,self.session.profile);state=deepcopy(self.state);attempt=state['attempts'][-1]
                    need(attempt['phase']=='reserved');attempt.update(phase='enveloped',envelope=deepcopy(original));self.save(state)
                    self.fresh_current()
                self.session.stage(self.identity,'input.move',deepcopy(MOVE),intent=intent)
                return self.observe_locked()
        except Exception:raise NativeUIError('Pico world input unresolved; original ownership retained') from None

    def observe_locked(self):
        self.lock.assert_held();need(self.state is not None and self.state['attempts'] and self.state['attempts'][-1]['envelope'] is not None)
        packets=self.current();events=self.attempts(self.state,packets['gesture']);state=deepcopy(self.state);attempt=state['attempts'][-1]
        if attempt['phase']=='enveloped':
            attempt.update(phase='consumed',receiptFrame=len(state['frames'])-1,receiptId=events[-1]['id']);self.save(state)
        need(attempt['phase'] in ('consumed','release-issued','quiet'));return self.report(packets,len(events))

    def reconcile(self):
        try:
            with self.lock.held():self.load();return self.observe_locked()
        except Exception:raise NativeUIError('Pico world reconciliation unresolved; no input repeated') from None

    def release(self):
        try:
            with self.lock.held():
                self.load();need(self.state is not None and self.state['attempts']);attempt=self.state['attempts'][-1]
                need(attempt['phase'] in ('consumed','release-issued','quiet'))
                if attempt['phase']=='consumed':
                    def intent():
                        state=deepcopy(self.state);need(state['attempts'][-1]['phase']=='consumed')
                        state['attempts'][-1]['phase']='release-issued';self.save(state)
                    self.session.neutralize_owned(self.identity,attempt['envelope'],intent=intent)
                # A lost release response is reconciled read-only, never resent.
                self.session.require_owned_neutral(self.identity,attempt['envelope'])
                quiet=drive.AvatarReleaseWindow(self.anchor);first=len(self.state['frames']);started=self.now()
                for index in range(41):
                    packets=self.current();self.attempts(self.state,packets['gesture']);neutral(packets['gesture']);now=self.now()
                    need(now-started<20)
                    if quiet.observe(packets['drive'],now):
                        self.session.require_owned_neutral(self.identity,attempt['envelope']);need(self.now()-now<=1.5)
                        state=deepcopy(self.state);state['attempts'][-1].update(phase='quiet',quiet=dict(first=first,last=len(state['frames'])-1));self.save(state)
                        need(self.now()-now<=1.5);return self.report(packets,len(state['attempts']))
                    need(index<40);self.sleep(.25)
        except Exception:raise NativeUIError('Pico world release unresolved; original ownership retained') from None


class LifecycleWorldHistory:
    """Exact shared historical validators; no transport/input/lifetime authority."""
    originals=PicoLifecycleWorld.originals
    attempts=PicoLifecycleWorld.attempts
    editor_gate=staticmethod(PicoLifecycleWorld.editor_gate)

    def __init__(self,run,binding,pid,profile):
        need(ui.nonce(run) and integer(pid,1));self.run,self.binding,self.pid,self.profile=run,deepcopy(context(binding)),pid,profile
        need(int(self.binding['processIdentity'].split(':')[0])==pid);self.state=self.anchor=None

    def validate(self,disk):
        exact(disk,{'lifecycleWorldOwnerVersion','runId','binding','payload'})
        need(type(disk['lifecycleWorldOwnerVersion']) is int and disk['lifecycleWorldOwnerVersion']==VERSION
            and disk['runId']==self.run and disk['binding']==self.binding)
        payload=unpack(disk['payload']);need(len(payload)==1);state=payload[0]
        exact(state,{'frames','attempts'});need(type(state['frames']) is list and 1<=len(state['frames'])<=MAX_FRAMES
            and type(state['attempts']) is list and len(state['attempts'])<=2)
        previous=None;seen={name:set() for name in ('ui','gesture','drive')}
        for row in state['frames']:
            current=self.originals(row)
            if previous:
                ui.accept(ui.summary(previous['ui']),ui.summary(current['ui']));gesture.accept(previous['gesture'],current['gesture'])
                drive.continuity(previous['drive'],current['drive']);need(row['hostMonotonic']>=host)
            for name,value in current.items():need(value['commandId'] not in seen[name]);seen[name].add(value['commandId'])
            previous=current;host=row['hostMonotonic']
        initial=self.originals(state['frames'][0]);neutral(initial['gesture']);self.anchor=drive.AvatarDisplacement(initial['drive'])
        need(ui.current_editor(initial['ui']) is None and measured_keyboard(initial['ui']['source']['keyboard']) is False
            and not any(row['focused'] for row in initial['ui']['source']['editors']))
        prior=-1
        for index,attempt in enumerate(state['attempts']):
            exact(attempt,{'phase','before','envelope','receiptFrame','receiptId','quiet'})
            need(attempt['phase'] in PHASES and integer(attempt['before'],prior+1,len(state['frames'])-1))
            if index:need(state['attempts'][index-1]['phase']=='quiet'
                and attempt['before']>state['attempts'][index-1]['quiet']['last'])
            prior=attempt['before'];before=self.originals(state['frames'][prior]);neutral(before['gesture']);self.editor_gate(before['ui'],index)
            if attempt['envelope'] is None:need(attempt['phase']=='reserved')
            else:envelope(attempt['envelope'],self.profile);need(attempt['phase']!='reserved')
            if attempt['phase'] in ('consumed','release-issued','quiet'):
                need(integer(attempt['receiptFrame'],prior+1,len(state['frames'])-1) and ui.nonce(attempt['receiptId']))
                packet=self.originals(state['frames'][attempt['receiptFrame']])
                events=self.attempts(state,packet['gesture'],through=index+1)
                need(events[-1]['id']==attempt['receiptId'])
            else:need(attempt['receiptFrame'] is None and attempt['receiptId'] is None)
            if attempt['phase']=='quiet':
                exact(attempt['quiet'],{'first','last'});first,last=attempt['quiet']['first'],attempt['quiet']['last']
                need(integer(first,attempt['receiptFrame']+1,len(state['frames'])-1) and integer(last,first+1,len(state['frames'])-1))
                quiet=drive.AvatarReleaseWindow(self.anchor)
                for row in state['frames'][first:last+1]:
                    current=self.originals(row);neutral(current['gesture']);result=quiet.observe(current['drive'],row['hostMonotonic'])
                need(result)
            else:need(attempt['quiet'] is None)
        self.state=deepcopy(state)
        return deepcopy(state),deepcopy(previous),self.anchor
