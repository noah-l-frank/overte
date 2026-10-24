"""Existing paired whole fixture with explicit rooted role producers selected.

Only fixture constructors differ. Actual controllers, normal JS/W3C, immutable
sources, UDP peer bytes, PNGs, publishers and original decoders run unchanged.
Native/SDK/Qt/GPU/clock producers remain declared host models.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import nullcontext
from unittest.mock import patch
from ios.adapters.emote_rooted_feature import IOSEmoteRootedFeature
from ios.adapters.emote_rooted_observation import IOSEmoteRootedObserver
from ios.self_tests import emote_active_observer_fixture as primary_observation
from ios.self_tests import emote_active_actor_fixture as actor_observation
from ios.self_tests import test_ios_emote_marker_scope as marker
from ios.self_tests.emote_rooted_marker_fixture import RootedMarkerDomain
from ios.self_tests.test_ios_emote_rooted_marker_scope import rooted
from ios.self_tests.emote_whole_primary_fixture import WholePrimaryFixture
from ios.self_tests.emote_whole_actor_fixture import WholeActorFixture
from ios.self_tests.emote_scene_pair_fixture import connect
from ios.self_tests.retained_host_roots import retain_owned_root


class RootedSharedClockDomain(actor_observation.SharedClockDomain,RootedMarkerDomain):
    def web(self,run,url):
        value=super().web(run,url);self.scope.web.last=deepcopy(value);return value


def paired(test,*,retain_originals=False):
    setup=marker.MarkerScopeTests.setUp
    def retained(case):
        setup(case);root=retain_owned_root(case.temp,expected_root=case.root)
        if not hasattr(test,'retained_original_roots'):test.retained_original_roots=[]
        test.retained_original_roots.append(root);print('Retained Emote original root: '+str(root),flush=True)
    with (patch.object(marker.MarkerScopeTests,'owner',rooted),
          patch.object(marker.MarkerScopeTests,'setUp',retained) if retain_originals else nullcontext(),
          patch.object(primary_observation.native_fixture,'RunningDomain',RootedMarkerDomain),
          patch.object(primary_observation,'IOSEmoteObserver',IOSEmoteRootedObserver),
          patch.object(actor_observation,'SharedClockDomain',RootedSharedClockDomain),
          patch.object(actor_observation,'IOSEmoteObserver',IOSEmoteRootedObserver)):
        primary=WholePrimaryFixture(test,feature_type=IOSEmoteRootedFeature)
        actor=WholeActorFixture(test,primary,feature_type=IOSEmoteRootedFeature)
    return connect(primary,actor)
