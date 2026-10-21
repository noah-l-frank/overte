"""Ordinary Phone Graphics/Go To/View-menu input; full run ownership is separate."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from urllib.parse import urlsplit

from adapters.native_feature_observation import need
from adapters.native_graphics_subject import NativeGraphicsSubject
from adapters.normal_ui import Locator,NativeUI,NativeUIError
from adapters.token_graphics_ui import TokenGraphicsUI
from feature_journeys.contract import identifier
from overte_phone_script_ui import PhoneScriptUI

VERSION=1
MODES={'first person look at':'First Person','look at':'Look At','selfie':'Selfie'}


class PhoneGraphicsSurface:
    """Input receipts only. The caller durably owns each input and UI lease.

    intent(stage, original_subject, original_graphics_or_none, control_id)
    precedes each possible mutation. lease(field, bool) must durably update
    owns(field); explicit fresh UI absence precedes lease retirement. The owner
    must reject replay of an already issued ordinary action after a lost return.
    """
    def __init__(self,ui,subject,graphics,run,intent,owns,lease,allow_url):
        need(isinstance(ui,NativeUI) and isinstance(subject,NativeGraphicsSubject)
             and isinstance(graphics,TokenGraphicsUI) and all(callable(v) for v in (intent,owns,lease,allow_url)))
        identifier(run)
        self.ui,self.subject,self.graphics,self.run=ui,subject,graphics,run
        self.intent,self.owns,self.lease,self.allow_url=intent,owns,lease,allow_url
        self.tablet=PhoneScriptUI(ui,'io.github.noah_be.overte.phone');self.started=None
        self.graphics.intent=self._graphics_intent

    @contextmanager
    def operation(self):
        outer=self.started is None
        if outer:self.started=self.ui._now()
        try:
            self.bound();yield;self.bound()
        finally:
            if outer:self.started=None

    def bound(self):
        need(self.started is not None and self.ui._now()-self.started<20 and self.subject.guard() is not False)

    def owned(self,field):
        need(field in ('tablet','address','menu'));value=self.owns(field);need(type(value) is bool);return value

    def mark(self,field,value):
        need(type(value) is bool and self.lease(field,value) is not False and self.owned(field) is value);self.bound()

    def before(self,stage,control,graphics=None):
        value=self.subject.read(self.run,require_avatar=True);self.bound()
        need(self.intent(stage,deepcopy(value),deepcopy(graphics),control) is not False);self.bound()
        return value

    def control(self,locator):
        root=self.tablet.tree();key='resource-id' if locator.using=='id' else None
        rows=[row for row in root.iter() if row.get('package')==self.tablet.package
            and row.get('displayed','true')=='true' and row.get('enabled','true')=='true'
            and (row.get(key)==locator.value if key else locator.value in (row.get('text'),row.get('content-desc')))]
        need(len(rows)==1);self.bound()

    def click(self,stage,locator):
        self.control(locator);self.before(stage,locator.value);self.control(locator);self.ui.click(locator);self.bound()

    def _graphics_intent(self,stage,value,control):self.before('graphics-'+stage,control,value)

    def qt(self,identifier,stage):
        value=self.graphics.capture();row=self.graphics.row(value,identifier)
        need(row is not None and row['enabled'] and row['inputReady'] and row['viewport']=='visible')
        self.before(stage,identifier,value);self.graphics.io.activate(identifier,token=row['token']);self.bound()

    def known_tablet(self,value):
        if any(self.graphics.row(value,key) is not None for key in ('graphics.page','graphics.settings-entry','settings.entry')):return True
        if any(self.ui.available(self.tablet.resource('tabletPage.'+str(page))) for page in range(1,9)):return True
        if self.owned('menu'):
            labels={'View',*MODES.values()}
            return any(row.get('package')==self.tablet.package and row.get('displayed','true')=='true'
                and row.get('enabled','true')=='true' and (row.get('text') in labels or row.get('content-desc') in labels)
                for row in self.tablet.tree().iter())
        return False

    def close_address(self):
        with self.operation():
            field=self.tablet.resource('PhoneAddressField')
            if self.ui.available(field,require_enabled=False):
                need(self.owned('address'));self.click('address-cancel',self.tablet.resource('PhoneAddressCancelButton'))
            self.ui.wait_absent(field);self.bound()
            if self.owned('address'):self.mark('address',False)

    def open_tablet(self):
        with self.operation():
            self.close_address()
            if self.tablet.tablet_visible():need(self.owned('tablet'));return
            self.before('tablet-open','tablet.open');self.mark('tablet',True)
            self.control(self.tablet.resource('tablet.open'));self.ui.click(self.tablet.resource('tablet.open'))
            self.ui.wait_control(self.tablet.resource('nav.close'));self.bound()

    def close_tablet(self):
        with self.operation():
            if self.tablet.tablet_visible():
                need(self.owned('tablet'))
                value=self.graphics.capture()
                need(self.known_tablet(value))
                self.click('tablet-close',self.tablet.resource('nav.close'))
            self.ui.wait_absent(self.tablet.resource('nav.close'));self.bound()
            if self.owned('menu'):self.mark('menu',False)
            if self.owned('tablet'):self.mark('tablet',False)

    def navigate(self,url):
        """Enter only a caller-owned original/controlled URL through normal Go To."""
        with self.operation():
            need(type(url) is str and 0<len(url)<=2048 and all(ord(c)>=32 and ord(c)!=127 for c in url))
            parsed=urlsplit(url);parsed.port
            need(parsed.scheme in ('http','https','file','overte') and parsed.username is None and parsed.password is None
                 and not parsed.fragment and (parsed.scheme=='file' or bool(parsed.hostname)) and self.allow_url(url) is True)
            self.close_tablet();field=self.tablet.resource('PhoneAddressField')
            if self.ui.available(field,require_enabled=False):need(self.owned('address'))
            else:
                self.before('address-open','Go to destination');self.mark('address',True)
                locator=Locator('accessibility id','Go to destination');self.control(locator);self.ui.click(locator)
                self.ui.wait_control(field);self.bound()
            self.before('address-replace',field.value);self.control(field)
            need(self.allow_url(url) is True);self.ui.replace_text(field,url);self.bound();need(self.ui.text(field)==url)
            self.click('address-go',self.tablet.resource('PhoneAddressGoButton'))
            self.ui.wait_absent(field);self.bound();self.mark('address',False)
            return {'performed':True} # No loaded-scene/viewpoint claim.

    def open_settings(self):
        with self.operation():
            self.open_tablet();value=self.graphics.capture()
            if self.graphics.row(value,'graphics.settings-entry') is None:
                if self.graphics.row(value,'settings.entry') is None and self.graphics.row(value,'graphics.settings-entry') is None:
                    need(self.known_tablet(value))
                    if self.ui.available(self.tablet.resource('nav.home')):self.click('tablet-home',self.tablet.resource('nav.home'))
                    for page in range(1,9):
                        value=self.graphics.capture()
                        if self.graphics.row(value,'settings.entry') is not None:break
                        locator=self.tablet.resource('tabletPage.'+str(page))
                        if self.ui.available(locator):self.click('tablet-page-'+str(page),locator)
                    value=self.graphics.capture()
                if self.graphics.row(value,'settings.entry') is not None:
                    self.qt('settings.entry','settings-open')
                    self.graphics.wait(lambda current:self.graphics.row(current,'graphics.settings-entry') is not None);self.bound()
            need(self.tablet.tablet_visible());return {'performed':True}

    def open(self):
        with self.operation():
            self.open_tablet();value=self.graphics.capture()
            if self.graphics.row(value,'graphics.page') is None:
                self.open_settings();self.qt('graphics.settings-entry','graphics-open')
                value=self.graphics.wait(lambda current:self.graphics.row(current,'graphics.page') is not None);self.bound()
            page=self.graphics.row(value,'graphics.page');need(page is not None and page['profile']=='phone-immediate-v1')
            need(self.tablet.tablet_visible());return {'performed':True}

    def set_resolution(self,value):
        with self.operation():
            need(self.owned('tablet') and self.tablet.tablet_visible());self.graphics.set_resolution(value);self.bound()
            return {'performed':True}

    def toggle(self,identifier,enabled):
        with self.operation():
            need(self.owned('tablet') and self.tablet.tablet_visible());self.graphics.toggle(identifier,enabled);self.bound()
            return {'performed':True}

    def select_camera(self,mode):
        with self.operation():
            need(type(mode) is str and mode in MODES)
            original=self.subject.read(self.run,require_avatar=True);self.bound()
            if original['source']['view']['mode']==mode:return {'performed':False}
            self.open_tablet()
            need(self.known_tablet(self.graphics.capture()))
            if self.ui.available(self.tablet.resource('nav.home')):self.click('tablet-home',self.tablet.resource('nav.home'))
            menu=Locator('accessibility id','MENU')
            if not self.ui.available(menu):
                for page in range(1,9):
                    locator=self.tablet.resource('tabletPage.'+str(page))
                    if self.ui.available(locator):self.click('tablet-page-'+str(page),locator)
                    if self.ui.available(menu):break
            self.before('menu-open',menu.value);self.mark('menu',True);self.control(menu);self.ui.click(menu);self.bound()
            self.ui.wait_control(Locator('accessibility id','View'));self.click('menu-view',Locator('accessibility id','View'))
            locator=Locator('accessibility id',MODES[mode]);self.ui.wait_control(locator);self.click('camera-select',locator)
            for attempt in range(51):
                current=self.subject.read(self.run,require_avatar=True);self.bound()
                if current['source']['view']['mode']==mode:
                    self.close_tablet();return {'performed':True} # Independent render proof remains mandatory.
                if attempt<50:self.ui.sleep(.1)
            raise NativeUIError('Normal Phone camera input did not change the original camera mode')
