"""Replay actual interrupted original ownership before fixed metadata retires."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from adapters.original_avatar_peer_recovery import OriginalAvatarPeerRecovery
from adapters.original_marker_recovery import OriginalMarkerRecovery
from ios.adapters.emote_retirement import Frozen
from ios.adapters.emote_source_recovery import IOSEmoteSourceRecovery
from ios.adapters.emote_sample_recovery import IOSEmoteSampleRecovery


def validate(final,copies,sources,peers,scope,samples):
    f=final.flow
    def original(tail,primary=False):
        path=final.path('ios-emote-'+f.role+'-'+tail+'.json',primary=primary)
        return path,copies[str(path.path)]
    path,value=original('source-recovery',True)
    if value is not None:
        reader=IOSEmoteSourceRecovery.archive(value,sources);need(reader.state['pending'] is None)
        for ref in reader.state['records']:
            pending=reader.attempt(reader.record(ref))
            # A retained returned native fact needs a genuinely later complete
            # original. No historical flag may promote an unresolved prefix.
            if pending['pending']['partial']:need(pending['revision']<len(sources.frames))
        if reader.state['records']:reader.follow(sources.frames[-1],historical=True)
    if peers is not None:
        path,value=original('peer-recovery')
        if value is not None:
            reader=OriginalAvatarPeerRecovery.archive(value,peers);need(reader.state['pending'] is None)
            for ref in reader.state['records']:
                pending=reader.attempt(reader.record(ref))
                if pending['pending']['partial']:need(pending['revision']<len(peers.frames))
            if reader.state['records']:reader.follow(peers.frames[-1],historical=True)
    path,value=original('marker-recovery')
    if value is not None:
        reader=OriginalMarkerRecovery.archive(value,scope,Frozen(path.path,value));need(reader.state['pending'] is None)
        if reader.state['records']:reader.follow(scope.frames[-1],historical=True)
    path,value=original('sample-recovery')
    if value is not None:
        kind=getattr(final,'SampleRecovery',IOSEmoteSampleRecovery)
        if kind is not IOSEmoteSampleRecovery:
            from ios.adapters.emote_callback_observation import IOSEmoteCallbackSampleRecovery
            need(kind is IOSEmoteCallbackSampleRecovery)
        reader=object.__new__(kind);reader.samples=samples;reader.store=Frozen(path.path,value)
        reader.state=reader.decode(value);need(reader.state['pending'] is None)
    return True
