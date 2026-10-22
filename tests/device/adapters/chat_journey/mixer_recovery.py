"""Once-only original fixture recovery when native Chat journals are interrupted.

This retains every native transcript and cannot produce a Chat/resource verdict.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import time
import uuid
from adapters.chat_journey.mixer import VERSION,control_join
from adapters.chat_journey.mixer_control import FixtureMixerControl
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.normal_feature_state import context
from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import pack,unpack
from feature_journeys.contract import identifier
from fixture.messages_mixer import valid_control_command


class ChatMixerRecovery:
    """Restore only the already-owned original mixer; no native role adoption."""
    def __init__(self,controls,store,binding,run,guard,*,component_only=False,monotonic=time.monotonic):
        identifier(run);context(binding,component_only=component_only)
        need(type(controls) is tuple and len(controls)==2 and controls[0] is not controls[1]
            and all(isinstance(source,FixtureMixerControl) and source.previous is None for source in controls)
            and not controls[0].readonly and controls[1].readonly and controls[0].identity==controls[1].identity
            and callable(guard) and callable(monotonic))
        self.controls,self.store,self.guard,self.monotonic=controls,store,guard,monotonic
        self.previous=store.read();need(self.previous is not None)
        self.base=deepcopy(self.previous);self.last_clock=None;self.deadline=None
        exact(self.base,{'chatMixerOwnerVersion','runId','binding','peerBinding','controlIdentity','transcripts',
            'phase','commands','recoverySources','offlineObserved','original','transcript'})
        need(type(self.base['chatMixerOwnerVersion']) is int and self.base['chatMixerOwnerVersion']==VERSION
            and self.base['runId']==run and self.base['binding']==binding and self.base['controlIdentity']==controls[0].identity
            and type(self.base['offlineObserved']) is bool
            and self.base['phase'] in ('issuing-offline','offline','issuing-online','online','recovering','recovery-observed'))
        context(self.base['peerBinding'],component_only=component_only)
        names=self.base['transcripts'];need(type(names) is list and len(names)==2 and len(set(names))==2
            and all(type(name) is str and name.endswith('.json') and '/' not in name and '\\' not in name for name in names))
        commands=self.base['commands'];need(type(commands) is list and 1<=len(commands)<=2
            and all(valid_control_command(row) and row['runId']==run for row in commands)
            and commands[0]['action']=='offline' and (len(commands)==1 or commands[1]['action']=='online')
            and len({row['commandId'] for row in commands})==len(commands))
        rows=unpack(self.base['transcript']);recovery=self.base['recoverySources']
        need(type(recovery) is list and len(recovery)<=2)
        for row in rows+recovery:
            control_join(row,commands,run)
            for source,value in zip(controls,row['controls']):source.accept(value)
        original=self.base['original'];exact(original,{'control','nativeMixer'})
        need(any(not row['controlOnly'] and not row['transition'] and row['controls'][0]==original['control'] for row in rows)
            and all(command['instance']==original['control']['instance'] for command in commands)
            and original['control']['runId'] is None and original['control']['commands']==[]
            and original['control']['mixer']['running'] and not original['control']['mixer']['pending'])
        for row in recovery:need(row['controlOnly'])
        self.run=run

    def now(self):
        need(self.guard() is not False);value=self.monotonic()
        need(number(value,0,1e15) and (self.last_clock is None or value>=self.last_clock))
        self.last_clock=value
        if self.deadline is not None:need(value<=self.deadline)
        return value

    def save(self,phase,**changes):
        need(self.store.read()==self.previous)
        value={**self.base,**changes,'phase':phase}
        # Existing packed original history is copied unchanged, not repacked,
        # truncated, unblocked or relabelled as a successful native read.
        self.store.write(value,self.previous);need(self.store.read()==value)
        self.previous=self.base=deepcopy(value)

    def fresh(self,frame,started):
        for source in self.controls:need(source.guard() is not False)
        self.now();clocks=[];previous=self.last_clock
        for source,value in zip(self.controls,frame['controls']):
            measured=self.monotonic();need(number(measured,previous,started+1.5));previous=measured
            epoch=source.clock_ms();fresh(value['capturedEpochMs'],epoch)
            clocks.append((measured,epoch,value['capturedEpochMs']))
        finished=self.monotonic();need(number(finished,previous,started+1.5)
            and (self.deadline is None or finished<=self.deadline)
            and all(epoch-oldest+math.ceil((finished-measured)*1000)<=1500 for measured,epoch,oldest in clocks))
        self.last_clock=finished

    def current(self):
        started=self.now();values=[source.state() for source in self.controls]
        frame=dict(controls=deepcopy(values),roles=[],transition=True,controlOnly=True)
        control_join(frame,self.base['commands'],self.run);self.fresh(frame,started)
        return frame,started

    def inspect(self):
        need(len(self.base['commands'])==2 and len(self.base['recoverySources'])<2)
        if self.deadline is None:self.deadline=self.now()+20
        frame,started=self.current();source=frame['controls'][0];online=self.base['commands'][1]
        row=next((row for row in source['commands'] if row['commandId']==online['commandId']),None)
        need(source['offlineFenced'] and row is not None and row['action']=='online' and row['status']!='pending'
            and source['mixer']['running'] and not source['mixer']['pending'])
        self.save('recovery-observed',recoverySources=self.base['recoverySources']+[frame]);self.fresh(frame,started)
        return dict(mixerProcessRestored=True,nativeChatUnresolved=True,journalsRetained=True,
            source=deepcopy(source))

    def restore_once(self):
        try:
            need(len(self.base['recoverySources'])<2);self.deadline=self.now()+20
            if len(self.base['commands'])==1:
                frame,started=self.current();source=frame['controls'][1]
                if not self.base['recoverySources']:
                    self.save('recovering',recoverySources=[frame]);self.fresh(frame,started)
                request=dict(schemaVersion=2,commandId=uuid.uuid4().hex,runId=self.run,instance=source['instance'],
                    observedGeneration=source['mixer']['generation'],action='online')
                self.save('issuing-online',commands=self.base['commands']+[request]);self.fresh(frame,started)
                self.controls[0].command(request)
            # Once online intent exists this path is exclusively passive, even
            # after a transport loss, interpreter death or new owner object.
            return self.inspect()
        except Exception:
            raise NativeUIError('Original mixer recovery is unresolved; no input or native journal is replayed') from None
