"""Ordinary Audio page navigation, with mandatory pre-input ownership hooks.

This recipe reports observed UI only. Its caller must retain original effects,
unknown delivery and page/resource lifetime; this module advertises nothing.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
import time
from adapters.native_feature_observation import need,number
from adapters.normal_ui import Locator,NativeUI,NativeUIError
from adapters.token_audio_ui import TokenAudioUI
from ios.adapters.normal_audio import IOSAudioIO
from ios.adapters import tablet_launcher_controls as launcher

PRIMARY={'hud.tablet':'OverteTabletOpen','tablet.close':'OverteTabletClose'}
FIXED={'hud.tablet','tablet.close','tablet.home','audio.entry','settings.entry','audio.settings-entry','audio.back'}


class AudioPageInputs:
    def __init__(self,io,native_ui,intent,*,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(io,IOSAudioIO) and isinstance(native_ui,NativeUI) and all(callable(fn) for fn in (intent,monotonic,sleep)))
        self.io,self.native_ui,self.intent=io,native_ui,intent
        self.controls=TokenAudioUI(io,lambda *_:need(False),monotonic=monotonic,sleep=sleep)
        self.monotonic,self.sleep=monotonic,sleep

    def capture(self):
        value=self.controls.capture();need(type(value.get('tabletShown')) is bool);return value

    @staticmethod
    def route(value):
        pages=[row for row in value['controls'] if row['id']=='audio.page']
        if not value['tabletShown']:need(not pages);return 'closed'
        if pages:need(len(pages)==1);return 'audio'
        if any('tabletLauncherControlVersion' in row for row in value['controls']):launcher.selection(value);return 'launcher'
        if TokenAudioUI.row(value,'audio.settings-entry') is not None:return 'settings'
        return 'foreign'

    def click(self,label,control):
        need(type(label) is str and re.fullmatch('[a-z][a-z0-9-]{0,63}',label) is not None and type(control) is str
             and (control in FIXED or re.fullmatch(r'tablet\.page\.([1-9]|[12][0-9]|3[0-2])',control)))
        before=self.capture();rows=[row for row in before['controls'] if row['id']==control]
        need(len(rows)==1 and rows[0]['enabled'] and (control in PRIMARY or rows[0].get('inputReady',True)))
        row=rows[0];ui=self.native_ui;ui._check()
        element=ui._resolve(Locator('accessibility id',PRIMARY.get(control,'OverteNavigation.'+control)))
        if control not in PRIMARY:need(ui._request('GET',element+'/attribute/value')==row['token'])
        current=self.capture();need([row]==[item for item in current['controls'] if item['id']==control])
        # The actual resolved object is retained. No re-resolution after the
        # original token check, and no click is retried after a lost return.
        need(self.intent(label,control,deepcopy(current),element) is not False)
        ui._check();ui._request('POST',element+'/click',{});ui._check()

    def wait(self,predicate):
        started=self.monotonic();need(number(started,0,1e15));previous=started
        for _ in range(101):
            value=self.capture();current=self.monotonic();need(number(current,previous,1e15) and current<started+10)
            previous=current
            if predicate(value):return value
            self.sleep(.1)
        raise NativeUIError('Original Audio page navigation remains unresolved')

    def open(self):
        value=self.capture();kind=self.route(value)
        if kind=='audio':return dict(ui=deepcopy(value),launcher=None)
        need(kind in ('closed','launcher'))
        if kind=='closed':
            self.click('open-tablet','hud.tablet');value=self.wait(lambda packet:self.route(packet)=='launcher')
        original=launcher.selection(value);visited=set()
        for _ in range(32):
            value=self.capture();need(self.route(value)=='launcher');selection=launcher.selection(value)
            need(selection['launcherRootId']==original['launcherRootId'] and selection['launcherPageCount']==original['launcherPageCount'])
            visited.add(selection['launcherCurrentIndex'])
            if TokenAudioUI.row(value,'audio.entry',ready=True) is not None:
                self.click('open-audio','audio.entry');after=self.wait(lambda packet:self.route(packet)=='audio')
                return dict(ui=deepcopy(after),launcher=original)
            if TokenAudioUI.row(value,'settings.entry',ready=True) is not None:
                self.click('open-settings','settings.entry');self.wait(lambda packet:self.route(packet)=='settings')
                self.click('open-audio-settings','audio.settings-entry');after=self.wait(lambda packet:self.route(packet)=='audio')
                return dict(ui=deepcopy(after),launcher=original)
            remaining=[index for index in range(selection['launcherPageCount']) if index not in visited]
            need(remaining);target=remaining[0]
            self.click('find-audio-page-'+str(target),'tablet.page.'+str(target+1))
            self.wait(lambda packet:self.route(packet)=='launcher' and launcher.selection(packet)['launcherCurrentIndex']==target)
        raise NativeUIError('Actual launcher has no observed Audio route')

    def close(self,original_launcher):
        value=self.capture();kind=self.route(value);need(kind in ('audio','launcher'))
        if kind=='audio':
            self.click('restore-audio-home','tablet.home');value=self.wait(lambda packet:self.route(packet)=='launcher')
        selection=launcher.selection(value)
        need(type(original_launcher) is dict and selection['launcherPageCount']==original_launcher['launcherPageCount'])
        target=original_launcher['launcherCurrentIndex'];need(type(target) is int and 0<=target<selection['launcherPageCount'])
        if selection['launcherCurrentIndex']!=target:
            self.click('restore-audio-page','tablet.page.'+str(target+1))
            value=self.wait(lambda packet:self.route(packet)=='launcher' and launcher.selection(packet)['launcherCurrentIndex']==target)
        self.click('restore-audio-close','tablet.close');return self.wait(lambda packet:self.route(packet)=='closed')
