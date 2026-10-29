"""Explicit Callback Live2 on the existing once-only rooted live journal.

Original Archive2 selects exact Native4/Rendered4/Keyed4/Scene4. Legacy Live1
keeps Archive1 and literal owner2. Terminal/State/process/SDK admission is closed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from ios.adapters.emote_callback_scene import IOSEmoteCallbackKeyedRetirement,IOSEmoteCallbackSceneFeature,PROFILE6
from ios.adapters.emote_rooted_feature import IOSEmoteRootedFeature
from ios.adapters.emote_rooted_live import IOSEmoteRootedLive
from ios.adapters import emote_callback_archive as archive
from ios.adapters.emote_callback_current_state import current as current_state


class IOSEmoteCallbackLive(IOSEmoteRootedLive):
    Owner=IOSEmoteCallbackKeyedRetirement
    FORMAT_VERSION=2

    def capture_snapshot(self,reference):
        # Base.append has already performed its original owner.current().
        # Validate current copied State/GPU continuity AFTER that admission and
        # BEFORE any new Live intent, without a duplicate SDK/owner guard.
        snapshot=archive.capture(self.owner,reference)
        current_state(snapshot,lock=self.lock,primary_lock=self.primary_lock)
        return snapshot

    def read_snapshot(self,snapshot):return archive.read(snapshot,lock=self.lock,primary_lock=self.primary_lock)

    def group_snapshots(self,snapshots):return archive.grouped(snapshots,lock=self.lock,primary_lock=self.primary_lock)


PROFILE7=dict(PROFILE6,callbackProfileVersion=4,liveVersion=2,archiveVersion=2)


class IOSEmoteCallbackLiveFeature(IOSEmoteCallbackSceneFeature):
    FORMAT_VERSION=7
    PAIRED_FORMAT_VERSION=7

    def profile_envelope(self,state):
        value=IOSEmoteRootedFeature.profile_envelope(self,state)
        if self.previous is not None:need(self.previous.get('iosEmoteFeatureVersion')==7 and same(self.previous.get('callbackProfile'),PROFILE7))
        return dict(value,callbackProfile=deepcopy(PROFILE7))

    def retirement_sample(self,parts,after_sequence=0,*,fresh_end=False):
        if self.state['cleanup']:
            live=IOSEmoteCallbackLive(self.retirement_owner(parts))
            if live.state['pending'] is not None:live.recover()
        return super().retirement_sample(parts,after_sequence,fresh_end=fresh_end)

    def retirement_public(self,owner,reference,public):
        measured=IOSEmoteCallbackLive(owner).append(reference)['measurement']
        need(same(measured['sourcePublic'],public));return measured['public']
