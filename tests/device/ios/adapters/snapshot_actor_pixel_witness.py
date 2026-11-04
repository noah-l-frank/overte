"""Independent Actor's durable original rendered PNG and real phase association.

No full Snapshot witness state is inferred from a scene. This local publication
is not the canonical fixture /samples journal and grants no cleanup authority.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_original
from ios.adapters.snapshot_capture_clock import operation
from ios.adapters.snapshot_actor_pixel_packet import SnapshotActorPixelPacket


class SnapshotScenePending(NativeUIError):pass


class SnapshotActorPixelWitnessOwner:
    def __init__(self,store,lock,binding,run,index,fixture_url,*,phase=None,feature=None,native=None,guard=None,
                 epoch_ms=None,monotonic=None,historical=False):
        need(type(store) is PrivateFeatureState and type(lock) is ScriptSourceLock
            and integer(index,1,128) and type(historical) is bool)
        self.store,self.lock,self.binding,self.run,self.index=store,lock,deepcopy(context(binding)),identifier(run),index
        self.role='actor';self.fixture_url=fixture_url;self.historical=historical
        need(store.path.name=='ios-snapshot-actor-render-witness-'+format(index,'04d')+'.json'
            and lock.path==store.path.with_name('script-feature-sources.lock') and type(fixture_url) is str
            and fixture_url.endswith('/runs/'+run+'/'))
        lock.assert_held();self.phase,self.feature,self.native,self.guard=phase,feature,native,guard
        self.epoch_ms,self.monotonic=epoch_ms,monotonic
        if historical:need(phase is feature is native is guard is None)
        else:
            need(type(phase) is PhaseFixtureReader and phase.area=='snapshots' and phase.run==run and phase.fixture_url==fixture_url
                and all(callable(fn) for fn in (guard,epoch_ms,monotonic)))
        self.previous=store.read();self.state=dict(phase='new',ticket=None,before=None,childStarted=False,after=None,packetSha256=None)
        if self.previous is not None:self.state=self.decode(self.previous)
        elif historical:need(False)

    def envelope(self,state):
        return dict(iosSnapshotActorPixelWitnessOwnerVersion=1,binding=self.binding,runId=self.run,role=self.role,
            index=self.index,fixtureUrl=self.fixture_url,payload=pack([state]))

    def bound(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous)
            and (self.previous is None or same(self.envelope(self.state),self.previous)))
        if not self.historical:need(self.guard() is not False)

    def packet_store(self):
        return PrivateFeatureState(self.store.path.with_name('ios-snapshot-actor-native-actor-pixels-'+format(self.index,'04d')+'.json'))

    def child(self,*,historical):
        args=(self.packet_store(),self.lock,self.binding,self.run,'actor',self.index)
        if historical:return SnapshotActorPixelPacket.history(*args)
        need(not self.historical)
        return SnapshotActorPixelPacket(*args,self.feature,self.native,self.guard,epoch_ms=self.epoch_ms,monotonic=self.monotonic)

    def phase_packet(self,value):
        phase_original(value,run=self.run,area='snapshots',request=value['requestId'],epoch=value['capturedEpochMs'])
        need(value['active'] and value['activations'] and value['activations'][-1]['ticket']==self.state['ticket'])
        return value

    def decode(self,value):
        exact(value,{'iosSnapshotActorPixelWitnessOwnerVersion','binding','runId','role','index','fixtureUrl','payload'})
        states=unpack(value['payload']);need(len(states)==1 and type(value['iosSnapshotActorPixelWitnessOwnerVersion']) is int
            and value['iosSnapshotActorPixelWitnessOwnerVersion']==1 and same(value,self.envelope(states[0])))
        state=states[0];exact(state,{'phase','ticket','before','childStarted','after','packetSha256'})
        need(state['phase'] in ('new','reading','complete') and type(state['childStarted']) is bool)
        if state['phase']=='new':need(state==dict(phase='new',ticket=None,before=None,childStarted=False,after=None,packetSha256=None))
        else:
            identifier(state['ticket']);before=state['before'];phase_original(before,run=self.run,area='snapshots',request=before['requestId'],epoch=before['capturedEpochMs'])
            need(before['active'] and before['activations'] and before['activations'][-1]['ticket']==state['ticket'])
            if state['phase']=='reading':need(state['after'] is state['packetSha256'] is None)
            else:
                need(state['childStarted']);after=state['after']
                phase_original(after,run=self.run,area='snapshots',request=after['requestId'],epoch=after['capturedEpochMs'],previous=before)
                need(after['active'] and same(before['activations'],after['activations']))
                packet=self.child(historical=True);need(digest(packet.previous)==state['packetSha256']);packet.qualified()
        return deepcopy(state)

    def save(self):
        need(not self.historical);self.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous))
        value=self.envelope(self.state);self.decode(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    @operation
    def acquire(self,ticket):
        need(not self.historical);identifier(ticket);self.bound()
        if self.state['phase']=='complete':need(self.state['ticket']==ticket);return self.original()
        if self.state['phase']=='new':
            current=self.phase.read();need(current['ticket']==ticket)
            self.state.update(phase='reading',ticket=ticket,before=deepcopy(current['status']));self.save()
        need(self.state['ticket']==ticket)
        started=self.state['childStarted']
        if started and self.packet_store().read() is None:
            raise SnapshotScenePending('Actor packet birth is uncertain; no new native query may be issued')
        if not started:self.state['childStarted']=True;self.save()
        packet=self.child(historical=False)
        if packet.state is None:
            need(not started);packet.reserve()
        if packet.state['phase']=='reserved':packet.send()
        if packet.state['phase']=='issued':packet.retain()
        need(packet.state['phase']=='retained');packet.qualified()
        after=self.phase.status(self.state['before']);self.phase_packet(after)
        need(same(after['activations'],self.state['before']['activations']))
        self.state.update(phase='complete',after=deepcopy(after),packetSha256=digest(packet.previous));self.save()
        return self.original()

    def original(self):
        self.bound();need(self.state['phase']=='complete');self.decode(self.previous)
        return dict(iosSnapshotActorPixelWitnessOriginalVersion=1,owner=deepcopy(self.previous),ownerSha256=digest(self.previous),
            publicationKind='local-render-original-only-not-canonical-samples')

    def validate_original(self,value):
        self.bound();exact(value,{'iosSnapshotActorPixelWitnessOriginalVersion','owner','ownerSha256','publicationKind'})
        need(type(value['iosSnapshotActorPixelWitnessOriginalVersion']) is int and value['iosSnapshotActorPixelWitnessOriginalVersion']==1
            and value['publicationKind']=='local-render-original-only-not-canonical-samples'
            and same(value,self.original()))
        child=self.child(historical=True);frame=child.historical();clock=child.qualified()
        return dict(binding=deepcopy(self.binding),runId=self.run,role='actor',ticket=self.state['ticket'],
            phaseBefore=deepcopy(self.state['before']),phaseAfter=deepcopy(self.state['after']),
            nativeOriginal=frame,clockJoin=clock,ownerSha256=digest(self.previous),packetOwnerSha256=digest(child.previous),
            localOriginalPublicationEstablished=True,canonicalActorPublicationRequired=True)
