"""Original iOS Create controls; native UI component scope only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.token_create_ui import control_id,snapshot


def project(original):
    need(type(original.get('createControlsVersion')) is int and original['createControlsVersion']==1)
    rows=deepcopy([row for row in original['controls'] if control_id(row['id'])])
    for row in rows:row.pop('frame') # NativeInput validated the actual original geometry.
    return snapshot(dict(createControlsVersion=1,open=original['tabletShown'],ready=original['ready'],
        scope=dict(instance=original['instance'],generation=original['createGeneration'],sequence=original['lastSequence'],
                   elapsedMs=original['elapsedMs'],processId=original['processId']),controls=rows))


class IOSCreateIO:
    def __init__(self,original):self.original=original
    def capture(self):return project(self.original.capture())
    def activate(self,identifier,*,reference):self.original.native.create_input(identifier,'activate',reference=reference)
    def replace(self,identifier,value,*,reference):self.original.native.create_input(identifier,'replace',reference=reference,value=value)
    def select_index(self,identifier,value,*,reference):self.original.native.create_input(identifier,'select-index',reference=reference,value=value)
    def scroll(self,identifier,value,*,reference):self.original.native.create_input(identifier,'scroll',reference=reference,value=value)
