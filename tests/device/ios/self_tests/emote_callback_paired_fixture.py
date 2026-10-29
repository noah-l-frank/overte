"""Declared callback producers chosen before actual paired owner births.

This reuses the established whole-role assembly and ordinary scene scheduling.
It supplies no expected observation/publication/terminal outcome. Native/SDK/
Qt/OS remain models; JS/W3C/UDP/HTTP/PNG and private originals are actual.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from adapters.native_feature_observation import need
from ios.adapters.emote_callback_retirement import IOSEmoteCallbackRetirementObserver
from ios.adapters.emote_callback_samples import IOSEmoteCallbackSamples
from ios.adapters.emote_callback_live import IOSEmoteCallbackLiveFeature
from ios.self_tests import emote_callback_observer_fixture as callback
from ios.self_tests import emote_rooted_whole_fixture as rooted_pair
from ios.self_tests import emote_whole_primary_fixture as primary_whole
from ios.self_tests import emote_whole_actor_fixture as actor_whole
from ios.self_tests import emote_active_actor_fixture as actor_observation


class CallbackActorFixture(actor_observation.ActiveActorFixture):
    # Same qualified actual single-context producer body, with this role's
    # original renderer view and its distinct native epoch chosen before birth.
    sync_gpu=callback.CallbackActiveFixture.sync_gpu
    gpu_sleep=callback.CallbackActiveFixture.gpu_sleep
    vulkan=callback.CallbackActiveFixture.vulkan

    def __init__(self,*args,**kwargs):
        need(kwargs.get('defer_setup') is True)
        self.callback_context=callback.DomainContext();self.trace_consumer=callback.HostTraceConsumer()
        self.frame_birth_ids={};self.callback_epoch_origin=None
        self.f=SimpleNamespace(recorded_view=self.recorded_view)
        super().__init__(*args,**kwargs)


def paired(test):
    # Both real canonical artifact roots exist BEFORE either role chooses its
    # original target pair, native callback context, marker or feature owner.
    # Use the exact original marker TD producer alias (retained by Root).
    original=callback.marker_fixture.tempfile
    directories=[original.TemporaryDirectory(),original.TemporaryDirectory()]
    for directory in directories:
        Path(directory.name).chmod(0o700);test.addCleanup(directory.cleanup)
    roots=[str(Path(item.name).resolve(strict=True)) for item in directories]
    chosen=dict(primaryTarget='primary',actorTarget='actor',primaryArtifactRoot=roots[0],actorArtifactRoot=roots[1])
    issued=[]
    def directory(*args,**kwargs):
        need(not args and not kwargs and len(issued)<2)
        item=directories[len(issued)];issued.append(item);return item
    class ConfiguredCallbackFeature(IOSEmoteCallbackLiveFeature):
        def __init__(self,*args,**kwargs):
            need('target_pair' not in kwargs);super().__init__(*args,target_pair=chosen,**kwargs)
    frames=callback.bundled_frames()
    with (patch.object(callback.marker_fixture,'tempfile',SimpleNamespace(TemporaryDirectory=directory)),
          patch.object(callback.vm_fixture,'ActualEmoteVM',partial(callback.vm_fixture.ActualEmoteVM,frame_counts=frames)),
          patch.object(callback.active_fixture,'ActualVMRig',partial(callback.active_fixture.ActualVMRig,pose_profile='requested-clip')),
          patch.object(primary_whole,'ActiveObserverFixture',callback.CallbackActiveFixture),
          patch.object(actor_whole,'ActiveActorFixture',CallbackActorFixture),
          patch.object(callback.active_fixture,'IOSEmoteSamples',IOSEmoteCallbackSamples),
          patch.object(actor_observation,'IOSEmoteSamples',IOSEmoteCallbackSamples),
          patch.object(rooted_pair,'IOSEmoteRootedObserver',IOSEmoteCallbackRetirementObserver),
          patch.object(rooted_pair,'IOSEmoteRootedFeature',ConfiguredCallbackFeature)):
        result=rooted_pair.paired(test)
    need(issued==directories and result.target.root==Path(roots[0]) and result.actor.target.root==Path(roots[1]))
    result.callback_selected_pair=chosen
    return result
