"""Retry only original scene readiness outside both existing SDK leases."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import wraps
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import same
from ios.adapters.emote_scene_gate import IOSEmoteSceneGate
from ios.adapters.peer_admission import admit_existing_peer


class ScenePending(BaseException):
    """Private yield signal, consumed outside leases by retry_scene only.

    Existing source locks deliberately normalize ordinary Exception instances.
    This signal crosses their finally blocks without changing their error or
    serialization policy; OS descriptors still close before any polling.
    """
    def __init__(self,gate,stage,ticket):
        super().__init__('The other original scene endpoint is not ready')
        self.gate,self.stage,self.ticket=gate,stage,ticket


def retry_scene(function):
    @wraps(function)
    def invoke(flow,*args,**kwargs):
        prior=getattr(flow,'_scene_proofs',None);flow._scene_proofs={}
        try:
            while True:
                try:return function(flow,*args,**kwargs)
                except ScenePending as pending:
                    # Exception unwinding releases every held() context. The
                    # operation decorator remains outside this retry loop, so
                    # neither polling nor reacquisition can restart its deadline.
                    gate=pending.gate
                    while True:
                        flow.clock();candidate=gate.candidate(pending.stage,pending.ticket,retired=not flow.phase.previous['active'])
                        if candidate is None:flow.sleep(.05);continue
                        with flow.held():
                            flow.load();flow.phase.status();status=flow.phase.previous
                            need(flow.state['phaseInstance']==status['instance']
                                and status['activations'][-1]['ticket']==pending.ticket)
                            current=gate.store.read();need(current is not None)
                            gate.previous=deepcopy(current);gate.state=gate.decode(current)
                            # Actual peer originals are admitted before the own
                            # passive keys/native-clock receipt is acquired.
                            gate.read_peer(candidate['snapshot'],candidate['reference'])
                            parts=flow.components();keys=flow.keys(parts);keys.abandon();ref=keys.capture()
                            ack=dict(keys=keys.store.read(),reference=ref,ownerPath=str(keys.store.path))
                            gate.admit(pending.stage,pending.ticket,candidate,ack);gate.ready(pending.stage,pending.ticket)
                        break
        finally:flow._scene_proofs=prior
    return invoke


def owner(flow,parts):
    own=parts['own'];store=PrivateFeatureState(flow.runtime.state_path(flow.selector).with_name('ios-emote-'+flow.role+'-scene-gate.json'))
    other=flow.actor_selector if flow.role=='primary' else flow.primary_selector
    previous=store.read()
    if previous is None:
        admission=(deepcopy(flow.state['actorAdmission']) if flow.role=='primary' else
            admit_existing_peer(flow.runtime,other,own['binding'],epoch_ms=flow.epoch_ms,monotonic=flow.monotonic))
    else:admission=deepcopy(previous['peerAdmission'])
    peer_store=PrivateFeatureState(flow.runtime.state_path(other).with_name('ios-emote-'+('actor' if flow.role=='primary' else 'primary')+'-scene-gate.json'))
    return IOSEmoteSceneGate(store,flow.root,flow.state['binding'],flow.run,flow.role,flow.state['phaseInstance'],admission,peer_store,
        flow.lock,flow.primary_lock,own['check'],check=flow.clock,monotonic=flow.monotonic)


def require(flow,parts,stage,proof):
    gate=owner(flow,parts);gate.abandon();ticket=flow.phase.previous['activations'][-1]['ticket']
    gate.retain('own',stage,ticket,proof)
    try:gate.ready(stage,ticket)
    except NativeUIError:raise ScenePending(gate,stage,ticket) from None
    if flow.phase.previous['active']:
        other=flow.actor_selector if flow.role=='primary' else flow.primary_selector
        current=admit_existing_peer(flow.runtime,other,flow.state['binding'],epoch_ms=flow.epoch_ms,monotonic=flow.monotonic)
        need(same(current['binding'],gate.peer_binding))
    return gate


def initial(flow,parts):
    frames=parts['restoration'];refs=[ref for ref in frames.state['records']
        if frames.original(ref)['kind']=='initial' and frames.original(ref)['phase']=='captured'];need(refs)
    return require(flow,parts,'initial',dict(iosEmoteSceneProofVersion=1,stage='initial',phase=deepcopy(flow.phase.previous),
        restoration=frames.store.read(),reference=refs[0],ownerPath=str(frames.store.path)))


def retired(flow,parts):
    ticket=flow.phase.previous['activations'][-1]['ticket'];cache=getattr(flow,'_scene_proofs',None)
    need(type(cache) is dict);key=('scene-retired',ticket)
    if key not in cache:
        scope=parts['scope'];entities=flow.marker_entities(parts);entities.abandon();entities.capture();entities.closed(scope)
        cache[key]=dict(iosEmoteSceneProofVersion=1,stage='scene-retired',phase=deepcopy(flow.phase.previous),
            scope=scope.store.read(),entities=entities.store.read(),ownerPath=str(entities.store.path))
    return require(flow,parts,'scene-retired',cache[key])
