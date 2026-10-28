"""Existing Emote source/image observations with explicit marker-scope two.

This changes only the selected original scope reader. Live facts, images,
original storage, inputs and publication remain the existing owner pipeline.
It supplies no held-resource finalization or complete capability by itself.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import exact,need
from feature_journeys.contract import identifier
from ios.adapters.emote_held_marker_scope import IOSEmoteHeldMarkerScope
from ios.adapters.emote_observation import IOSEmoteObservationDecoder
from ios.adapters.emote_observer import IOSEmoteObserver
from ios.adapters.emote_samples import archived_sample


class IOSEmoteHeldObservationDecoder(IOSEmoteObservationDecoder):
    Marker=IOSEmoteHeldMarkerScope
    ImageArchive=staticmethod(archived_sample)

    def image(self,value,marker):
        exact(marker,{'nonce','url','scope'});identifier(marker['nonce'])
        scope=self.Marker.archive(marker['scope'],root=self.root,binding=self.binding,run=self.run,role=self.role,
            lock=self.lock,require_ready=True)
        frame,raw,image,name=self.ImageArchive(value,root=self.root,binding=self.binding,run=self.run,role=self.role,
            lock=self.lock,policy=self.policy,marker_nonce=marker['nonce'],marker_url=marker['url'])
        need(value['iosEmoteSampleVersion']>=2 and (image is None or image['iosEmoteImageVersion']>=2))
        for key in ('worldBefore','worldAfter'):need(scope.bind_image_world(frame[key])=={k:marker[k] for k in ('nonce','url')})
        return frame,raw,image,name


class IOSEmoteHeldObserver(IOSEmoteObserver):
    Decoder=IOSEmoteHeldObservationDecoder

    def select_decoder(self):
        self.decoder=self.Decoder(self.sources,self.binding,self.role,self.root,self.policy,self.lock,
            phase_instance=self.phase.previous['instance'],peers=self.peers)

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.select_decoder()

    def decode(self,value):
        # Parent construction dispatches here before decoding earlier records.
        # Every old original is checked by the same explicit scope-two reader.
        self.select_decoder();return super().decode(value)
