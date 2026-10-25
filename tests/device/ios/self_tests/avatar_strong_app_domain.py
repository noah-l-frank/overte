"""Strict composed host scenario with real original AvatarApp API call frames.

Qt controls, returned native entities and engine identities are explicit host
models. Original full JS, returned UUIDs, callback order and call locations are
executed independently; reviewed callsite profiles never produce these values.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import uuid
from ios.self_tests.avatar_strong_domain import StrongDomain
from ios.self_tests.avatar_social_domain import SocialDomain
from ios.self_tests.avatar_app_node import AvatarAppNode
from ios.self_tests.avatar_prepare_fixture import SESSIONS


class StrongAvatarAppDomain(StrongDomain):
    def __init__(self,test):
        self.seen_channels={role:dict(pal=0,avatar=0) for role in SESSIONS};self.avatar_nodes={}
        super().__init__(test)
        for role,w in self.widgets.items():
            node=AvatarAppNode(test,self.avatar_config(role),self.natives[role].epoch);self.avatar_nodes[role]=node
            def create(w=w,role=role,node=node):
                value=node.request('message',config=self.avatar_config(role),message=dict(method='addWearable',url=w.draft))
                call=value['calls'][-1];assert call['method']=='addEntity';w.actual_avatar_call=deepcopy(call)
                self.avatar_events(role,value);return call['id']
            def delete(w=w,role=role,node=node):
                value=node.request('message',config=self.avatar_config(role),message=dict(method='deleteWearable',entityID=w.wearable_id))
                call=value['calls'][-1];assert call['method']=='deleteEntity';self.avatar_events(role,value)
                source=self.scenes[role].f.prototypes['entities']['source'];old=next(row for row in reversed(source['events']) if row['entity']['entityId']==call['id'])
                event=deepcopy(old);event.update(sequence=len(source['events'])+1,eventId=uuid.uuid4().hex,kind='deleted-local')
                event['clock'].update(epochMs=self.natives[role].epoch(),monotonicMs=round(self.clock[0]*1000))
                event['caller']=self.entity_caller(role,call);source['events'].append(event)
            w.create_wearable=create;w.delete_wearable=delete;w.actual_avatar_call=None
            native=self.natives[role];old=native.post
            def post(request,timeout,role=role,w=w,node=node,old=old):
                before=w.wearable_id;result=old(request,timeout)
                if w.wearable_id is not None and w.wearable_id!=before:
                    call=w.actual_avatar_call;assert call is not None and call['id']==w.wearable_id
                    event=self.scenes[role].f.prototypes['entities']['source']['events'][-1]
                    assert event['entity']['entityId']==call['id'];event['caller']=self.entity_caller(role,call)
                value=node.request('screen',open=w.screen=='avatar',config=self.avatar_config(role));self.avatar_events(role,value)
                return result
            native.post=post
            mutate=self.scenes[role].f.mutate
            def sample(name,value,role=role,node=node,old=mutate):
                # Original scheduler callbacks run only after their real due
                # time, before this modeled native event-loop observation.
                if name=='scripts' and node.latest['pending'] and min(node.latest['pending'])<=self.natives[role].epoch():
                    self.avatar_events(role,node.request('tick',config=self.avatar_config(role)))
                old(name,value)
            self.scenes[role].f.mutate=sample

    def avatar_config(self,role):
        w=self.widgets[role]
        return dict(self=SESSIONS[role],joints=['Hips'],avatarUrl=w.avatar_url,scale=w.scale,
            bookmarks={} if not w.name or w.saved is None else {w.name:deepcopy(w.saved)})

    def incoming_timers(self,role,events,channel):
        start=self.seen_channels[role][channel];assert len(events)>=start
        for event in events[start:]:
            current=deepcopy(event)
            if current['kind']=='created':
                frames=current['details'].pop('callerFrames');actual,modules=self.actual_stack(role,frames,current['capturedEpochMs'])
                current['details']['callerStackId']=self.retain(role,'avatar',actual,modules);self.retain(role,'uiWork',actual,modules)
            self.produced[role].append(current)
        self.seen_channels[role][channel]=len(events)

    def update(self,value):
        for role,events in value['timers'].items():self.incoming_timers(role,events,'pal')
        value=deepcopy(value);value['timers']=deepcopy(self.produced);SocialDomain.update(self,value)

    def avatar_events(self,role,value):
        self.incoming_timers(role,value['events'],'avatar');self.timer_events=deepcopy(self.produced)

    def entity_caller(self,role,call):
        worker=self.scenes[role].f.prototypes['scripts']['source']['workers'][0]
        events=self.scenes[role].f.prototypes['entities']['source']['events']
        sequence=call['ordinal']
        actual,modules=self.actual_stack(role,call['frames'],call['capturedEpochMs'])
        return dict(callerVersion=1,method=call['method'],sequence=sequence,invokedEpochMs=call['capturedEpochMs'],
            manager=deepcopy(worker['membership']),code=deepcopy(worker['code']),callerChain=['qrc:/scripts/system/avatarapp.js'],
            avatarCode={key:deepcopy(worker['avatar'][key]) for key in ('avatarScriptVersion','instance','complete','code')},
            avatarCallers=dict(avatarEntityCallersVersion=1,complete=True,callerStack=actual,callerModules=modules))
