"""Original Create controls on the candidate/OpenXR-bound normal Pico route."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.pico4.navigation import need
from adapters.token_create_ui import control_id,snapshot


def project(original,*,pico_assets=False):
    need(type(original.get('createControlsVersion')) is int and original['createControlsVersion']==1)
    value=dict(createControlsVersion=1,open=original['open'],ready=original['ready'],
        scope=dict(instance=original['bridgeId'],generation=original['generation'],sequence=original['lastCommandSequence'],
                   elapsedMs=original['elapsedMs'],processId=original['processId']),
        controls=deepcopy([row for row in original['controls'] if control_id(row['id'],pico_assets=pico_assets)]))
    if pico_assets and 'picoAssetsCreateControlsVersion' in original:
        # The extended mode has its own discriminator. It cannot infer support
        # from a requested operation or an ordinary Create v1 packet.
        need(type(original.get('picoAssetsCreateControlsVersion')) is int and original['picoAssetsCreateControlsVersion']==1)
        value['picoAssetsCreateControlsVersion']=1
    return snapshot(value,pico_assets=pico_assets)


class PicoCreateIO:
    def __init__(self,original,*,pico_assets=False):
        need(type(pico_assets) is bool);self.original,self.pico_assets=original,pico_assets
    def bind_before_send(self,callback):self.original.navigation.io.bind_before_send(callback)
    def capture(self):return project(self.original.capture(),pico_assets=self.pico_assets)
    def activate(self,identifier,*,reference):self.original.navigation.input(identifier,reference=reference)
    def replace(self,identifier,value,*,reference):self.original.navigation.input(identifier,'replace',value,reference=reference)
    def select_index(self,identifier,value,*,reference):self.original.navigation.input(identifier,'select-index',index=value,reference=reference)
    def scroll(self,identifier,value,*,reference):self.original.navigation.input(identifier,'scroll',direction=value,reference=reference)
