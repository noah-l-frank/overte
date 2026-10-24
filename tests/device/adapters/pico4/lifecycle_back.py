"""One durable normal Pico X/Back, with original editor/keyboard quiet.

This is a partial Lifecycle input primitive. Retained contexts, uncertain
streams and original proofs remain owned; no full feature verdict is produced.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import time
from adapters.native_feature_observation import decode, exact, integer, need, number
from adapters.native_chat_view import measured_keyboard
from adapters.normal_feature_state import PrivateFeatureState, context
from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_source import (PicoLifecycleSource, accept, current_editor, nonce, summary, validate)
from adapters.script_journey.history import canonical, pack, unpack
from adapters.script_journey.lock import ScriptSourceLock
from openxr_input.adapter_session import PicoOpenXrAdapterSession
from openxr_input.controller_protocol import validate_envelope

VERSION=1
BUTTON=dict(hand='left',control='primary',holdMilliseconds=120)
MAX_FRAMES=128


def envelope(value,profile):
    validate_envelope(value,profile)
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1)
    need(len(value['commands'])==1)
    command=value['commands'][0]
    need(command==dict(id='controller-button-'+str(value['sequence']),operation='controller.button',arguments=BUTTON))
    return value


def frame(raw):
    need(type(raw) is str)
    return dict(raw=raw,sha256=hashlib.sha256(raw.encode()).hexdigest())


def validate_history(disk,run,binding,pid,profile):
    """Validate the immutable original Back journal without any live IO."""
    def original_packet(original):
        exact(original,{'raw','sha256'});need(frame(original['raw'])==original)
        value=decode(original['raw']);validate(value,value,pid,value['capturedEpochMs']);need(value['runId']==run);return value
    exact(disk,{'lifecycleBackOwnerVersion','runId','binding','payload'})
    need(type(disk['lifecycleBackOwnerVersion']) is int and disk['lifecycleBackOwnerVersion']==VERSION
        and disk['runId']==run and disk['binding']==binding)
    payload=unpack(disk['payload']);need(len(payload)==1)
    value=payload[0];exact(value,{'phase','originalId','envelope','frames','neutral','quiet'})
    need(value['phase'] in ('reserved','enveloped','retained','released') and nonce(value['originalId'])
        and type(value['frames']) is list and 1<=len(value['frames'])<=MAX_FRAMES)
    previous=None;commands=set()
    for original in value['frames']:
        packet=original_packet(original);need(packet['commandId'] not in commands);commands.add(packet['commandId'])
        previous=accept(previous,summary(packet))
    before=original_packet(value['frames'][0]);editor=current_editor(before)
    need(editor is not None and editor['id']==value['originalId'] and editor['kind']=='create'
        and editor['visible'] and before['source']['tabletShown'] and not before['source']['onHomeScreen'])
    if value['envelope'] is None:need(value['phase']=='reserved' and len(value['frames'])==1)
    else:envelope(value['envelope'],profile);need(value['phase']!='reserved')
    if value['phase'] in ('retained','released'):
        PicoLifecycleBack.neutral(value['neutral'],value['envelope'],before['capturedEpochMs'])
        quiet=value['quiet'];exact(quiet,{'first','last'})
        need(integer(quiet['first'],1,len(value['frames'])-1) and integer(quiet['last'],quiet['first'],len(value['frames'])-1))
        samples=[original_packet(row) for row in value['frames'][quiet['first']:quiet['last']+1]]
        need(len(samples)>=2 and samples[-1]['capturedEpochMs']-samples[0]['capturedEpochMs']>=3000)
        for packet in samples:PicoLifecycleBack.home(packet,value['originalId'])
        retired=PicoLifecycleBack.retired(samples[-1],value['originalId'])
        need((value['phase']=='released')==retired)
    else:need(value['neutral'] is None and value['quiet'] is None)
    return deepcopy(value),deepcopy(previous)


class PicoLifecycleBack:
    def __init__(self,source,session,path,run,binding,guard,*,monotonic=time.monotonic,sleep=time.sleep,source_lock=None):
        need(isinstance(source,PicoLifecycleSource) and isinstance(session,PicoOpenXrAdapterSession)
            and nonce(run) and all(callable(f) for f in (guard,monotonic,sleep)))
        self.source,self.session,self.run,self.guard=source,session,run,guard
        self.binding=deepcopy(context(binding));self.identity=self.binding['processIdentity']
        need(source.pid==int(self.identity.split(':')[0]))
        self.store=PrivateFeatureState(path);self.lock=ScriptSourceLock(self.store.path.with_suffix('.lock'))
        self.source_lock=source_lock or source.source_lock or ScriptSourceLock(self.store.path.with_name('script-sources.lock'))
        need(isinstance(self.source_lock,ScriptSourceLock) and (source.source_lock is None or source.source_lock is self.source_lock))
        source.source_lock=self.source_lock
        self.monotonic,self.sleep,self.clock,self.deadline=monotonic,sleep,None,None
        self.disk,self.state,self.anchor=None,None,None
        with self.source_lock.held(),self.lock.held():self.load()

    def now(self):
        need(self.guard() is not False);now=self.monotonic()
        need(number(now,0,1e15) and (self.clock is None or self.clock<=now)
            and (self.deadline is None or now<=self.deadline))
        self.clock=now;return now

    def packet(self,value):
        exact(value,{'raw','sha256'});need(frame(value['raw'])==value)
        result=decode(value['raw'])
        validate(result,dict(commandId=result['commandId'],runId=self.run),self.source.pid,result['capturedEpochMs'])
        return result

    def load(self):
        self.lock.assert_held();need(self.guard() is not False)
        disk=self.store.read()
        if self.disk is not None:need(disk==self.disk)
        if disk is None:need(self.state is None);return
        value,previous=validate_history(disk,self.run,self.binding,self.source.pid,self.session.profile)
        if self.source.previous is None:self.source.restore(previous)
        else:need(self.source.previous==previous)
        self.disk,self.state=deepcopy(disk),deepcopy(value)

    def save(self,value):
        # Deliberately host-only. The intent callback runs while the exact
        # session sequence is locked; reentering guard/session/ADB deadlocks.
        self.lock.assert_held();need(self.store.read()==self.disk)
        disk=dict(lifecycleBackOwnerVersion=VERSION,runId=self.run,binding=self.binding,payload=pack([value]))
        self.store.write(disk,self.disk);need(self.store.read()==disk)
        self.disk,self.state=deepcopy(disk),deepcopy(value)

    def fresh_packet(self):
        # Host-only, including in the locked pre-transport intent callback.
        # Count all parsing, compression, final guards and status reads after
        # acquisition even when the device clock itself stops advancing.
        need(self.anchor is not None)
        started,requested,captured=self.anchor;now=self.monotonic()
        need(number(now,0,1e15) and (self.clock is None or self.clock<=now)
            and (self.deadline is None or now<=self.deadline)
            and requested-captured+(now-started)*1000<=1500)
        self.clock=now

    def acquire(self):
        self.source_lock.assert_held()
        started=self.now();requested=self.source.clock_ms();need(integer(requested,1))
        packet=self.source.capture(self.run);self.now()
        self.anchor=(started,requested,packet['capturedEpochMs']);self.fresh_packet()
        return packet

    def capture(self):
        self.now();need(self.state is not None and len(self.state['frames'])<MAX_FRAMES)
        packet=self.acquire()
        need(frame(self.source.last_raw)['sha256']==self.source.last_sha256 and self.packet(frame(self.source.last_raw))==packet)
        value=deepcopy(self.state);value['frames'].append(frame(self.source.last_raw));self.save(value)
        self.now();self.fresh_packet();return packet

    @staticmethod
    def row(packet,original):
        rows=[row for row in packet['source']['editors'] if row['id']==original];need(len(rows)==1);return rows[0]

    @classmethod
    def retired(cls,packet,original):
        row=cls.row(packet,original)
        return not any(row[key] for key in ('fieldAlive','pageAlive','contextAlive'))

    @classmethod
    def home(cls,packet,original):
        source=packet['source'];row=cls.row(packet,original)
        need(source['tabletShown'] and source['onHomeScreen'] and source['current']==''
            and not row['fieldAlive'] and not row['pageAlive'] and not row['current']
            and not any(editor['focused'] for editor in source['editors'])
            and measured_keyboard(source['keyboard']) is False)
        return row

    @staticmethod
    def neutral(value,owned,epoch):
        need(type(value) is dict and value.get('state')=='neutral' and integer(value.get('acceptedSequence'),1) and value.get('acceptedSequence')==owned['sequence']
            and value.get('acceptedNonce')=='[redacted]' and value.get('activeCommandId')==''
            and number(value.get('updatedEpochMs'),epoch,1e15))
        return value

    def back(self,*,original_id=None):
        try:
            with self.source_lock.held(),self.lock.held():
                self.load();need(self.state is None);self.deadline=self.now()+10
                before=self.acquire();editor=current_editor(before)
                need((original_id is None or nonce(original_id)) and editor is not None
                    and (original_id is None or editor['id']==original_id) and editor['kind']=='create' and editor['visible']
                    and before['source']['tabletShown'] and not before['source']['onHomeScreen'])
                from adapters.pico4.lifecycle_operations import phase
                if phase(self) is not None:phase(self).mark()
                self.save(dict(phase='reserved',originalId=editor['id'],envelope=None,
                    frames=[frame(self.source.last_raw)],neutral=None,quiet=None))
                def intent(original):
                    need(self.state['phase']=='reserved' and self.state['envelope'] is None)
                    envelope(original,self.session.profile)
                    value=deepcopy(self.state);value.update(phase='enveloped',envelope=deepcopy(original));self.save(value)
                    self.fresh_packet()
                    if phase(self) is not None:phase(self).host_fresh()
                self.now()
                if phase(self) is not None:phase(self).check()
                def before_publish(original):
                    need(original==self.state['envelope']);self.fresh_packet();phase(self).host_fresh()
                # The original product mapping receives physical left/X. Its
                # acknowledgement is ignored: only separate Qt/VR sources can
                # prove Home, editor death and released keys.
                self.session.stage(self.identity,'controller.button',deepcopy(BUTTON),intent=intent,
                    **({} if phase(self) is None else dict(before_publish=before_publish)))
                return self.observe()
        except Exception:raise NativeUIError('Pico normal Back unresolved; original ownership retained') from None
        finally:self.deadline=None

    def observe(self):
        self.lock.assert_held();need(self.state is not None and self.state['envelope'] is not None)
        self.now();owned=deepcopy(self.state['envelope']);before=self.packet(self.state['frames'][0])
        originalNeutral=self.session.require_owned_neutral(self.identity,owned);self.now()
        self.neutral(originalNeutral,owned,before['capturedEpochMs'])
        started=quietStart=first=None
        for attempt in range(41):
            current=self.capture();now=self.now()
            need(originalNeutral['updatedEpochMs']<=current['capturedEpochMs']+250)
            try:self.home(current,self.state['originalId']);isHome=True
            except NativeUIError:isHome=False
            if isHome:
                if first is None:first=len(self.state['frames'])-1;started=current['capturedEpochMs'];quietStart=now
                if current['capturedEpochMs']-started>=3000 and now-quietStart>=3:
                    finalNeutral=self.session.require_owned_neutral(self.identity,owned);self.now()
                    self.neutral(finalNeutral,owned,before['capturedEpochMs'])
                    need(canonical(originalNeutral)==canonical(finalNeutral))
                    value=deepcopy(self.state);value.update(phase='released' if self.retired(current,value['originalId']) else 'retained',
                        neutral=deepcopy(originalNeutral),quiet=dict(first=first,last=len(value['frames'])-1));self.save(value)
                    self.now();self.fresh_packet();return self.report(current)
            else:first=started=quietStart=None
            need(attempt<40);self.sleep(.25);self.now()
        need(False)

    def report(self,packet):
        row=self.row(packet,self.state['originalId'])
        return dict(routeObserved=True,editorRetired=self.retired(packet,row['id']),phase=self.state['phase'],
            originalId=row['id'],editor=deepcopy(row),sourceSequence=packet['sequence'],
            capturedEpochMs=packet['capturedEpochMs'],keyboardSequence=packet['source']['keyboard']['sequence'])

    def reconcile(self):
        try:
            with self.source_lock.held(),self.lock.held():
                self.load();need(self.state is not None);self.deadline=self.now()+10
                return self.observe() # Only source queries; never another input.
        except Exception:raise NativeUIError('Pico normal Back reconciliation unresolved; original ownership retained') from None
        finally:self.deadline=None
