"""Original Assets widgets on the existing candidate-bound Pico input route."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.token_assets_ui import control_id,snapshot


def project(value):
    need(type(value.get('assetsControlsVersion')) is int and value['assetsControlsVersion']==1)
    rows=deepcopy([row for row in value['controls'] if control_id(row['id'])])
    # Only the original generic Home row lacks feature inputReady metadata.
    for row in rows:
        if row['id']=='tablet.home':row.setdefault('inputReady',row['enabled'])
    return snapshot(dict(assetsControlsVersion=1,open=value['open'],ready=value['ready'],
        scope=dict(instance=value['bridgeId'],generation=value['generation'],sequence=value['lastCommandSequence'],elapsedMs=value['elapsedMs'],processId=value['processId']),controls=rows))


class PicoAssetsIO:
    def __init__(self,original):self.original=original
    def capture(self):return project(self.original.capture())
    def activate(self,identifier,*,reference):self.original.navigation.input(identifier,reference=reference)
    def probe_disabled(self,identifier,*,reference):self.original.navigation.input(identifier,'probe-disabled',reference=reference)
    def replace(self,identifier,value,*,reference):self.original.navigation.input(identifier,'replace',value,reference=reference)
    def submit(self,identifier,*,reference):self.original.navigation.input(identifier,'submit',reference=reference)
    def select_index(self,identifier,value,*,reference):self.original.navigation.input(identifier,'select-index',index=value,reference=reference)
    def scroll(self,identifier,value,*,reference):self.original.navigation.input(identifier,'scroll',direction=value,reference=reference)
