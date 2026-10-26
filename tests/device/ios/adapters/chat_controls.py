"""Original iOS Chat normal input; explicitly unbound native component scope."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.token_chat_ui import control_id,snapshot


def project(original):
    need(type(original.get('chatControlsVersion')) is int and original['chatControlsVersion'] in (1,2))
    rows=deepcopy([row for row in original['controls'] if control_id(row['id'])])
    for row in rows:row.pop('frame') # NativeInput validated actual original geometry.
    return snapshot(dict(chatControlsVersion=original['chatControlsVersion'],open=original['tabletShown'],ready=original['ready'],
        scope=dict(instance=original['instance'],generation=original['chatGeneration'],sequence=original['lastSequence'],
                   elapsedMs=original['elapsedMs'],processId=original['processId']),controls=rows))


class IOSChatIO:
    def __init__(self,original):self.original=original
    def capture(self):return project(self.original.capture())
    def activate(self,identifier,*,reference):self.original.native.chat_input(identifier,'activate',reference=reference)
    def replace(self,identifier,value,*,reference):self.original.native.chat_input(identifier,'replace',reference=reference,value=value)
    def submit(self,identifier,*,reference):self.original.native.chat_input(identifier,'submit',reference=reference)
