"""Ordinary VR Graphics/Go To inputs; effect and whole-run ownership are separate."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import hashlib
from urllib.parse import urlsplit
from adapters.native_feature_observation import need
from adapters.native_graphics_subject import NativeGraphicsSubject
from adapters.normal_ui import NativeUIError
from adapters.pico4.normal_graphics import PicoGraphicsIO
from adapters.pico4.normal_scripts import PicoScriptIO
from adapters.pico4.tablet_home import PicoTabletHome
from adapters.token_graphics_ui import TokenGraphicsUI
from adapters.token_script_ui import TokenScriptUI
from feature_journeys.contract import identifier

VERSION=1


class PicoGraphicsSurface:
    """Intent/lease callbacks must commit to the owning durable action first.

    A callback receives (stage, original_subject, typed_original_input_source,
    control). It must reject replay after uncertain delivery. This surface sends
    each input once and reports input receipts, never a feature-effect verdict.
    """
    def __init__(self,ui,subject,home,run,intent,owns,lease,allow_url):
        need(isinstance(ui,TokenScriptUI) and isinstance(ui.io,PicoScriptIO)
            and isinstance(subject,NativeGraphicsSubject) and subject.require_framework is True
            and isinstance(home,PicoTabletHome) and all(callable(v) for v in (intent,owns,lease,allow_url)))
        identifier(run)
        self.ui,self.subject,self.home,self.run=ui,subject,home,run
        self.intent,self.owns,self.lease,self.allow_url=intent,owns,lease,allow_url
        self.started=None
        self.graphics=TokenGraphicsUI(PicoGraphicsIO(ui.io),self._graphics_intent,monotonic=ui.monotonic,sleep=ui.sleep)
        initial=ui.capture()
        need(initial.get('navigationAddressVersion')==1 and initial.get('graphicsControlsVersion')==1)
        navigation=ui.io.navigation
        need(subject.pid==navigation.process_id==home.source.pid and navigation.address_authority is None)
        # An explicit per-instance scope replaces the legacy configured URL set.
        # No global, operation registry or other navigation instance is widened.
        navigation.address_authority=self.authorized_url

    @contextmanager
    def operation(self):
        outer=self.started is None
        if outer:self.started=self.ui.now()
        try:self.bound();yield;self.bound()
        finally:
            if outer:self.started=None

    def bound(self):
        need(self.started is not None and self.ui.now()-self.started<20 and self.subject.guard() is not False)

    def owned(self,field):
        need(field in ('tablet','address','menu'));value=self.owns(field);need(type(value) is bool);return value

    def mark(self,field,value):
        need(type(value) is bool and self.lease(field,value) is not False and self.owned(field) is value);self.bound()

    def before(self,stage,control,source):
        value=self.subject.read(self.run,require_avatar=True,require_framework=True);self.bound()
        need(type(source) is dict and set(source)=={'kind','value'}
            and source['kind'] in ('navigation','graphics','home'))
        need(self.intent(stage,deepcopy(value),deepcopy(source),control) is not False);self.bound()
        return value

    def authorized_url(self,url):
        need(type(url) is str and 0<len(url)<=2048 and all(32<=ord(c)<127 for c in url))
        parsed=urlsplit(url);parsed.port
        need(parsed.scheme in ('http','https','file','overte') and parsed.username is None and parsed.password is None
            and not parsed.fragment and (parsed.scheme=='file' or bool(parsed.hostname)))
        return self.allow_url(url) is True

    def _graphics_intent(self,stage,value,control):
        self.before('graphics-'+stage,control,dict(kind='graphics',value=value))

    def _home_intent(self,stage,value,control):
        self.before(stage,control,dict(kind='home',value=value))

    def address_visible(self):return self.ui.available('navigation.address',enabled=False)
    def tablet_visible(self):return self.ui.tablet_visible()

    def navigation_input(self,stage,control,action='activate',text=None,*,expected_text=None):
        value=self.ui.capture();row=self.ui.control(value,control)
        need(value['open'] and value['ready'] and row is not None)
        if control=='navigation.address' and action in ('replace','submit'):
            need(value.get('navigationAddressVersion')==1 and row['inputReady'] and row['focused'])
        self.before(stage,control,dict(kind='navigation',value=value))
        if expected_text is not None:need(self.authorized_url(expected_text))
        self.ui.io.navigation.input(control,action,text,token=row['token'],expected_address=expected_text);self.bound()

    def open_tablet(self):
        with self.operation():
            value=self.ui.capture()
            if value['open']:need(self.owned('tablet'));return
            self.before('tablet-open','tablet.open',dict(kind='navigation',value=value));self.mark('tablet',True)
            self.ui.open_tablet();self.bound()

    def home_page(self):
        with self.operation():
            need(self.owned('tablet') and self.tablet_visible())
            before=self.home.source.capture()
            need(before['tabletShown'])
            if not before['onHomeScreen']:
                value=self.ui.capture()
                known=any(self.ui.control(value,key,enabled=False) is not None for key in
                    ('graphics.page','graphics.settings-entry','settings.entry'))
                known=known or self.owned('address') and self.ui.control(value,'navigation.address',enabled=False) is not None
                need(known)
            result=self.home.ensure(self._home_intent);self.bound()
            need(result['onHomeScreen'])
            return result

    def find_entry(self,control):
        value=self.ui.capture()
        if self.ui.control(value,control) is not None:return
        pages=sorted((row['id'] for row in value['controls'] if row['id'].startswith('tablet.page.')),
            key=lambda name:int(name.rsplit('.',1)[1]))
        for page in pages:
            self.navigation_input('tablet-'+page,page)
            for attempt in range(7):
                value=self.ui.capture();self.bound()
                if self.ui.control(value,control) is not None:return
                if attempt<6:self.ui.sleep(.1)
        raise NativeUIError('Original VR tablet entry is unavailable')

    def open(self):
        with self.operation():
            self.open_tablet();value=self.graphics.capture()
            if self.graphics.row(value,'graphics.page') is None:
                if self.graphics.row(value,'graphics.settings-entry') is None:
                    self.home_page();self.find_entry('settings.entry')
                    value=self.graphics.capture();row=self.graphics.row(value,'settings.entry')
                    need(row is not None and row['inputReady'] and row['enabled'])
                    self.before('settings-open','settings.entry',dict(kind='graphics',value=value))
                    self.graphics.io.activate('settings.entry',token=row['token'])
                    self.graphics.wait(lambda v:self.graphics.row(v,'graphics.settings-entry') is not None);self.bound()
                value=self.graphics.capture();row=self.graphics.row(value,'graphics.settings-entry')
                need(row is not None and row['inputReady'] and row['enabled'])
                self.before('graphics-open','graphics.settings-entry',dict(kind='graphics',value=value))
                self.graphics.io.activate('graphics.settings-entry',token=row['token'])
                value=self.graphics.wait(lambda v:self.graphics.row(v,'graphics.page') is not None);self.bound()
            need(self.graphics.row(value,'graphics.page')['profile']=='generic-immediate-v1' and self.tablet_visible())
            return {'performed':True}

    def set_resolution(self,value):
        with self.operation():
            need(self.owned('tablet') and self.tablet_visible());self.graphics.set_resolution(value);self.bound()
            return {'performed':True}

    def toggle(self,control,enabled):
        with self.operation():
            need(self.owned('tablet') and self.tablet_visible());self.graphics.toggle(control,enabled);self.bound()
            return {'performed':True}

    def close_address(self):
        with self.operation():
            # A different owned page is closed by close_tablet's ordinary Home
            # ray. No address lease means this method has nothing to retire.
            if not self.address_visible() and not self.owned('address'):return
            if not self.tablet_visible():
                if not self.owned('address'):return
                need(self.owned('tablet'));self.open_tablet()
            if self.address_visible():
                need(self.owned('address'));self.home_page()
            need(not self.address_visible() and self.home.source.capture()['onHomeScreen'])
            if self.owned('address'):self.mark('address',False)

    def close_tablet(self):
        with self.operation():
            if not self.tablet_visible() and not self.home.source.capture()['onHomeScreen']:
                need(self.owned('tablet'));self.open_tablet()
            if self.tablet_visible():
                need(self.owned('tablet'))
                # Physical close alone retains generic Graphics/Go To objects.
                # Ordinary Home must precede it; backend retirement is observed
                # separately through the passive UI/HTTP/Web/scene sources.
                self.home_page()
                if self.owned('address'):self.mark('address',False)
                value=self.ui.capture();self.before('tablet-close','tablet.close',dict(kind='navigation',value=value))
                self.ui.io.tablet(False);self.ui.wait(lambda v:not v['open']);self.bound()
            need(not self.tablet_visible() and self.home.source.capture()['onHomeScreen'])
            if self.owned('tablet'):self.mark('tablet',False)
            need(not self.owned('menu'))
            return {'performed':True}

    def navigate(self,url):
        with self.operation():
            need(self.authorized_url(url));self.close_address();self.open_tablet();self.home_page()
            self.find_entry('navigation.goto')
            self.mark('address',True);self.navigation_input('address-open','navigation.goto')
            self.ui.wait(lambda v:self.ui.control(v,'navigation.address') is not None);self.bound()
            self.navigation_input('address-focus','navigation.address')
            self.ui.wait(lambda v:(self.ui.control(v,'navigation.address') or {}).get('inputReady') is True);self.bound()
            need(self.authorized_url(url));self.navigation_input('address-replace','navigation.address','replace',url)
            expected=hashlib.sha256(url.encode()).hexdigest()
            def actual_field(value):
                row=self.ui.control(value,'navigation.address')
                return value.get('navigationAddressVersion')==1 and row is not None and row['inputReady'] and row['focused'] \
                    and row['textLength']==len(url) and row['textSha256']==expected
            self.ui.wait(actual_field);self.bound();need(self.authorized_url(url))
            self.navigation_input('address-go','navigation.address','submit',expected_text=url)
            self.ui.wait(lambda v:self.ui.control(v,'navigation.address',enabled=False) is None);self.bound()
            need(self.home.source.capture()['onHomeScreen'])
            self.mark('address',False);self.close_tablet()
            return {'performed':True}

    def select_camera(self,mode):
        # Pico's controlled first-person preparation already establishes the
        # actual HMD camera mode. No product Camera setter or fictitious menu.
        # A different mode needs a future normal native View-menu operation.
        with self.operation():
            need(mode in ('first person','first person look at'))
            source=self.subject.read(self.run,require_avatar=True,require_framework=True);self.bound()
            need(source['source']['view']['mode']==mode)
            return {'performed':False}
