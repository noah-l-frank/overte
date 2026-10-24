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

    def publish_retirement(self,parts):
        """One committed scene receipt per ticket; new facts for every cut.

        The scene journal deliberately rejects a second scene-stage POST for
        the same cleanup activation. Later quiet observations still have their
        own typed cleanup originals and independent ordinary fact publication.
        """
        need(self.role=='actor' and self.state['cleanup'])
        if not parts['observer'].publisher().resolve():
            raise EmoteObservationPending('An earlier facts publication is still unresolved')
        publisher=self.retirement_publisher(parts)
        if not publisher.resolve():
            raise EmoteObservationPending('An earlier scene publication is still unresolved')
        ticket=self.phase.previous['activations'][-1]['ticket'];matches=[]
        for reference in publisher.state['records']:
            row=publisher.load(reference)
            if row['mode']=='published' and row['intent']['body']['ticket']==ticket:
                need(row['intent']['body']['stage']==self.retirement_stage)
                matches.append((reference,row))
        need(len(matches)<=1)
        if matches:reference,row=matches[0]
        else:
            publisher.publish(self.state['cleanup'][-1])
            reference=publisher.state['records'][-1];row=publisher.load(reference)
        need(row['mode']=='published' and row['intent']['original'] in self.state['cleanup'])
        parts['observer'].publish_latest()
        actual=dict(kind='actor-published',original=row['intent']['original'],publisher=reference)
        if not same(self.state['retirement'],actual):self.state['retirement']=actual;self.save()
        return dict(performed=True)

    def finalize(self):
        # Version-one finalization declares full native drainage. A rooted
        # source cannot use it before its separate actual process-end owner.
        raise EmoteObservationPending('Rooted Emote responsibility still requires its typed terminal process end')
