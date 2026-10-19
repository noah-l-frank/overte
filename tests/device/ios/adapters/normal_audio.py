"""iOS normal Audio component: no canonical installed-code association."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.normal_feature_state import need
from adapters.normal_ui import Locator
from adapters.token_audio_ui import audio_control


class IOSAudioIO:
    def __init__(self, original): self.original = original

    def capture(self):
        value=self.original.capture()
        need(type(value.get('audioControlsVersion')) is int and value['audioControlsVersion'] == 1)
        return value

    def activate(self, identifier, *, token):
        need(audio_control(identifier) and identifier not in ('audio.page','audio.scrollbar'))
        value=self.capture();rows=[r for r in value['controls'] if r['id']==identifier]
        need(len(rows)==1 and rows[0]['enabled'] and rows[0]['inputReady'] and rows[0]['token']==token)
        self.original.ui.click_with_token(Locator('accessibility id','OverteNavigation.'+identifier),token)

    def scroll(self, identifier, direction, *, token):
        need(identifier=='audio.scrollbar' and direction in ('up','down'))
        self.original.native.scroll(direction,token=token)
