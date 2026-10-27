"""Two actual Chat scripts; explicit native, widget, bus and clock models.

Both native epochs are selected before creating either source. One shared host
clock advances both independent modeled processes; it never retimes originals.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import uuid
from functools import partial
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.chat_receive_sources import IOSChatReceiveSources
from ios.self_tests.chat_send_receive_fixture import BusScriptModel
from ios.self_tests.test_ios_chat_receive_runtime import IOSChatReceiveRuntimeTests
from ios.self_tests.test_ios_chat_source_bound_owner import ChatSourceBoundOwnerTests
from self_tests.test_native_chat_observation import SELF,PEER


class HostClock:
    def __init__(self):self.value=0.;self.models=[]
    def advance(self,seconds=.001):
        self.value+=seconds
        for model in self.models:model.widgets.clock=self.value;model.widgets.elapsed=100+round(self.value*1000)


class PairScriptModel(BusScriptModel):
    def __init__(self,case,clock,role):
        self.host,self.role=clock,role;super().__init__(case)
        clock.models.append(self);self.widgets.clock=clock.value;self.widgets.sleep=clock.advance
        if role=='peer':self.widgets.instance=str(uuid.UUID('1'*32));self.widgets.generation=str(uuid.UUID('2'*32))
    def tick(self):self.host.advance()
    def sleep(self,seconds):self.host.advance(seconds)
    def epoch(self):return 5000000+round(self.host.value*1000)
    def native_epoch(self):return (100000 if self.role=='primary' else 300000)+round(self.host.value*1000)
    def produce_native(self,command):
        super().produce_native(command);self.native.sample['instance']=('e' if self.role=='primary' else '9')*32


class PeerSendFixture:
    def __init__(self,case,*,model_class=PairScriptModel,clock=None):
        self.pair=IOSChatReceiveRuntimeTests();self.pair.setUp();case.addCleanup(self.pair.doCleanups)
        self.clock=HostClock() if clock is None else clock;self.models={};self.drafts={};self.opened={}
        self.drop_primary=False;self.mutate_wire=None
        self.pair.sources['primary']['binding']['processIdentity']='42';self.pair.sources['primary']['observer'].pid=42
        for role in ('primary','peer'):
            model=self.models[role]=model_class(case,self.clock,role)
            draft=self.drafts[role]=ChatSourceBoundOwnerTests();draft.setUp();case.addCleanup(draft.doCleanups)
            draft.m=draft.f.model=model;draft.binding=deepcopy(self.pair.sources[role]['binding'])
            draft.f.root=self.pair.artifacts[role];draft.f.lock=self.pair.locks[role]
            draft.f.store=PrivateFeatureState(self.pair.paths[role].with_name('ios-chat-draft-owner.json'))
            if role=='peer':draft.owner=partial(draft.owner,peer_actor=True)
        for role,native in (('primary',self.pair.primary),('peer',self.pair.peer)):
            def mutate(value,role=role):
                epoch=self.models[role].native_epoch()
                if value['source']['scopePresent'] and role not in self.opened:self.opened[role]=epoch
                value.update(processId=42,instance=('c' if role=='primary' else 'd')*32,capturedEpochMs=epoch)
                value['source'].update(selfSha256=SELF if role=='primary' else PEER,
                    openedEpochMs=self.opened[role] if value['source']['scopePresent'] else 0)
            native.mutate=mutate;transport=self.pair.sources[role]['observer'];factory=transport.chat_capture
            def capture(owner,run,factory=factory,role=role):
                value=factory(owner,run);value.reader.clock_ms=self.models[role].native_epoch;return value
            transport.chat_capture=capture
        self.parts=self.pair.parts();self.parts['primary_capture'].observe()
        for role,model in self.models.items():
            self.parts[role]['clock_source']=NativeFeatureObservation(model.produce_native,
                lambda model=model:json.dumps(model.native.sample),model.native_epoch,model.guard,42,ios=True,
                monotonic=lambda:self.clock.value,sleep=self.clock.advance)
            model.bus=lambda wire,role=role:self.deliver(role,wire)
        self.receive=IOSChatReceiveSources(self.parts,
            PrivateFeatureState(self.pair.paths['peer'].with_name('ios-chat-receive-sources.json')),
            epoch_ms=self.models['primary'].epoch,monotonic=lambda:self.clock.value)
    def deliver(self,sender,wire):
        assert wire['channel']=='chat' and wire['localOnly'] is False
        body=json.loads(wire['message']);assert body['action']=='send_chat_message'
        if self.mutate_wire is not None:wire=deepcopy(wire);self.mutate_wire(wire);body=json.loads(wire['message'])
        for role,native in (('primary',self.pair.primary),('peer',self.pair.peer)):
            if role=='primary' and self.drop_primary and sender=='peer':continue
            native.events.append(dict(sequence=len(native.events)+1,capturedEpochMs=self.models[role].native_epoch(),
                senderSha256=SELF if sender=='primary' else PEER,localOnly=False,channel=body['channel'],text=body['message']))
            if role!=sender:self.models[role].command('receive',message=wire['message'],localOnly=False)
    def open(self):
        for role in ('primary','peer'):self.drafts[role].act('open')
    def type(self,role,token='reply',*,channel='domain'):
        from feature_journeys.fixtures import context
        draft=self.drafts[role];text=context(draft.run)[token]
        if role=='peer':
            ticket='f'*32;draft.m.add_phase('peer-send',dict(text=text,channel=channel),ticket)
            with draft.owner() as owner:owner.act(ticket,'select-channel',dict(channel=channel))
            with draft.owner() as owner:owner.act(ticket,'type',dict(text=text))
        else:
            draft.act('select-channel',dict(channel=channel));draft.act('type',dict(text=text))
            draft.m.add_phase('send',{},'e'*32)
