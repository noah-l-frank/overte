"""Explicit retired Observation4 and callback native Retirement4 source slice.

The original Sample3 remains pending as-of its acquisition. Only a separate
actual immutable released-owner snapshot can clear this selected callback duty.
Default Observer1/2/3 and native Retirement1/2 keep their literal readers.
Rendered/scene/live/process/SDK end profiles are deliberately still closed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from adapters.normal_feature_state import PrivateFeatureState
from adapters.native_feature_observation import exact,need
from adapters.script_feature.history import same,unpack
from adapters.native_clock_join import digest
from ios.adapters.emote_observation import ORIGINAL_FIELDS
from ios.adapters.emote_rooted_observation import IOSEmoteRootedObserver
from ios.adapters.emote_callback_observation import IOSEmoteCallbackRootedDecoder,IOSEmoteCallbackRootedObserver
from ios.adapters.emote_rooted_retirement import IOSEmoteRootedNativeRetirement
from ios.adapters.emote_callback_feature import IOSEmoteCallbackFeature,PROFILE
from ios.adapters.emote_rooted_feature import IOSEmoteRootedFeature
from ios.adapters.emote_observer import EmoteObservationPending
from ios.adapters import emote_callback_drain_originals as drains

VERSION=4


class IOSEmoteCallbackRetirementDecoder(IOSEmoteCallbackRootedDecoder):
    def original_shape(self,value):
        if type(value) is dict and type(value.get('iosEmoteObservationOriginalVersion')) is int and value['iosEmoteObservationOriginalVersion']==VERSION:
            exact(value,ORIGINAL_FIELDS|{'sampleOwners'})
            need(value['image'] is value['imageBefore'] is value['marker'] is None
                and value['proof']['kind'] in ('idle','retired'))
            # Common field semantics are validated by the unchanged derive
            # body; this is an explicit closed v4 shape, never a v1 DTO.
            return None
        return super().original_shape(value)

    def image_resources(self,value):
        if value['image'] is not None:return super().image_resources(value)
        need(type(value['iosEmoteObservationOriginalVersion']) is int and value['iosEmoteObservationOriginalVersion']==VERSION)
        current=self.source(value['source']);activation=current['phaseAfter']['activations'][-1]
        need(activation['ticket']==value['ticket'] and activation['stimulus']==dict(verb='cleanup',inputs={}))
        own=current if self.role=='primary' else self.retained(self.peers,value['peerAfter'])['peer']
        drains.projection(value['sampleOwners'],root=self.root,binding=self.binding,run=self.run,role=self.role,
            lock=self.lock,policy=self.policy,native_before=own['clockJoin']['nativeBefore'],acquisition=value['acquisition'])
        return []


class IOSEmoteCallbackRetirementObserver(IOSEmoteCallbackRootedObserver):
    OwnerVersion=VERSION
    OwnerReads=(VERSION,)
    Decoder=IOSEmoteCallbackRetirementDecoder
    PendingExtraFields=frozenset({'callbackDrains'})

    def pending_extra(self):return dict(callbackDrains=None)

    def validate_pending_extra(self,pending):
        need(type(pending) is dict and 'callbackDrains' in pending)
        drains.validate_pending(self,pending)

    def __init__(self,store,sources,binding,role,root,policy,phase,lock,guard,**kwargs):
        need(isinstance(store,PrivateFeatureState));root=Path(root)
        PrivateFeatureState(root/'callback-observer-root-check')._parent()
        if store.read() is None:need(not any(path.name.startswith(drains.NAMESPACE+'-') for path in root.iterdir()))
        self._callback_drain_span=None
        super().__init__(store,sources,binding,role,root,policy,phase,lock,guard,**kwargs);drains.history(self)

    def observe(self,after_sequence,*,input_barrier=None,retired=False):
        if retired or self.samples.scope.state['phase']!='ready':
            # Check the complete known carrier prefix before any native drain
            # query, and use exactly the existing nonblocking once-release /
            # fresh INSPECT. A real held callback remains pending, not quiet.
            need(self._callback_drain_span is None and self.samples.state['phase']=='ready' and self.samples.state['rows'])
            drains.history(self);before=dict(hostBeforeEpochMs=self.epoch_ms(),hostBeforeMonotonic=self.monotonic())
            self.samples.before_capture();heads=[]
            for row in self.samples.state['rows']:
                value=self.samples.owner(row).store.read();events=unpack(value['transcript']);last=events[-1]
                need(last['receipt'] is not None)
                heads.append(dict(requestId=row['requestId'],commandId=last['command']['commandId'],receiptSha256=digest(last['receipt'])))
            self._callback_drain_span=dict(before,hostAfterEpochMs=self.epoch_ms(),hostAfterMonotonic=self.monotonic(),heads=heads)
            try:return IOSEmoteRootedObserver.observe(self,after_sequence,input_barrier=input_barrier,retired=retired)
            finally:self._callback_drain_span=None
        return super().observe(after_sequence,input_barrier=input_barrier,retired=retired)

    def prepare_original(self,value):
        value=super().prepare_original(value)
        if value['image'] is not None:return value
        need(value['proof']['kind'] in ('idle','retired') and value['imageBefore'] is value['marker'] is None)
        projection=drains.prepare(self)
        return dict(value,iosEmoteObservationOriginalVersion=VERSION,sampleOwners=projection)

    def abandon_read(self):
        pending=self.state['pending']
        if pending is not None and pending['callbackDrains'] is not None:
            # Partial/opened carriers remain explicit original responsibility.
            # This bounded slice never rewrites, removes or silently adopts a
            # lost carrier. A complete metadata-only pending original retains
            # the existing exact resolve() path, without another acquisition.
            need(pending['callbackDrains']['original'] is None)
        return super().abandon_read()


class IOSEmoteCallbackNativeRetirement(IOSEmoteRootedNativeRetirement):
    FORMAT_VERSION=VERSION
    Decoder=IOSEmoteCallbackRetirementDecoder

    def owners(self,original):
        need(type(original['observation'].get('iosEmoteObservationOriginalVersion')) is int
            and original['observation']['iosEmoteObservationOriginalVersion']==VERSION
            and same(original['sampleOwners'],original['observation']['sampleOwners']))
        return super().owners(original)

    def samples(self,owners,scope):
        actual=drains.projection(owners,root=self.root,binding=self.binding,run=self.run,role=self.role,lock=self.lock,policy=self.policy)
        need(same(actual.envelope(actual.state),scope.envelope(scope.state)))


# This prospective profile is not selected by public configuration. It wires
# the actual Native4/sampleOwners boundary; strict scene/live/end routes still
# require a separate reviewed profile and normal complete-journey result.
PROFILE5=dict(PROFILE,callbackProfileVersion=2,observerOwnerVersion=4,nativeRetirementVersion=4,sampleOwnersVersion=4)


class IOSEmoteCallbackRetirementFeature(IOSEmoteCallbackFeature):
    FORMAT_VERSION=5
    PAIRED_FORMAT_VERSION=5
    Observer=IOSEmoteCallbackRetirementObserver
    NativeRetirement=IOSEmoteCallbackNativeRetirement

    def __init__(self,*args,target_pair=None,**kwargs):
        need(target_pair is not None)
        super().__init__(*args,target_pair=target_pair,**kwargs)

    def profile_envelope(self,state):
        value=IOSEmoteRootedFeature.profile_envelope(self,state)
        if self.previous is not None:need(self.previous.get('iosEmoteFeatureVersion')==5 and same(self.previous.get('callbackProfile'),PROFILE5))
        return dict(value,callbackProfile=deepcopy(PROFILE5))

    def retirement_sample_owners(self,parts,observation):
        need(type(parts['observer']) is self.Observer and observation['iosEmoteObservationOriginalVersion']==VERSION)
        return deepcopy(observation['sampleOwners'])

    def rendered_retirement_owner(self,parts,*,native=None):
        raise EmoteObservationPending('Callback Native4 is retained; rendered/scene/process end profile remains closed')
