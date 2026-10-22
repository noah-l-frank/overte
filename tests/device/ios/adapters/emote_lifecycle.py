"""One-send ordinary Emote Home/activate input with original OS/native proof."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
from adapters.native_feature_observation import exact,need,number,validate as native_packet
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import arguments,identifier
from ios.adapters.graphics_history import follow_native
from ios.adapters.graphics_lifecycle import IOSGraphicsBackground
from ios.adapters.graphics_runtime import IOSGraphicsRuntime
from ios.adapters.script_runtime import IOSScriptRuntime

VERSION=1


class IOSEmoteBackground:
    def __init__(self,runtime,selector,run,fixture_url,binding,lock,*,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(runtime,IOSScriptRuntime) and isinstance(lock,ScriptSourceLock)
            and all(callable(fn) for fn in (monotonic,sleep)))
        self.runtime,self.selector,self.run,self.fixture_url=runtime,selector,identifier(run),fixture_url
        self.binding=deepcopy(context(binding));self.pid=int(binding['processIdentity'])
        self.lock,self.monotonic,self.sleep=lock,monotonic,sleep;self.started=self.last_clock=None
        self.store=PrivateFeatureState(runtime.state_path(selector).with_name('ios-emote-background.json'))
        need(lock.path==self.store.path.with_name('script-feature-sources.lock'));lock.assert_held()
        self.previous=self.store.read();self.state=None if self.previous is None else self.decode(self.previous)

    def envelope(self,state):
        return dict(iosEmoteBackgroundVersion=VERSION,runId=self.run,fixtureUrl=self.fixture_url,binding=self.binding,payload=pack([state]))

    def decode(self,value):
        exact(value,{'iosEmoteBackgroundVersion','runId','fixtureUrl','binding','payload'});rows=unpack(value['payload'])
        need(len(rows)==1 and same(value,self.envelope(rows[0])));state=rows[0]
        exact(state,{'call','phase','before','background','after'})
        call=arguments('feature.emotes.act',state['call'])
        need(call['verb']=='background-resume' and call['runId']==self.run and call['fixtureUrl']==self.fixture_url
            and state['phase'] in ('background-issued','background-observed','foreground-issued','observed'))
        packet=state['before'];native_packet(packet,packet['requestId'],self.pid,packet['capturedEpochMs'],require_animation_history=True)
        need(packet['animation']['overrideActive'] is False)
        if state['background'] is not None:
            IOSGraphicsBackground.status_packet(state['background'],self.binding);need(not state['background']['foreground'])
        need(state['phase']=='background-issued' or state['background'] is not None)
        if state['after'] is not None:self.completed(packet,state['after'])
        need(state['phase']!='observed' or state['after'] is not None)
        return deepcopy(state)

    def bound(self):
        self.lock.assert_held();now=self.monotonic()
        need(number(now,0,1e15) and (self.last_clock is None or now>=self.last_clock)
            and (self.started is None or now-self.started<30) and same(self.store.read(),self.previous))
        self.last_clock=now

    def save(self):
        self.bound();value=self.envelope(self.state);self.decode(value)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def status(self):
        self.bound();value=IOSGraphicsRuntime._graphics_lifecycle_status(self.runtime,self.selector,self.binding)
        IOSGraphicsBackground.status_packet(value,self.binding);self.bound();return deepcopy(value)

    def source(self):
        self.bound();sources=self.runtime._sources(self.selector);need(same(sources['binding'],self.binding))
        reader=sources['observer'].bound_native_observer(sources['clock_source'])
        value=reader.read(0,require_animation=True,require_animation_history=True);self.bound();return value

    @staticmethod
    def completed(before,after):
        follow_native(before,after);a,b=before['lifecycle'],after['lifecycle']
        need(b['backgrounds']>=a['backgrounds']+1 and b['activations']>=a['activations']+1 and b['launches']==a['launches']
            and before['graphics']==after['graphics'] and after['animation']['overrideActive'] is False)

    def send(self,operation):
        self.bound();need(operation in ('lifecycle.background','app.launch')
            and self.state['phase']==('background-issued' if operation=='lifecycle.background' else 'foreground-issued'))
        base=self.runtime.adapter;outer=base._operation
        need(outer in (None,'feature.emotes.act') or outer=='feature.emotes.cleanup' and operation=='app.launch')
        # Candidate/source and same SDK session stay under the canonical adapter.
        # The durable phase already owns this one ordinary lifecycle delivery.
        base._operation=None
        try:return base.invoke(self.selector,operation,{})
        finally:base._operation=outer

    def act(self,call):
        call=deepcopy(arguments('feature.emotes.act',call));need(call['runId']==self.run and call['fixtureUrl']==self.fixture_url
            and call['verb']=='background-resume')
        self.started=self.monotonic();self.bound()
        with self.runtime.existing_input_session(self.selector):
            if self.state is None:
                need(self.status()['foreground']);before=self.source();need(before['animation']['overrideActive'] is False)
                self.state=dict(call=call,phase='background-issued',before=before,background=None,after=None);self.save()
                self.send('lifecycle.background')
            else:need(same(self.state['call'],call))
            if self.state['phase']=='background-issued':
                for attempt in range(51):
                    value=self.status()
                    if not value['foreground']:break
                    need(attempt<50);self.sleep(.1)
                self.state.update(phase='background-observed',background=value);self.save()
            if self.state['phase']=='background-observed':
                need(not self.status()['foreground']);self.state['phase']='foreground-issued';self.save();self.send('app.launch')
            need(self.state['phase'] in ('foreground-issued','observed') and self.status()['foreground'])
            after=self.source();self.completed(self.state['before'],after)
            if self.state['after'] is not None:follow_native(self.state['after'],after)
            self.state.update(phase='observed',after=after);self.save()
        return {'performed':True}

    def retire(self):
        self.started=self.monotonic();self.bound();need(self.state is not None and self.state['phase']=='observed'
            and self.status()['foreground']);after=self.source();follow_native(self.state['after'],after)
        self.decode(self.previous);self.store.discard(self.previous)
