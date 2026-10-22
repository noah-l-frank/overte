"""World Web abandoned passive acquisitions retain original native floors."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from adapters.original_marker_recovery import OriginalMarkerRecovery


class IOSWorldWebMarkerRecovery(OriginalMarkerRecovery):
    def __init__(self,scope):
        need(scope.components.profile=='worldweb');super().__init__(scope)
