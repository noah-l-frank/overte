"""Avatar marker passive-read recovery with its own original namespace."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.original_marker_recovery import OriginalMarkerRecovery,VERSION
from adapters.original_marker_scope import OriginalMarkerScope
from adapters.native_feature_observation import need


class IOSAvatarMarkerRecovery(OriginalMarkerRecovery):
    def __init__(self,scope):
        need(isinstance(scope,OriginalMarkerScope) and scope.components.profile=='avatar')
        super().__init__(scope)
