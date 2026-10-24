"""Original Create controls on the candidate/OpenXR-bound normal Pico route."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.pico4.navigation import need
from adapters.token_create_ui import control_id,snapshot


def project(original):
    need(type(original.get('createControlsVersion')) is int and original['createControlsVersion']==1)
    return snapshot(dict(createControlsVersion=1,open=original['open'],ready=original['ready'],
        scope=dict(instance=original['bridgeId'],generation=original['generation'],sequence=original['lastCommandSequence'],
                   elapsedMs=original['elapsedMs'],processId=original['processId']),
        controls=deepcopy([row for row in original['controls'] if control_id(row['id'])])))


class PicoCreateIO:
    def __init__(self,original):self.original=original
    def bind_before_send(self,callback):self.original.navigation.io.bind_before_send(callback)
    def capture(self):return project(self.original.capture())
    def activate(self,identifier,*,reference):self.original.navigation.input(identifier,reference=reference)
    def replace(self,identifier,value,*,reference):self.original.navigation.input(identifier,'replace',value,reference=reference)
    def select_index(self,identifier,value,*,reference):self.original.navigation.input(identifier,'select-index',index=value,reference=reference)
    def scroll(self,identifier,value,*,reference):self.original.navigation.input(identifier,'scroll',direction=value,reference=reference)
