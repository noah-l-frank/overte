"""Use the existing normal Pico pointer/IME bridge for its actual Create draft."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.token_lifecycle_ui import ID,VERSION,snapshot


def project(original):
    need(type(original.get('lifecycleControlsVersion')) is int and original['lifecycleControlsVersion']==VERSION)
    return snapshot(dict(lifecycleControlsVersion=VERSION,open=original['open'],ready=original['ready'],
        scope=dict(instance=original['bridgeId'],generation=original['generation'],sequence=original['lastCommandSequence'],
            elapsedMs=original['elapsedMs'],processId=original['processId']),
        controls=deepcopy([row for row in original['controls'] if row['id']==ID])))


class PicoLifecycleIO:
    def __init__(self,original):self.original=original
    def capture(self):return project(self.original.capture())
    def activate(self,identifier,*,reference):self.original.navigation.input(identifier,reference=reference)
    def replace(self,identifier,value,*,reference):self.original.navigation.input(identifier,'replace',value,reference=reference)
