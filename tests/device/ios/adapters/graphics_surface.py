"""Ordinary generic iOS Graphics, Go To and View-menu input.

Delivery only: the owner must persist intent before each mutation and validate
independent original scene/view/preference/render effects afterwards.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from urllib.parse import urlsplit
from adapters.native_feature_observation import need
from adapters.native_graphics_subject import NativeGraphicsSubject
from adapters.normal_ui import Locator,NativeUIError
from adapters.token_graphics_ui import TokenGraphicsUI
from adapters.token_script_ui import TokenScriptUI
from feature_journeys.contract import identifier
from ios.adapters.view_controls import MODES,IDS as VIEW_IDS,metadata as view_metadata

VERSION=1


class IOSGraphicsSurface:
    def __init__(self,original,subject,graphics,run,intent,owns,lease,allow_url):
        identifier(run)
        need(isinstance(subject,NativeGraphicsSubject) and subject.ios and subject.clock_bound
             and isinstance(graphics,TokenGraphicsUI) and graphics.io.original is original
             and all(callable(value) for value in (intent,owns,lease,allow_url)))
        self.original,self.ui,self.subject,self.graphics,self.run=original,original.ui,subject,graphics,run
        self.intent,self.owns,self.lease,self.allow_url=intent,owns,lease,allow_url
        self.tablet=TokenScriptUI(original,monotonic=self.ui.monotonic,sleep=self.ui.sleep)
        self.graphics.intent=self._graphics_intent;self.started=None

    @staticmethod
    def locator(identifier):return Locator('accessibility id','OverteNavigation.'+identifier)

    @contextmanager
    def operation(self):
        outer=self.started is None
        if outer:self.started=self.ui._now()
        try:self.bound();yield;self.bound()
        finally:
            if outer:self.started=None

    def bound(self):
        need(self.started is not None and self.ui._now()-self.started<20 and self.subject.guard() is not False)

    def owned(self,field):
        need(field in ('tablet','address','menu'));value=self.owns(field);need(type(value) is bool);return value

    def mark(self,field,value):
        need(type(value) is bool and self.lease(field,value) is not False and self.owned(field) is value);self.bound()

    def before(self,stage,control,graphics=None):
        if graphics is None:graphics=self.graphics.capture()
        source=self.subject.read(self.run,require_avatar=True);self.bound()
        need(self.intent(stage,deepcopy(source),deepcopy(graphics),control) is not False);self.bound()
        return source

    def _graphics_intent(self,stage,value,control):self.before('graphics-'+stage,control,value)

    def raw(self):
        value=self.original.capture();self.bound();return value

    def row(self,identifier):
        rows=[row for row in self.raw()['controls'] if row['id']==identifier]
        need(len(rows)<=1);return rows[0] if rows else None

    def click(self,identifier,stage):
        row=self.row(identifier);need(row is not None and row['enabled'])
        if identifier in VIEW_IDS:view_metadata(row)
        self.before(stage,identifier)
        self.ui.click_with_token(self.locator(identifier),row['token']);self.bound()

    def wait(self,predicate):
        for attempt in range(101):
            self.bound();value=self.raw()
            if predicate(value):return value
            if attempt<100:self.ui.sleep(.1)
        raise NativeUIError('Normal iOS Graphics surface did not reach its original control state')

    def address_visible(self):return self.ui.available(self.locator('address.field'),require_enabled=False)

    def close_address(self):
        with self.operation():
            if self.address_visible():need(self.owned('address'));self.click('address.cancel','address-cancel')
            self.ui.wait_absent(self.locator('address.field'));self.bound()
            if self.owned('address'):self.mark('address',False)

    def open_tablet(self):
        with self.operation():
            self.close_address()
            if self.raw()['tabletShown']:need(self.owned('tablet'));return
            self.before('tablet-open','tablet.open');self.mark('tablet',True)
            self.ui.click(Locator('accessibility id','OverteTabletOpen'))
            self.wait(lambda value:value['tabletShown'])
            # Pin this ordinary input context only after the actual window
            # transition. Original acquisition readers retain both generations.
            self.graphics.identity=None

    def known_tablet(self):
        value=self.raw()
        return any(row['id'] in ('tablet.home','scripts.menu','settings.entry','graphics.settings-entry','graphics.page')
            or row['id'].startswith('tablet.page.') or self.owned('menu') and row['id'] in VIEW_IDS
            for row in value['controls'])

    def close_tablet(self):
        with self.operation():
            if self.raw()['tabletShown']:
                need(self.owned('tablet') and self.known_tablet())
                self.before('tablet-close','tablet.close')
                self.ui.click(Locator('accessibility id','OverteTabletClose'))
            self.wait(lambda value:not value['tabletShown']);self.bound()
            self.graphics.identity=None # Only after verified actual window closure.
            if self.owned('menu'):self.mark('menu',False)
            if self.owned('tablet'):self.mark('tablet',False)

    def home(self):
        if self.row('tablet.home') is not None:self.click('tablet.home','tablet-home')

    def find_entry(self,identifier):
        pages=[row['id'] for row in self.raw()['controls'] if row['id'].startswith('tablet.page.')]
        pages.sort(key=lambda value:int(value.rsplit('.',1)[1]))
        for page in [None,*pages]:
            if page is not None:self.click(page,'tablet-'+page)
            for _attempt in range(7):
                if self.row(identifier) is not None:return
                self.ui.sleep(.1);self.bound()
        raise NativeUIError('Normal iOS Graphics surface entry is unavailable')

    def open(self):
        with self.operation():
            self.open_tablet()
            if self.row('graphics.page') is None:
                if self.row('graphics.settings-entry') is None:
                    need(self.known_tablet());self.home();self.find_entry('settings.entry')
                    self.click('settings.entry','settings-open')
                    self.wait(lambda value:any(row['id']=='graphics.settings-entry' for row in value['controls']))
                self.click('graphics.settings-entry','graphics-open')
                self.wait(lambda value:any(row['id']=='graphics.page' for row in value['controls']))
            page=self.graphics.row(self.graphics.capture(),'graphics.page')
            need(page is not None and page['profile']=='generic-immediate-v1' and self.raw()['tabletShown'])
            return {'performed':True}

    def set_resolution(self,value):
        with self.operation():
            need(self.owned('tablet') and self.raw()['tabletShown']);self.graphics.set_resolution(value);self.bound()
            return {'performed':True}

    def toggle(self,identifier,enabled):
        with self.operation():
            need(self.owned('tablet') and self.raw()['tabletShown']);self.graphics.toggle(identifier,enabled);self.bound()
            return {'performed':True}

    def select_camera(self,mode):
        with self.operation():
            need(type(mode) is str and mode in MODES)
            if self.subject.read(self.run,require_avatar=True)['source']['view']['mode']==mode:return {'performed':False}
            self.open_tablet();need(self.known_tablet());self.home();self.find_entry('scripts.menu')
            self.mark('menu',True);self.click('scripts.menu','menu-open')
            self.wait(lambda value:any(row['id']=='view.menu' for row in value['controls']))
            self.click('view.menu','menu-view')
            target=MODES[mode];self.wait(lambda value:any(row['id']==target for row in value['controls']))
            self.click(target,'camera-select')
            for attempt in range(51):
                source=self.subject.read(self.run,require_avatar=True);self.bound()
                if source['source']['view']['mode']==mode:self.close_tablet();return {'performed':True}
                if attempt<50:self.ui.sleep(.1)
            raise NativeUIError('Ordinary iOS camera pointer did not change the original camera mode')

    def navigate(self,url):
        with self.operation():
            need(type(url) is str and 0<len(url)<=2048 and all(ord(char)>=32 and ord(char)!=127 for char in url))
            parsed=urlsplit(url);parsed.port
            need(parsed.scheme in ('http','https','file','overte') and parsed.username is None and parsed.password is None
                 and not parsed.fragment and (parsed.scheme=='file' or bool(parsed.hostname)) and self.allow_url(url) is True)
            self.close_tablet()
            if self.address_visible():need(self.owned('address'))
            else:
                self.before('address-open','hud.goto');self.mark('address',True);self.click('hud.goto','address-open-pointer')
                self.wait(lambda value:any(row['id']=='address.field' for row in value['controls']))
            self.click('address.field','address-focus');self.before('address-replace','address.field')
            need(self.allow_url(url) is True);self.original.native.edit('replace',url,field='address.field');self.bound()
            self.click('address.go','address-go')
            self.ui.wait_absent(self.locator('address.field'));self.bound();self.mark('address',False)
            return {'performed':True}
