"""Normal Pico browser-app/Home/script input; owner journals and effects are separate."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError
from adapters.phase_input_fence import PhaseInputFence
from adapters.pico4.browser_apps import PicoBrowserAppsIO,IDS
from adapters.pico4.normal_scripts import PicoScriptIO
from adapters.pico4.tablet_home import PicoTabletHome
from adapters.token_script_ui import TokenScriptUI

VERSION=1


class PicoBrowserScriptIO(PicoScriptIO):
    """Preserve the original actuator and add admission before each child intent."""
    def __init__(self,original,fence,begin,done):
        need(isinstance(original,PicoScriptIO) and isinstance(fence,PhaseInputFence) and callable(begin) and callable(done))
        super().__init__(original.navigation);self.fence,self.begin,self.done=fence,begin,done
        original.navigation.io.bind_before_send(fence.before_send)
        original.navigation.io.bind_controller_admission(fence.before_controller,intent=fence.stage_intent,before_publish=fence.before_publish)
    def execute(self,operation,control,action):
        self.begin(dict(kind='normal-ui',operation=operation,control=control))
        value=action();self.done();return value
    def activate(self,identifier,*,source=None):
        return self.execute('activate',identifier,lambda:super(PicoBrowserScriptIO,self).activate(identifier,source=source))
    def replace(self,identifier,text):
        return self.execute('replace',identifier,lambda:super(PicoBrowserScriptIO,self).replace(identifier,text))
    def submit(self,identifier):
        return self.execute('submit',identifier,lambda:super(PicoBrowserScriptIO,self).submit(identifier))
    def tablet(self,opened):
        need(type(opened) is bool)
        return self.execute('controller','tablet.open' if opened else 'tablet.close',lambda:super(PicoBrowserScriptIO,self).tablet(opened))
    def select_index(self,*_args,**_kwargs):
        raise NativeUIError('Browser normal Script input does not own a file picker')


class PicoBrowserEntry:
    def __init__(self,normal,apps,home,fence,begin,done,owns,lease):
        need(isinstance(normal,TokenScriptUI) and isinstance(normal.io,PicoBrowserScriptIO)
            and isinstance(apps,PicoBrowserAppsIO) and not apps.read_only and isinstance(home,PicoTabletHome)
            and isinstance(fence,PhaseInputFence) and all(callable(f) for f in (begin,done,owns,lease)))
        need(normal.io.navigation.process_id==apps.original.navigation.process_id==home.source.pid)
        self.normal,self.apps,self.home,self.fence=normal,apps,home,fence
        self.begin,self.done,self.owns,self.lease=begin,done,owns,lease
        apps.bind_input_fence(fence)

    def home_page(self):
        need(self.owns() is True and self.normal.tablet_visible());issued=False
        def intent(stage,original,control):
            nonlocal issued
            need(not issued);issued=True
            self.begin(dict(kind='home-ray',operation=stage,control=control,original=deepcopy(original)))
            self.fence.check()
        value=self.home.ensure(intent,stream_intent=self.fence.stage_intent,stream_publish=self.fence.before_publish)
        if issued:self.done()
        return value

    def activate(self,identifier,reference):
        self.begin(dict(kind='browser-app',operation='activate',control=identifier,original=deepcopy(reference)))
        self.apps.activate(identifier,reference=reference);self.done()

    def open(self,identifier,*,initial):
        need(identifier in IDS and type(initial) is bool)
        if initial:
            need(not self.owns() and not self.normal.tablet_visible())
            self.lease(True);self.normal.open_tablet()
        else:need(self.owns() is True and self.normal.tablet_visible())
        self.home_page();current=self.apps.capture()
        pages=sorted((row['id'] for row in current['controls'] if re.fullmatch(r'tablet\.page\.(?:[1-9]|[12][0-9]|3[0-2])',row['id'])),
            key=lambda key:int(key.rsplit('.',1)[1]))
        started=self.normal.now()
        for page in [None,*pages]:
            if page is not None:self.activate(page,self.apps.capture())
            until=self.normal.now()+.6
            for attempt in range(7):
                current=self.apps.capture();need(self.normal.now()-started<20)
                rows=[row for row in current['controls'] if row['id']==identifier and row['enabled'] and row['inputReady']]
                if rows:
                    need(len(rows)==1);self.activate(identifier,current);return
                if self.normal.now()>=until:break
                self.normal.sleep(.1)
        raise NativeUIError('Original normal Pico fixture app tile is unavailable')

    def close(self):
        if not self.owns():need(not self.normal.tablet_visible());return
        if self.normal.tablet_visible():
            self.home_page();self.normal.close_tablet();self.normal.wait_tablet_absent()
        self.lease(False)
