"""Immediate Graphics component; no canonical iOS installed-code association."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.normal_feature_state import need
from adapters.normal_ui import Locator
from adapters.token_graphics_ui import graphics_control


class IOSGraphicsIO:
    def __init__(self,original):self.original=original

    def capture(self):
        value=self.original.capture()
        need(type(value.get('graphicsControlsVersion')) is int and value['graphicsControlsVersion']==1)
        return value

    def activate(self,identifier,*,token):
        need(graphics_control(identifier) and identifier not in ('graphics.page','graphics.resolution','graphics.scrollbar'))
        value=self.capture();rows=[r for r in value['controls'] if r['id']==identifier]
        need(len(rows)==1 and rows[0]['enabled'] and rows[0]['inputReady'] and rows[0]['viewport']=='visible' and rows[0]['token']==token)
        self.original.ui.click_with_token(Locator('accessibility id','OverteNavigation.'+identifier),token)

    def scroll(self,identifier,direction,*,token):
        need(identifier=='graphics.scrollbar' and direction in ('up','down'))
        self.original.native.scroll(direction,token=token,field=identifier)

    def set_value(self,identifier,value,*,token):
        need(identifier=='graphics.resolution')
        self.original.native.set_value(identifier,value,token=token)
