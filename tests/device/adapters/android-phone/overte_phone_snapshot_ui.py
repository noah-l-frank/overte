"""Normal Snapshot navigation, choices and exact original image controls.

These methods deliver inputs and check actual widget transitions only. Separate
native/file/receiver/provider/peer originals must prove each feature effect.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import time

from adapters.native_feature_observation import integer,need,number
from adapters.normal_ui import NativeUIError
from overte_phone_snapshot_controls import PhoneSnapshotIO,original_path

MODES=('still','animated','panorama','cubemap')


class PhoneSnapshotControls:
    def __init__(self,io,tablet,intent,*,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(io,PhoneSnapshotIO) and callable(intent) and callable(monotonic) and callable(sleep)
            and all(callable(getattr(tablet,key,None)) for key in ('tablet_visible','open_tablet','close_tablet','release')))
        self.io,self.tablet,self.intent=io,tablet,intent
        self.monotonic,self.sleep,self.clock=monotonic,sleep,None

    def now(self):
        value=self.monotonic();need(number(value,0,1e15) and (self.clock is None or value>=self.clock));self.clock=value;return value

    def capture(self):return self.io.capture()

    @staticmethod
    def row(value,id,*,ready=True):
        rows=[row for row in value['controls'] if row['id']==id];need(len(rows)<=1)
        return rows[0] if rows and (not ready or rows[0]['enabled'] and rows[0]['inputReady']) else None

    def wait(self,predicate):
        start=previous=self.now()
        for attempt in range(51):
            value=self.capture();now=self.now();need(previous<=now and now-start<5);previous=now
            if predicate(value):return value
            if attempt<50:self.sleep(min(.1,max(0,5-(now-start))))
        raise NativeUIError('Original normal Snapshot widget transition was not observed')

    def input(self,id,action='activate',value=None):
        original=self.capture();need(self.row(original,id) is not None)
        self.io.input(id,action,reference=original,value=value)
        actual=self.capture()
        need(actual['instance']==original['instance'] and actual['generation']==original['generation']
            and actual['lastCommandSequence']==original['lastCommandSequence']+1
            and actual['sourceSequence']>original['sourceSequence'])
        return actual # Receipt/actual controls only, never a feature outcome.

    def sdk(self,action):
        need(action in ('tablet.open','tablet.close','input.release'))
        original=self.capture()
        need(self.intent(dict(snapshotSdkInputVersion=1,action=action,original=deepcopy(original))) is not False)
        if action=='tablet.open':self.tablet.open_tablet()
        elif action=='tablet.close':self.tablet.close_tablet()
        else:self.tablet.release()

    def open(self):
        if not self.tablet.tablet_visible():self.sdk('tablet.open')
        value=self.capture()
        if self.row(value,'snapshot.page',ready=False):return self.wait_page()
        if self.row(value,'tablet.home'):self.input('tablet.home')
        value=self.capture()
        pages=sorted((row['id'] for row in value['controls'] if row['id'].startswith('tablet.page.')),
            key=lambda id:int(id.rsplit('.',1)[1]))
        for page in [None,*pages]:
            if page is not None:self.input(page)
            deadline=self.now()+.6
            for attempt in range(7):
                value=self.capture()
                if self.row(value,'snapshot.entry'):
                    self.input('snapshot.entry');return self.wait_page()
                remaining=deadline-self.now()
                if remaining<=0 or attempt==6:break
                self.sleep(min(.1,remaining))
        raise NativeUIError('Original normal Snapshot entry is unavailable')

    def wait_page(self):
        return self.wait(lambda value:value['ready'] and self.row(value,'snapshot.page',ready=False) is not None
            and self.row(value,'snapshot.page',ready=False)['captureSettingsLoaded'])

    def name(self,value):
        need(type(value) is str and 1<=len(value)<=48 and all(32<=ord(char)<=126 for char in value))
        self.wait_page();self.input('snapshot.name');self.input('snapshot.name','replace',value)
        return self.wait(lambda actual:self.row(actual,'snapshot.name',ready=False) is not None
            and self.row(actual,'snapshot.name',ready=False)['text']==value)

    def choose(self,id,index):
        need(id in ('snapshot.mode','snapshot.format') and integer(index,0,7))
        value=self.wait_page();row=self.row(value,id);need(row is not None and index<row['count'])
        self.input(id);self.input(id,'select-index',index)
        return self.wait(lambda actual:self.row(actual,id,ready=False) is not None
            and self.row(actual,id,ready=False)['currentIndex']==index)

    def configure(self,mode,format):
        need(mode in MODES and format in ('png','jpg','jpeg','webp'))
        self.choose('snapshot.mode',MODES.index(mode))
        actual=self.wait_page();row=self.row(actual,'snapshot.format');need(row is not None and format in row['options'])
        return self.choose('snapshot.format',row['options'].index(format))

    def plan_cancel(self):
        value=self.wait_page();mode=self.row(value,'snapshot.mode',ready=False)
        need(mode is not None and mode['currentIndex']==MODES.index('animated'))
        return self.io.plan_capture(reference=value)

    def plan_image_action(self,action,path):
        need(action in ('save','share'))
        value,id=self._image_control(action,path)
        request=self.io._prepare(id,'activate',reference=value)
        return dict(request=request,original=deepcopy(value))

    def image_action(self,action,path):
        value,id=self._image_control(action,path)
        return self.input(id)

    def _image_control(self,action,path):
        need(action in ('save','share','upload') and original_path(path))
        id='snapshot.'+action+'.'+hashlib.sha256(path.encode()).hexdigest()
        self.wait_page()
        for attempt in range(13):
            value=self.capture();row=self.row(value,id)
            if row is not None:
                need(row['path']==path);return value,id
            scrollbar=self.row(value,'snapshot.scrollbar')
            if scrollbar is None or attempt==12:break
            before=scrollbar['position'];self.input('snapshot.scrollbar','scroll','down')
            self.wait(lambda actual:self.row(actual,id) is not None or self.row(actual,'snapshot.scrollbar',ready=False) is not None
                and self.row(actual,'snapshot.scrollbar',ready=False)['position']!=before)
        raise NativeUIError('Exact original Snapshot image action is unavailable')

    def close(self):
        self.sdk('tablet.close')
        self.wait(lambda value:self.row(value,'snapshot.page',ready=False) is None)
        need(not self.tablet.tablet_visible())

    def release(self):self.sdk('input.release')
