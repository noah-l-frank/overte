"""Normal candidate-bound tablet Open/Close inputs with durable one-send intent."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import context
from overte_phone_script_history import same


class PhoneTabletControls:
    def __init__(self,ui,store,binding,guard,*,monotonic=time.monotonic,sleep=time.sleep):
        self.ui,self.store,self.binding,self.guard=ui,store,deepcopy(context(binding)),guard
        self.monotonic,self.sleep=monotonic,sleep;self.previous=store.read();self.state=deepcopy(self.previous)
        if self.state is not None:
            exact(self.state,{'phoneTabletControlsVersion','binding','phase'})
            need(type(self.state['phoneTabletControlsVersion']) is int and self.state['phoneTabletControlsVersion']==1
                and same(self.state['binding'],self.binding) and self.state['phase'] in ('open-issued','active','close-issued'))

    def save(self,phase):
        value=dict(phoneTabletControlsVersion=1,binding=self.binding,phase=phase)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value);self.state=deepcopy(value)

    def check(self):need(self.guard() is not False)

    def absent(self):
        start=previous=self.monotonic();count=0
        for attempt in range(81):
            self.check();need(not self.ui.tablet_visible());now=self.monotonic();need(number(now,previous,start+10));previous=now;count+=1
            if count>=3 and now-start>=3:return
            need(attempt<80);self.sleep(.1)
        need(False)

    def open(self):
        self.check()
        if self.state is not None:
            need(self.state['phase']=='active' and self.ui.tablet_visible());return {'performed':True}
        need(not self.ui.tablet_visible());self.save('open-issued');self.ui.open_tablet()
        self.check();need(self.ui.tablet_visible());self.save('active');return {'performed':True}

    def close(self):
        self.check()
        if self.state is None:
            need(not self.ui.tablet_visible());self.absent();return {'performed':True}
        if self.state['phase']!='close-issued':
            self.save('close-issued')
            if self.ui.tablet_visible():self.ui.close_tablet()
        # An uncertain close is never sent again. Only actual fresh absence can
        # resolve its durable intent; a visible replacement stays unavailable.
        self.absent();self.check();self.store.discard(self.previous);self.previous=self.state=None
        return {'performed':True}

    def cleanup(self):return self.close()
