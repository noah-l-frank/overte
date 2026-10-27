"""Actual production Chat output feeding explicitly modeled native receivers.

One fresh primary NativeFeature producer serves both existing owners. The peer
has an independent producer/epoch and target, despite coincident numeric PIDs.
No product, actual mixer, SDK, QML rendering or real network is exercised.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.chat_receive_sources import IOSChatReceiveSources
from ios.self_tests.chat_source_bound_fixture import SourceBoundScriptMessageModel
from ios.self_tests.test_ios_chat_receive_runtime import IOSChatReceiveRuntimeTests
from ios.self_tests.test_ios_chat_source_bound_owner import ChatSourceBoundOwnerTests
from self_tests.test_native_feature_observation import Boundary as ClockBoundary
from self_tests.test_native_chat_observation import SELF,PEER


class BusScriptModel(SourceBoundScriptMessageModel):
    def __init__(self,case):
        super().__init__(case);self.bus=None;self.lose_bus_return=False
    def produce_native(self,command):
        self.tick();self.native.send(command)
        self.native.sample.update(instance='e'*32,processId=42,capturedEpochMs=self.native_epoch(),
            requestedEpochMs=self.native_epoch(),animation={})
        self.native.sample.pop('animationFence',None)
    def send_native(self,command):self.query(command);self.produce_native(command)
    def chat_input(self,identifier,action,*,reference,value=None):
        before=len(self.source['chatSends']);super().chat_input(identifier,action,reference=reference,value=value)
        for wire in self.source['chatSends'][before:]:
            if self.bus is not None:self.bus(deepcopy(wire))
            if self.lose_bus_return:raise OSError('Declared lost normal Send return after actual Script emission')


class SendReceiveFixture:
    def __init__(self,case):
        self.pair=IOSChatReceiveRuntimeTests();self.pair.setUp();case.addCleanup(self.pair.doCleanups)
        self.draft=ChatSourceBoundOwnerTests();self.draft.setUp();case.addCleanup(self.draft.doCleanups)
        self.model=BusScriptModel(case);self.draft.m=self.draft.f.model=self.model
        self.pair.sources['primary']['binding']['processIdentity']='42'
        self.pair.sources['primary']['observer'].pid=42
        self.draft.binding=deepcopy(self.pair.sources['primary']['binding'])
        self.draft.f.root=self.pair.artifacts['primary'];self.draft.f.lock=self.pair.locks['primary']
        self.draft.f.store=PrivateFeatureState(self.pair.paths['primary'].with_name('ios-chat-draft-owner.json'))
        self.epoch={'primary':self.model.native_epoch,'peer':lambda:300000+round(self.model.widgets.clock*1000)}
        self.opened={};self.observation_fault=None;self.drop_peer=False;self.duplicate_peer=False
        self.local_peer=False;self.wrong_sender=False;self.wrong_text=False
        for role,native in (('primary',self.pair.primary),('peer',self.pair.peer)):
            def mutate(value,role=role):
                current=self.epoch[role]()
                if value['source']['scopePresent'] and role not in self.opened:self.opened[role]=current
                value.update(processId=42,instance=('c' if role=='primary' else 'd')*32,capturedEpochMs=current)
                value['source'].update(selfSha256=SELF if role=='primary' else PEER,
                    openedEpochMs=self.opened[role] if value['source']['scopePresent'] else 0)
                if self.observation_fault is not None:self.observation_fault(role,value)
            native.mutate=mutate
            transport=self.pair.sources[role]['observer'];factory=transport.chat_capture
            def capture(owner,run,factory=factory,role=role):
                value=factory(owner,run);value.reader.clock_ms=self.epoch[role];return value
            transport.chat_capture=capture
        self.parts=self.pair.parts();self.parts['primary_capture'].observe()
        self.peer_clock=ClockBoundary();self.attach_clocks()
        self.receive=IOSChatReceiveSources(self.parts,
            PrivateFeatureState(self.pair.paths['peer'].with_name('ios-chat-receive-sources.json')),
            epoch_ms=self.model.epoch,monotonic=lambda:self.model.widgets.clock)
        self.model.bus=self.deliver
    def attach_clocks(self):
        model=self.model
        self.parts['primary']['clock_source']=NativeFeatureObservation(model.produce_native,
            lambda:json.dumps(model.native.sample),model.native_epoch,model.guard,42,ios=True,
            monotonic=lambda:model.widgets.clock,sleep=model.sleep)
        def send(command):
            model.tick();self.peer_clock.send(command)
            self.peer_clock.sample.update(processId=42,instance='9'*32,
                requestedEpochMs=self.epoch['peer'](),capturedEpochMs=self.epoch['peer'](),animation={})
            self.peer_clock.sample.pop('animationFence',None)
        self.parts['peer']['clock_source']=NativeFeatureObservation(send,self.peer_clock.original,
            self.epoch['peer'],model.guard,42,ios=True,monotonic=lambda:model.widgets.clock,sleep=model.sleep)
    def deliver(self,wire,*,roles=('primary','peer')):
        assert wire['channel']=='chat' and wire['localOnly'] is False
        body=json.loads(wire['message']);assert body['action']=='send_chat_message'
        for role,native in (('primary',self.pair.primary),('peer',self.pair.peer)):
            if role not in roles:continue
            if role=='peer' and self.drop_peer:continue
            for _ in range(2 if role=='peer' and self.duplicate_peer else 1):
                from feature_journeys.fixtures import context
                text=body['message'] if not (role=='peer' and self.wrong_text) else context(self.draft.run)['retry']
                native.events.append(dict(sequence=len(native.events)+1,capturedEpochMs=self.epoch[role](),
                    senderSha256=PEER if role=='peer' and self.wrong_sender else SELF,
                    localOnly=role=='peer' and self.local_peer,channel=body['channel'],text=text))
    def prepare(self,*,channel=None):
        from feature_journeys.fixtures import context
        self.draft.act('open')
        if channel is not None:self.draft.act('select-channel',dict(channel=channel))
        self.draft.act('type',dict(text=context(self.draft.run)['unicode']))
        return self.receive.capture()
    def send(self):
        self.draft.act('send');return self.receive.capture(),self.model.ticket
    def archive(self):
        return IOSChatReceiveSources.archive(self.receive.store,self.receive.primary_binding,self.receive.binding,
            self.receive.run,self.draft.f.root,self.pair.artifacts['peer'],self.parts['binding'],
            self.pair.locks['primary'],self.pair.locks['peer'])
