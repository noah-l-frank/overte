"""Original Chat controls over the existing installed/OpenXR-bound Pico route."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.pico4.navigation import need
from adapters.token_chat_ui import control_id,snapshot


def project(original):
    need(type(original.get('chatControlsVersion')) is int and original['chatControlsVersion'] in (1,2))
    return snapshot(dict(chatControlsVersion=original['chatControlsVersion'],open=original['open'],ready=original['ready'],
        scope=dict(instance=original['bridgeId'],generation=original['generation'],sequence=original['lastCommandSequence'],
                   elapsedMs=original['elapsedMs'],processId=original['processId']),
        controls=deepcopy([row for row in original['controls'] if control_id(row['id'])])))


class PicoChatIO:
    def __init__(self,original):self.original=original
    def capture(self):return project(self.original.capture())
    def activate(self,identifier,*,reference):self.original.navigation.input(identifier,reference=reference)
    def replace(self,identifier,value,*,reference):self.original.navigation.input(identifier,'replace',value,reference=reference)
    def submit(self,identifier,*,reference):self.original.navigation.input(identifier,'submit',reference=reference)
