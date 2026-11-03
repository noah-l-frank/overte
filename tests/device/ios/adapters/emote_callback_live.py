"""Explicit Callback Live2 on the existing once-only rooted live journal.

Original Archive2 selects exact Native4/Rendered4/Keyed4/Scene4. Legacy Live1
keeps Archive1 and literal owner2. Terminal/State/process/SDK admission is closed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
from ios.adapters.emote_callback_live_records import CallbackLiveRecords
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

    def __init__(self,owner,*,historical_rows=None):
        need(historical_rows is None or type(historical_rows) is CallbackLiveRecords)
        self._historical_rows=historical_rows
        super().__init__(owner)

    @classmethod
    def archive(cls,value,*,store,lock,primary_lock,historical_rows=None):
        need(historical_rows is None or type(historical_rows) is CallbackLiveRecords)
        obj=cls._archive_header(value,store=store,lock=lock,primary_lock=primary_lock)
        obj._historical_rows=historical_rows;obj.state=obj.decode(value);return obj

    @classmethod
    @contextmanager
    def archive_scope(cls,value,*,store,lock,primary_lock,historical_rows=None):
        need(historical_rows is None or type(historical_rows) is CallbackLiveRecords)
        obj=cls._archive_header(value,store=store,lock=lock,primary_lock=primary_lock)
        obj._historical_rows=historical_rows
        with obj.decoding(value) as state:obj.state=state;yield obj

    def record(self,reference):
        history=getattr(self,'_historical_rows',None)
        if history is None:return super().record(reference)
        self.bound()
        with self.read_batch():return history.read(self,reference,lambda:self.read_record(reference))

    @contextmanager
    def decoding(self,value):
        history=getattr(self,'_historical_rows',None)
        if history is None or not history.literal():
            with super().decoding(value) as state:yield state
            return
        # The full inventory/prefix decoder remains the outer owner. Each cold
        # record still derives its actual original graph TWICE via the existing
        # AvatarRecordCache. Warm rows reopen exact physical file signatures
        # and restore actual reads; no copied result is a new/current sample.
        with self.read_batch():yield self.decode_state(value)

    def capture_snapshot(self,reference):
        # Base.append has already performed its original owner.current().
        # Validate current copied State/GPU continuity AFTER that admission and
        # BEFORE any new Live intent, without a duplicate SDK/owner guard.
        snapshot=archive.capture(self.owner,reference)
        current_state(snapshot,lock=self.lock,primary_lock=self.primary_lock,
            historical_rows=getattr(self,'_historical_rows',None))
        return snapshot

    def read_snapshot(self,snapshot):return archive.read(snapshot,lock=self.lock,primary_lock=self.primary_lock)

    def group_snapshots(self,snapshots):return archive.grouped(snapshots,lock=self.lock,primary_lock=self.primary_lock)


PROFILE7=dict(PROFILE6,callbackProfileVersion=4,liveVersion=2,archiveVersion=2)


class IOSEmoteCallbackLiveFeature(IOSEmoteCallbackSceneFeature):
    FORMAT_VERSION=7
    PAIRED_FORMAT_VERSION=7

    def retirement_owner(self,parts,*,rendered=None,keys=None):
        history=getattr(self,'_callback_live_historical_rows',None)
        if rendered is not None or keys is not None or history is None or not history.literal():
            return super().retirement_owner(parts,rendered=rendered,keys=keys)
        # Current key originals retain their ordinary SDK/header guards outside
        # the immutable historical construction. No fresh source/owner verdict
        # enters the pure validator or historical derivation memo.
        keys=self.keys(parts);keys.bound()
        if not history.literal():return super().retirement_owner(parts,keys=keys)
        boundary=dict(iosEmoteCallbackConstructionVersion=1,artifactRoot=str(self.root),
            stateRoot=str(self.store.path.parent),binding=self.state['binding'],runId=self.run,
            role=self.role,phaseInstance=self.state['phaseInstance'])
        from adapters.normal_feature_state import PrivateFeatureState
        with archive.original_round(boundary,lock=self.lock,primary_lock=self.primary_lock,
                key_packet_policy=archive.LITERAL_PACKETS):
            rendered=self.rendered_retirement_owner(parts)
            owner=self.KeyedRetirement(PrivateFeatureState(self.runtime.state_path(self.selector).with_name(
                'ios-emote-'+self.role+'-keyed-retirement-originals.json')),rendered,keys)
            need(history.literal())
        # Current guards run again after the frozen read. All mutable owner
        # journals/pending/orphan checks ran in the original constructors; a
        # current owner derivation is never memoized as a historical owner.
        keys.bound();return owner

    def live_owner(self,owner):
        history=getattr(self,'_callback_live_historical_rows',None)
        if history is None:
            history=CallbackLiveRecords();self._callback_live_historical_rows=history
        return IOSEmoteCallbackLive(owner,historical_rows=history)

    def profile_envelope(self,state):
        value=IOSEmoteRootedFeature.profile_envelope(self,state)
        if self.previous is not None:need(self.previous.get('iosEmoteFeatureVersion')==7 and same(self.previous.get('callbackProfile'),PROFILE7))
        return dict(value,callbackProfile=deepcopy(PROFILE7))

    def retirement_sample(self,parts,after_sequence=0,*,fresh_end=False):
        if self.state['cleanup']:
            live=self.live_owner(self.retirement_owner(parts))
            if live.state['pending'] is not None:live.recover()
        return super().retirement_sample(parts,after_sequence,fresh_end=fresh_end)

    def retirement_public(self,owner,reference,public):
        measured=self.live_owner(owner).append(reference)['measurement']
        need(same(measured['sourcePublic'],public));return measured['public']
