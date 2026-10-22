"""Avatar-owned peer archives retain genuine native source DTOs unchanged."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.original_avatar_peer_sources import OriginalAvatarPeerSources,VERSION
from ios.adapters.avatar_sources import AvatarPhaseChanged


class IOSAvatarPeerSources(OriginalAvatarPeerSources):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,profile='avatar',phase_changed=AvatarPhaseChanged,**kwargs)
