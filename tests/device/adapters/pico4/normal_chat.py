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
    def bind_before_send(self,callback):self.original.navigation.io.bind_before_send(callback)
    def bind_input_fence(self,fence):
        native=self.original.navigation.io
        native.bind_before_send(fence.before_send)
        native.bind_controller_admission(fence.before_controller,intent=fence.stage_intent,before_publish=fence.before_publish)
    def capture(self):return project(self.original.capture())
    def activate(self,identifier,*,reference):self.original.navigation.input(identifier,reference=reference)
    def replace(self,identifier,value,*,reference):self.original.navigation.input(identifier,'replace',value,reference=reference)
    def submit(self,identifier,*,reference):self.original.navigation.input(identifier,'submit',reference=reference)

    def open_tablet(self,*,reference):
        snapshot(reference);need(not reference['open'] and reference['controls']==[])
        current=self.capture();old=reference['scope'];actual=current['scope']
        need(not current['open'] and current['controls']==[]
            and all(actual[key]==old[key] for key in ('instance','generation','sequence','processId'))
            and 0<=actual['elapsedMs']-old['elapsedMs']<=5000)
        # Reuse the original installed/OpenXR-owned gesture and its durable
        # tablet input journal; never synthesize a QML activate command.
        self.original.navigation.open()
