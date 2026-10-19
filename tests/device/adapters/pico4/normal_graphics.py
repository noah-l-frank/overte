"""Immediate Graphics inputs on the existing candidate-bound Pico VR route."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.pico4.navigation import need


class PicoGraphicsIO:
    def __init__(self,original):self.original=original

    def capture(self):
        value=self.original.capture()
        need(type(value.get('graphicsControlsVersion')) is int and value['graphicsControlsVersion']==1)
        return value

    def activate(self,identifier,*,token):self.original.navigation.input(identifier,token=token)
    def scroll(self,identifier,direction,*,token):
        self.original.navigation.input(identifier,'scroll',token=token,direction=direction)
    def set_value(self,identifier,value,*,token):
        self.original.navigation.input(identifier,'set-value',token=token,value=value)
