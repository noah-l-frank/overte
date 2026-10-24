"""Reconstruct actual retained World Web owners without any live SDK access.

Every source/Scope/file/GPU byte graph is decoded by its owning type. The dummy
transports are fail-closed sentinels: they produce no packet and cannot acquire
current process, native, pixel, input or lifecycle facts.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from adapters.native_feature_observation import NativeFeatureObservation,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from adapters.script_feature.history import same
from ios.adapters.world_web_sources import WorldWebSources
from ios.adapters.world_web_scope import IOSWorldWebScope
from ios.adapters.world_web_identity import WorldWebLease
from ios.adapters.world_web_sample import WorldWebSample
from ios.adapters.world_web_input import WorldWebInput
from ios.adapters.world_web_file_receipts import WorldWebFileReceipts
from ios.adapters.world_web_observer import WorldWebObserver
from ios.adapters.world_web_retirement import WorldWebRetirement
from ios.adapters.world_web_actor_retirement import WorldWebActorRetirement


def forbidden(*_args,**_kwargs):
    raise RuntimeError('Historical World Web owner cannot access a live SDK')


def rebuild(flow):
    from ios.adapters.world_web_feature import IOSWorldWebFeature
    need(isinstance(flow,IOSWorldWebFeature));flow.lock.assert_held();flow.primary_lock.assert_held()
    need(flow.state is not None and same(flow.store.read(),flow.previous))
    state=flow.state
    def source(selector,role,lock,binding):
        owner=WorldWebSources(flow.runtime._world_web_store(selector,'ios-world-web-'+role+'-sources.json'),lock,binding,flow.run,role,
            lambda:True,phase=flow.phase,historical=True)
        # The GPU-clock historical decoder only requires the original PID and
        # unbound reader type; its receipts remain actual immutable files.
        owner.native=NativeFeatureObservation(forbidden,forbidden,forbidden,forbidden,owner.pid,ios=True)
        return owner
    primary=source(flow.primary_selector,'primary' if flow.role=='primary' else 'actor-primary',flow.primary_lock,state['primaryBinding'])
    marker_store=PrivateFeatureState(flow.runtime.state_path(flow.primary_selector).with_name('ios-worldweb-primary-marker.json'))
    marker=marker_store.read();need(marker is not None)
    scope=IOSWorldWebScope.archive(marker,root=flow.root,binding=primary.binding,run=flow.run,role='primary',lock=flow.primary_lock)
    scope.store,scope.previous=marker_store,marker
    scope.files.store=PrivateFeatureState(marker_store.path.with_name('ios-worldweb-primary-marker-files.json'))
    lease=None if state['lease'] is None else WorldWebLease(scope,primary,state['lease']['before'],state['lease']['after'])
    if flow.role=='actor':
        own=source(flow.selector,'actor',flow.lock,state['binding'])
        observer=WorldWebObserver(flow.runtime._world_web_store(flow.selector,'ios-world-web-actor-observer.json'),primary,flow.origins,forbidden,
            role='actor',peer=own,lease=lease,setup_scope=scope)
        if lease is None:
            from ios.adapters.world_web_setup_retirement import WorldWebSetupRetirement
            return WorldWebSetupRetirement(flow.runtime._world_web_store(flow.selector,'ios-world-web-actor-setup-retirement.json'),scope,observer,state['baseline'],sleep=forbidden)
        return WorldWebActorRetirement(flow.runtime._world_web_store(flow.selector,'ios-world-web-actor-retirement.json'),observer,sleep=forbidden)
    samples={}
    def sample(request):
        if request not in samples:
            frame=VulkanWorldFrameOwner(PrivateFeatureState(flow.runtime.state_path(flow.selector).with_name('graphics-world-frame-primary-0-'+request[4:]+'.json')),
                flow.root,primary.binding,flow.run,'primary',0,request,forbidden,lambda:True,source_lock=flow.lock)
            samples[request]=WorldWebSample(flow.runtime._world_web_store(flow.selector,'ios-world-web-primary-'+request[4:]+'-sample.json'),primary,frame,lambda:True)
        return samples[request]
    files_store=flow.runtime._world_web_store(flow.selector,'ios-world-web-primary-files.json');files=files_store.read()
    if files is None:
        # No file absence is manufactured for setup that never reserved files.
        # This empty typed owner has only fail-closed historical transports.
        need(lease is None and scope.state['fileOwnership'] is None)
        from adapters.native_script_files import NativeScriptFiles
        native_files=NativeScriptFiles(forbidden,forbidden,forbidden,forbidden,primary.pid,ios=True)
        receipts=WorldWebFileReceipts(files_store,flow.root,primary.binding,flow.run,'primary',flow.lock,forbidden,
            native=primary.native,files=native_files,epoch_ms=forbidden,monotonic=forbidden)
        receipts.historical=True
    else:receipts=WorldWebFileReceipts.archive(files,store=files_store,root=flow.root,binding=primary.binding,run=flow.run,role='primary',lock=flow.lock)
    need(state['beforeImage'] is not None)
    if lease is None:
        from ios.adapters.world_web_setup_retirement import WorldWebSetupRetirement
        observer=WorldWebObserver(flow.runtime._world_web_store(flow.selector,'ios-world-web-primary-observer.json'),primary,flow.origins,forbidden,
            role='primary',sample_resolver=sample,setup_scope=scope)
        return WorldWebSetupRetirement(flow.runtime._world_web_store(flow.selector,'ios-world-web-primary-setup-retirement.json'),scope,observer,state['baseline'],
            baseline_image=sample(state['beforeImage']),files=receipts,sample_factory=sample,sample_requests=state['images'],sleep=forbidden)
    inputs=WorldWebInput(flow.runtime._world_web_store(flow.selector,'ios-world-web-inputs.json'),primary,
        NativeUI(None,primary.binding['sessionId'],forbidden),lease.packet()['returned']['returned']['entityId'],forbidden)
    return WorldWebRetirement(flow.runtime._world_web_store(flow.selector,'ios-world-web-primary-retirement.json'),lease,sample(state['beforeImage']),receipts,sample,inputs,
        flow.origins,sample_requests=state['images'],sleep=forbidden)
