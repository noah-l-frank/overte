"""Complete Emote retirement composes unchanged native/rendered v1 proofs.

Only this stricter whole-feature original is eligible for whole publication.
Legacy component DTOs retain their original closed grammar and meaning.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.phase_witness_publisher import PhaseWitnessPublisher
from adapters.script_feature.history import pack,unpack,same
from ios.adapters.emote_keys import IOSEmoteKeys
from ios.adapters.emote_marker_scope import IOSEmoteMarkerScope
from ios.adapters.emote_native_prefix import follow
from ios.adapters.emote_pointers import IOSEmotePointers
from ios.adapters.emote_rendered_retirement import IOSEmoteRenderedRetirement
from ios.adapters.emote_retirement import IOSEmoteRetirement,Frozen

VERSION=1


class IOSEmoteKeyedRetirement(IOSEmoteRetirement):
    def __init__(self,store,rendered,keys):
        need(isinstance(store,PrivateFeatureState) and isinstance(rendered,IOSEmoteRenderedRetirement) and isinstance(keys,IOSEmoteKeys))
        self.store,self.rendered_owner,self.keys_owner=store,rendered,keys
        for name in ('root','binding','primary_binding','run','role','fixture_url','phase_instance','lock','primary_lock','policy','guard','paths'):
            setattr(self,name,getattr(rendered,name))
        need(keys.run==self.run and keys.role==self.role and keys.root==self.root and same(keys.binding,self.binding) and keys.lock is self.lock)
        self.previous=store.read();self.state=dict(records=[],abandoned=[],pending=None)
        if self.previous is not None:self.state=self.decode(self.previous)

    def envelope(self,state):
        return dict(iosEmoteKeyedRetirementVersion=VERSION,runId=self.run,role=self.role,binding=self.binding,primaryBinding=self.primary_binding,
            fixtureUrl=self.fixture_url,phaseInstance=self.phase_instance,artifactRoot=str(self.root),imagePolicy=self.policy,
            renderedPath=str(self.rendered_owner.store.path),keysPath=str(self.keys_owner.store.path),payload=pack([state]))

    def record_store(self,index):
        need(integer(index,1,128));return PrivateFeatureState(self.root/('emote-keyed-retirement-'+self.run+'-'+self.role+'-'+str(index)+'.json'))

    def wrap(self,original):
        exact(original,{'renderedReference','keys'})
        return dict(iosEmoteKeyedRetirementOriginalVersion=VERSION,runId=self.run,role=self.role,binding=self.binding,
            primaryBinding=self.primary_binding,phaseInstance=self.phase_instance,fixtureUrl=self.fixture_url,payload=pack([original]))

    def original(self,reference):
        exact(reference,{'index','sha256'});value=self.record_store(reference['index']).read();need(value is not None and digest(value)==reference['sha256'])
        rows=unpack(value['payload']);need(len(rows)==1 and same(value,self.wrap(rows[0])));return deepcopy(rows[0])

    def decode(self,value):return IOSEmoteRenderedRetirement.decode(self,value)

    def derive(self,reference):
        self.lock.assert_held();self.primary_lock.assert_held();original=self.original(reference)
        rendered=self.rendered_owner;ref=original['renderedReference'];need(ref in rendered.state['records'])
        derived=rendered.derive(ref);frame_original=rendered.original(ref)
        native=rendered.native_owner.original(frame_original['nativeReference'])
        scope=IOSEmoteMarkerScope.archive(native['scope'],root=self.root,binding=self.binding,run=self.run,role=self.role,lock=self.lock)
        keys=IOSEmoteKeys.archive(original['keys'],store=Frozen(self.keys_owner.store.path,original['keys']),root=self.root,
            binding=self.binding,run=self.run,role=self.role,lock=self.lock)
        closure=keys.closed(scope);last=closure['last']['clockJoin']
        pointers=IOSEmotePointers.archive(native['pointers'],store=Frozen(self.paths['pointers'],native['pointers']),
            root=self.root,binding=self.binding,run=self.run,role=self.role,lock=self.lock)
        before=pointers.closed(scope)['last']['clockJoin']['nativeAfter'];follow(before,last['nativeBefore'])
        acquisition=derived['acquisition']
        need(last['hostBeforeEpochMs']>=acquisition['hostAfterEpochMs'] and last['hostBeforeMonotonic']>=acquisition['hostAfterMonotonic']
            and last['nativeAfter']['animation']['overrideActive'] is False
            and last['nativeAfter']['animation']['history']['callSequence']==before['animation']['history']['callSequence']
            and same(last['nativeAfter']['lifecycle'],before['lifecycle']))
        derived['acquisition']=PhaseWitnessPublisher.acquisition(dict(acquisition,
            hostAfterEpochMs=last['hostAfterEpochMs'],hostAfterMonotonic=last['hostAfterMonotonic']))
        derived['retirement']['originalSha256']=reference['sha256']
        derived['retirement']['provenance']=dict(version=1,namespace='ios-emote-keyed-retirement-original',reference=deepcopy(reference),originalSha256=reference['sha256'])
        return derived
