"""Emote v1 facade over the configured original receiver/renderer owner."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.original_avatar_peer_sources import OriginalAvatarPeerSources,VERSION
from ios.adapters.emote_sources import EmotePhaseChanged


class IOSEmotePeerSources(OriginalAvatarPeerSources):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,profile='emote',phase_changed=EmotePhaseChanged,**kwargs)
