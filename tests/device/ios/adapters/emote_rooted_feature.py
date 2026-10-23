"""Explicit whole Emote version two selects rooted cleanup and scene3.

Normal actions, original source observations, roles and delivery journals stay
the existing coordinator. Terminal/process integration is separately required;
this class does not advertise a complete capability or a legacy Complete.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from feature_journeys.retirement_receipts import WEB_SCENE_STAGE
from ios.adapters.emote_feature import IOSEmoteFeature
from ios.adapters.emote_observer import EmoteObservationPending
from ios.adapters.emote_rooted_marker_scope import IOSEmoteRootedMarkerScope
from ios.adapters.emote_rooted_observation import IOSEmoteRootedObserver
from ios.adapters.emote_rooted_retirement import (IOSEmoteRootedNativeRetirement,
    IOSEmoteRootedRenderedRetirement,IOSEmoteRootedKeyedRetirement)
from ios.adapters.emote_rooted_scene_retirement import IOSEmoteRootedSceneRetirement
from ios.adapters.emote_rooted_live import IOSEmoteRootedLive
from ios.adapters.emote_rooted_quiet import refresh,extend
from ios.adapters.emote_scene_proof import rooted


class IOSEmoteRootedFeature(IOSEmoteFeature):
    FORMAT_VERSION=2
    Marker=IOSEmoteRootedMarkerScope
    Observer=IOSEmoteRootedObserver
    NativeRetirement=IOSEmoteRootedNativeRetirement
    RenderedRetirement=IOSEmoteRootedRenderedRetirement
    KeyedRetirement=IOSEmoteRootedKeyedRetirement
    scene_proof_version=2
    scene_validator=staticmethod(rooted)
    retirement_stage=WEB_SCENE_STAGE

    @staticmethod
    def quiet_refresh(scope,*,clock,sleep,pointers,keys):
        return refresh(scope,pointers,keys,clock=clock,sleep=sleep)

    @staticmethod
    def quiet_extend(scope,pointers,*,keys):return extend(scope,pointers,keys)

    def retirement_public(self,owner,reference,public):
        value=IOSEmoteRootedLive(owner).append(reference)['measurement']
        need(same(value['sourcePublic'],public));return value['public']

    def retirement_sample(self,parts,after_sequence=0,*,fresh_end=False):
        if self.state['cleanup']:
            live=IOSEmoteRootedLive(self.retirement_owner(parts))
            if live.state['pending'] is not None:live.recover()
        return super().retirement_sample(parts,after_sequence,fresh_end=fresh_end)

    def retirement_decoder(self,owner):return IOSEmoteRootedSceneRetirement(owner).actor_original

    def finalize(self):
        # Version-one finalization declares full native drainage. A rooted
        # source cannot use it before its separate actual process-end owner.
        raise EmoteObservationPending('Rooted Emote responsibility still requires its typed terminal process end')
