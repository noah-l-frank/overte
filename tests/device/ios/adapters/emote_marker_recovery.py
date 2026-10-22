"""Emote passive marker-read recovery preserving the original v1 namespace."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.original_marker_recovery import OriginalMarkerRecovery,VERSION
from adapters.original_marker_scope import OriginalMarkerScope
from adapters.native_feature_observation import need


class IOSEmoteMarkerRecovery(OriginalMarkerRecovery):
    def __init__(self,scope):
        need(isinstance(scope,OriginalMarkerScope) and scope.components.profile=='emote')
        super().__init__(scope)
