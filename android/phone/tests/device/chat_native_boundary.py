"""Synthetic Phone native envelope over the shared widget fixture."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from self_tests.test_token_chat_ui import Widgets
from create_native_boundary import CreateNativeBoundary


class ChatNativeBoundary(CreateNativeBoundary):
    wire_action='phone-chat-ui'
    def __init__(self):
        self.ui=Widgets();self.ui.panel=True;self.ui.pid=31;self.native=self.ui
        self.value=None;self.commands=[];self.input_requests=[];self.mutate=None;self.before_input=None
        self.source_sequence=0
    def raw(self):
        self.source_sequence+=1;value=self.ui.capture();scope=value['scope']
        return dict(schemaVersion=1,chatControlsVersion=1,instance=scope['instance'],generation=scope['generation'],
            sourceSequence=self.source_sequence,lastCommandSequence=scope['sequence'],elapsedMs=scope['elapsedMs'],
            capturedEpochMs=20000,processId=31,ready=value['ready'],controls=value['controls'])
