"""Typed current-file replay with an explicit modeled SDK/candidate guard.

Only supplied retained roots are read. No runtime, native transport, file
reconstruction, clock adjustment or new original acquisition is available.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from types import SimpleNamespace
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import unpack,same
from ios.adapters.emote_retirement import Frozen
from ios.adapters.emote_rooted_archive import reopen
from ios.adapters.emote_rooted_live import IOSEmoteRootedLive
from ios.adapters.emote_rooted_marker_scope import IOSEmoteRootedMarkerScope
from ios.adapters.emote_rooted_observation import IOSEmoteRootedObserver
from ios.adapters.emote_rooted_retirement import IOSEmoteRootedKeyedRetirement
from ios.adapters.emote_samples import IOSEmoteSamples


def load(roots,locks,role,run):
    root=Path(roots[role]);lock=locks[role];primary_lock=locks['primary']
    lock.assert_held();primary_lock.assert_held()
    feature_store=PrivateFeatureState(root/('ios-emote-'+role+'-feature.json'));feature=feature_store.read()
    need(feature is not None and type(feature['iosEmoteFeatureVersion']) is int and feature['iosEmoteFeatureVersion']==2
        and feature['runId']==run and feature['role']==role and feature['artifactRoot']==str(root))
    state=unpack(feature['payload'])[0]
    live_store=PrivateFeatureState(root/('ios-emote-'+role+'-'+run+'-terminal-live.json'));live_value=live_store.read()
    live_state=unpack(live_value['payload'])[0];need(live_state['pending'] is None and live_state['records'])
    files=OriginalFrameStore(root,state['binding'],run,role,lambda:True,lambda *_:need(False),namespace='emote-rooted-live',
        schema_prefix='iosEmoteRootedLive',kind='inputs')
    snapshot=files.read(files.expand(live_state['records'][-1]))['snapshot']
    need(all(same(PrivateFeatureState(snapshot['paths'][name]).read(),value) for name,value in snapshot['owners'].items()))
    historical=reopen(snapshot,lock=lock,primary_lock=primary_lock)
    # Actual current keyed metadata is decoded. The inherited candidate guard
    # is the declared model; every original file decoder remains unchanged.
    owner=IOSEmoteRootedKeyedRetirement(PrivateFeatureState(snapshot['paths']['keyed']),historical.rendered_owner,historical.keys_owner)
    live=IOSEmoteRootedLive(owner)
    rendered=owner.rendered_owner;native=rendered.native_owner
    rendered_ref=owner.original(snapshot['reference'])['renderedReference']
    raw=native.original(rendered.original(rendered_ref)['nativeReference'])
    sources,peers,_decoder=native.owners(raw)
    scope_store=PrivateFeatureState(root/('ios-emote-'+role+'-marker.json'))
    scope=IOSEmoteRootedMarkerScope.archive(scope_store.read(),root=root,binding=owner.binding,run=run,role=role,lock=lock)
    samples=object.__new__(IOSEmoteSamples)
    samples.root,samples.binding,samples.run,samples.role,samples.policy,samples.lock=root,owner.binding,run,role,owner.policy,lock
    samples.store=PrivateFeatureState(root/('ios-emote-'+role+'-samples.json'));samples.state=samples.decode(samples.store.read())
    observer=object.__new__(IOSEmoteRootedObserver)
    observer.root,observer.binding,observer.run,observer.role=root,owner.binding,run,role
    observer.sources,observer.peers,observer.samples,observer.policy,observer.lock=sources,peers,samples,owner.policy,lock
    observer.phase=SimpleNamespace(fixture_url=owner.fixture_url,previous=dict(instance=owner.phase_instance))
    observer.state=observer.decode(PrivateFeatureState(root/('ios-emote-'+role+'-observer.json')).read())
    runtime=SimpleNamespace(state_path=lambda selector:Path(roots[selector])/'session.json')
    suffix='/runs/'+run+'/';need(owner.fixture_url.endswith(suffix))
    flow=SimpleNamespace(root=root,role=role,run=run,state=state,store=feature_store,selector=role,primary_selector='primary',
        lock=lock,primary_lock=primary_lock,runtime=runtime,client=SimpleNamespace(url=owner.fixture_url[:-len(suffix)]))
    parts=dict(sources=sources,peers=peers,scope=scope,samples=samples,observer=observer,restoration=historical.rendered_owner.frames_owner)
    need(same(sources.store.read(),raw['sources']) and same(scope_store.read(),raw['scope'])
        and same(samples.store.read(),raw['sampleOwners']))
    for name,field in (('sources','sources'),('peers','peers'),('files','fileReceipts'),('entities','entities'),('pointers','pointers')):
        if native.paths[name] is not None:need(same(PrivateFeatureState(native.paths[name]).read(),raw[field]))
    for tail in ('marker-files','marker-script'):
        need(PrivateFeatureState(root/('ios-emote-'+role+'-'+tail+'.json')).read() is None)
    if role=='primary':
        for key,name in (('cleanup','cleanup-inputs'),('actions','inputs'),('background','background')):
            need(same(PrivateFeatureState(root/('ios-emote-'+name+'.json')).read(),raw['inputOwners'][key]))
    return flow,parts,owner,live
