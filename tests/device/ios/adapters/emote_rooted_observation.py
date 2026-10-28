"""Existing Emote observation pipeline with the explicit scope-three reader."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from ios.adapters.emote_held_observation import IOSEmoteHeldObservationDecoder,IOSEmoteHeldObserver
from ios.adapters.emote_rooted_marker_scope import IOSEmoteRootedMarkerScope
from adapters.native_feature_observation import exact,need
from adapters.script_feature.history import same
from ios.adapters.emote_observation import ORIGINAL_FIELDS
from ios.adapters import emote_peer_continuation as continuation


class IOSEmoteRootedObservationDecoder(IOSEmoteHeldObservationDecoder):
    Marker=IOSEmoteRootedMarkerScope

    def original_shape(self,value):
        version=value.get('iosEmoteObservationOriginalVersion') if type(value) is dict else None
        if type(version) is int and version in (continuation.VERSION,continuation.RESTORED_VERSION):
            exact(value,ORIGINAL_FIELDS|{'peerContinuation'})
            need(self.role=='actor' and type(value['proof']) is dict and value['proof'].get('kind') in ('playback','restoration'))
            if version==continuation.RESTORED_VERSION:need(value['proof']['kind']=='restoration')
        else:super().original_shape(value)

    def peer_movement(self,value,current,after):
        if value['iosEmoteObservationOriginalVersion']==continuation.RESTORED_VERSION:
            return continuation.restored_derive(self,value,current,after)
        if value['iosEmoteObservationOriginalVersion']==continuation.VERSION:
            return continuation.derive(self,value,current,after)
        return super().peer_movement(value,current,after)


class IOSEmoteRootedObserver(IOSEmoteHeldObserver):
    Decoder=IOSEmoteRootedObservationDecoder

    def prepare_original(self,value):
        if self.role!='actor' or value['proof']['kind'] not in ('playback','restoration') or value['peerBefore'] is None:
            return value
        if value['proof']['kind']=='restoration':
            for reference in self.state['records']:
                original=self.original(reference)
                if (type(original.get('iosEmoteObservationOriginalVersion')) is int
                        and original['iosEmoteObservationOriginalVersion']==1 and original['proof']['kind']=='playback'
                        and continuation.episode(original['proof'],value['proof']) and original['peerBefore'] is not None
                        and original['peerAfter'] is not None):
                    latest=self.state['lastPeer'];need(latest is not None and not same(latest,value['peerAfter']))
                    for abandoned in self.state['abandoned']:
                        pending=abandoned['pending'];candidate=pending.get('peer')
                        if pending.get('ticket')!=value['ticket'] or candidate is None:continue
                        exact(candidate,{'index','sha256'})
                        need(type(candidate['index']) is int and 1<=candidate['index']<=512)
                        if latest['index']<candidate['index']<value['peerAfter']['index']:latest=candidate
                    return dict(value,iosEmoteObservationOriginalVersion=continuation.RESTORED_VERSION,
                        peerBefore=latest.copy(),peerContinuation=reference.copy())
        old=self.decoder.retained(self.peers,value['peerBefore'])['peer']['receive']['source']
        current=self.decoder.retained(self.peers,value['peerAfter'])['peer']['receive']['source']
        if current['droppedRecords']<=old['receiveSequence']:return value
        for reference in self.state['records']:
            original=self.original(reference)
            if (type(original.get('iosEmoteObservationOriginalVersion')) is int
                    and original['iosEmoteObservationOriginalVersion']==1
                    and continuation.episode(original['proof'],value['proof']) and original['peerAfter'] is not None):
                # Validation, including actual files and full initial motion,
                # happens in the decoder before the new original is retained.
                latest=self.state['lastPeer'];need(latest is not None and not same(latest,value['peerAfter']))
                # A fully returned peer cut can survive a failed passive image
                # acquisition. Its durable abandonment does not make any public
                # fact: the unchanged decoder must prove this actual BEFORE
                # frame, the original v1 episode and fresh strict motion again.
                for abandoned in self.state['abandoned']:
                    pending=abandoned['pending'];candidate=pending.get('peer')
                    if pending.get('ticket')!=value['ticket'] or candidate is None:continue
                    exact(candidate,{'index','sha256'})
                    need(type(candidate['index']) is int and 1<=candidate['index']<=512)
                    if latest['index']<candidate['index']<value['peerAfter']['index']:
                        latest=candidate
                return dict(value,iosEmoteObservationOriginalVersion=continuation.VERSION,
                    peerBefore=latest.copy(),peerContinuation=reference.copy())
        # No original anchor exists. Keep the unchanged strict decoder failure.
        return value
