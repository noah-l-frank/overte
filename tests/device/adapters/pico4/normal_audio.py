"""Normal Audio input on the existing bound Pico VR token route."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.pico4.navigation import need


class PicoAudioIO:
    def __init__(self, original):
        self.original = original

    def bind_before_send(self, callback):
        self.original.navigation.io.bind_before_send(callback)

    def capture(self):
        value = self.original.capture()
        need(type(value.get('audioControlsVersion')) is int and value['audioControlsVersion'] == 1)
        return value

    def activate(self, identifier, *, token):
        self.original.navigation.input(identifier,token=token)

    def scroll(self, identifier, direction, *, token):
        self.original.navigation.input(identifier,'scroll',token=token,direction=direction)
