"""Actual Pico generic login widgets on the bound normal VR surface."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.pico4.navigation import need
from adapters.token_login_ui import IDS,VERSION


class PicoLoginIO:
    def __init__(self,original,home=None):
        self.original=original;self.epoch_floor=0;self.home=home

    def capture(self):
        value=self.original.capture()
        need(type(value.get('loginControlsVersion')) is int and value['loginControlsVersion']==VERSION
             and value['updatedEpochMs']>=self.epoch_floor)
        self.epoch_floor=value['updatedEpochMs']
        # Keep only actual original login rows. Other normal controls remain in
        # their independent source/transport; no state is manufactured here.
        result=deepcopy(value);result['controls']=[r for r in result['controls'] if r['id'] in IDS]
        return result

    def input(self,identifier,action,*,token,text=None):
        if action=='replace':
            try:self.original.navigation.input(identifier,action,text,token=token)
            finally:self.original.navigation.io.clear_private_input()
        else:
            need(text is None);self.original.navigation.input(identifier,action,token=token)

    def close_view(self):
        # Generic tablet pending pages have no cancel. This normal Home input
        # closes the actual page, while the AccountManager request stays alive.
        if self.home is not None:return self.home()
        value=self.original.capture()
        rows=[r for r in value['controls'] if r['id']=='tablet.home']
        need(len(rows)==1 and rows[0]['enabled'])
        self.original.navigation.input('tablet.home',token=rows[0]['token'])
