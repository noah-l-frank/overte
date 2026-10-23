"""One first-eight normal prefix; Qt/VM/GPU/OS/Account are explicit models.

Real HTTP/TLS, current Python transports, original Session callbacks, immutable
journals, PNGs, native-storage receipts and independent role readers execute.
Synthetic producer clocks are sampled only while constructing NEW originals;
no archived packet is retimed. This is not headset/image/peer qualification.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import shutil
import sys
import unittest
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.navigation_stereo import NavigationStereo
from adapters.navigation_arrival import stereo_frame
from adapters.navigation_transit import NavigationTransit
from adapters.pico4.normal_places import PicoPlacesIO
from adapters.pico4.navigation_transit_join import NavigationTransitJoin
from adapters.pico4.tablet_home import PicoTabletHome
from adapters.token_places_ui import TokenPlacesUI,sha
from adapters.token_script_ui import TokenScriptUI
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.fixtures import context
from feature_journeys.scenarios import SCENARIOS,expand
from feature_journeys.stereo_navigation_evidence import original_name
from navigation_observation import viewpoint_urls
from self_tests import test_pico_navigation_prefix as prefix
from self_tests import test_navigation_directory as directory
from self_tests.test_pico_tablet_home import original as home_original


def new_source_clock(value,epoch):
    """Explicit fresh synthetic producer, never called on retained originals."""
    for key,item in value.items():
        if key.endswith('EpochMs') and type(item) is int and item>0:value[key]=epoch
        elif type(item) is dict:new_source_clock(item,epoch)
        elif type(item) is list:
            for row in item:
                if type(row) is dict:new_source_clock(row,epoch)


class Model(prefix.Model):
    def __init__(self,root):
        super().__init__(root);self.shown=True;self.root_dead=False;self.ignore_arrival=False
        self.retain_root=False;self.controller_calls=[];self.lose_close=False;self.owner_test=None
    def raw(self):
        value=super().raw();value.update(open=self.shown,ready=self.shown)
        if self.loaded_row is not None:
            for control in value['controls']:
                if control['id']=='places.visit.'+sha(self.loaded_row['name']):control['addressSha256']=sha(self.loaded_row['address'])
        if not self.shown:value['controls']=[]
        return value
    def send(self,command):
        reply=super().send(command)
        if self.page and self.root_birth is None:self.root_birth=self.epoch()
        if command['controlId'].startswith('places.visit.') and not self.ignore_arrival and not self.ignore:
            self.owner_test.world.position='B'
        return reply
    def source_send(self,request):
        super().source_send(request);value=self.packet;value['navigationEnvironmentVersion']=2
        value['accountServer']=self.effective
        value['settings']=dict(navigationSettingsEntriesVersion=1,instance='a'*32,capturedEpochMs=self.epoch(),selectedPresent=self.present,
            selectedType='url' if self.present else 'absent',rawSettingsSha256='c'*64,otherSettingsSha256=self.other,handlesAbsent=True)
        value['ui'].update(open=self.shown,ready=self.shown)
    def source_read(self,request):
        directory.Model.source_read(self,request);value=self.source_packet;value['processId']=prefix.PID
        if self.root_birth is None:value['roots']=[]
        else:
            value['roots'][0].update(alive=not self.root_dead,current=self.page)
    def private(self,request,kind):
        super().private(request,kind);value=self.native_packets[kind]
        if kind=='panels':
            value['ui'].update(open=self.shown,ready=self.shown)
            value['roots']=[] if self.root_birth is None else [dict(rootId='e'*32,profile='pico-places-v1',sourceSha256='d'*64,
                firstObservedEpochMs=self.root_birth,alive=not self.root_dead,inCurrentTree=self.page,visible=self.page)]
        else:value['tabletOpen']=self.shown
    def consume_controller(self,envelope):
        command=envelope['commands'][0];operation=command['operation'];self.controller_calls.append(deepcopy(envelope))
        if operation=='input.primary':
            self.home_count+=1;self.login=False;self.focus=''
            if self.page:self.page=False;self.root_dead=not self.retain_root
            self.generation=str(uuid.uuid4())
        else:
            assert operation=='tablet.close';self.shown=False;self.generation=str(uuid.uuid4())
            if self.lose_close:raise NativeUIError('Synthetic applied controller close reply lost')


@unittest.skipUnless(shutil.which('openssl'),'Existing ephemeral TLS fixture requires OpenSSL')
class NavigationTransitPrefixTests(unittest.TestCase):
    model_type=Model
    setUpClass=classmethod(prefix.NavigationPrefixTests.setUpClass.__func__)
    tearDownClass=classmethod(prefix.NavigationPrefixTests.tearDownClass.__func__)
    setUp=prefix.NavigationPrefixTests.setUp
    activate=prefix.NavigationPrefixTests.activate
    write=prefix.NavigationPrefixTests.write
    read=prefix.NavigationPrefixTests.read
    installed=prefix.NavigationPrefixTests.installed

    def make(self,role):
        result=prefix.NavigationPrefixTests.make(self,role);m=self.model;w=self.world;m.owner_test=self
        w.binding=deepcopy(self.binding);w.lock=self.lock;w.sleep=m.sleep
        if not hasattr(w,'navigation_evidence_retained'):
            w.navigation_evidence_retained=True;w.temporary._finalizer.detach();w.close=lambda:None
            print('Retained original Navigation world-render fixture:',w.root,flush=True)
        original_write=w.ui.write
        # Installed once per fixture, not once per role/observer.
        if not hasattr(w,'navigation_ui_original'):
            w.navigation_ui_original=original_write
            def write(*args):
                w.ui.clock=m.clock;w.ui.epoch=m.epoch();w.ui.shown=m.shown;return w.navigation_ui_original(*args)
            w.ui.write=write
        def graphics():
            value=w.ui.source();value.clock_ms=m.epoch;value.monotonic=lambda:m.clock;value.sleep=m.sleep;return value
        gpu_mutate=w.gpu.camera_source
        def generated(value):gpu_mutate(value);new_source_clock(value,m.epoch())
        w.gpu.mutate=generated
        w.storage.mutate=lambda value:value.update(instance='a'*32,capturedEpochMs=m.epoch())
        original_send=w.inventory.send
        if not hasattr(w,'navigation_inventory_original'):
            w.navigation_inventory_original=original_send
            def inventory(request):w.inventory.epoch=m.epoch();return w.navigation_inventory_original(request)
            w.inventory.send=inventory
        feature_mutate=w.features.mutate
        if not hasattr(w,'navigation_features_original'):
            w.navigation_features_original=feature_mutate
            def feature(value):w.navigation_features_original(value);new_source_clock(value,m.epoch())
            w.features.mutate=feature
        def native():
            return NativeFeatureObservation(w.features.send,w.features.original,m.epoch,m.guard,prefix.PID,monotonic=lambda:m.clock,sleep=m.sleep)
        def capture():
            value=w._world_render_capture('owned',read_only=True,role='primary',require_frame_view=True,source_lock=self.lock)
            value.capture.clock_ms=value.storage.clock_ms=value.receipts.cleanup.clock_ms=m.epoch
            return value
        def factory(parent):
            images=self.root/'navigation-prefix-images';images.mkdir(mode=0o700,exist_ok=True)
            def stereo(ticket):
                return NavigationStereo(parent.source.arrival,capture,images/original_name(prefix.RUN,'primary',ticket),images,
                    prefix.RUN,self.binding,self.lock,m.guard,journal_id=ticket,ui_factory=graphics,native_factory=native,monotonic=lambda:m.clock)
            def home():
                self.home_sequence+=1
                return home_original()|dict(commandId=uuid.uuid4().hex,processId=prefix.PID,sourceSequence=self.home_sequence,
                    elapsedMs=100+round(m.clock*1000),capturedEpochMs=m.epoch(),tabletShown=m.shown,onHomeScreen=not m.login and not m.page)
            source=SimpleNamespace(pid=prefix.PID,capture=home,guard=m.guard,clock_ms=m.epoch,monotonic=lambda:m.clock,sleep=m.sleep)
            ui=lambda intent:TokenPlacesUI(PicoPlacesIO(parent.source.normal.io.original),intent,prefix.RUN,monotonic=lambda:m.clock,sleep=m.sleep)
            transit=NavigationTransit(ui,parent.source.arrival,parent.source.readers['directory'],parent.source.readers['bookmarks'],stereo,
                self.root/'navigation-prefix-transit.json',prefix.RUN,self.binding,directory.INPUTS['sceneUrl'],m.guard,directory=parent.directory,
                home=PicoTabletHome(source,lambda _pose:None),panels=parent.source.readers['panels'],monotonic=lambda:m.clock,sleep=m.sleep,
                defer_stereo_until_close=True)
            normal=TokenScriptUI(parent.source.normal.io.original,monotonic=lambda:m.clock,sleep=m.sleep)
            return NavigationTransitJoin(parent,transit,normal,graphics(),self.root/'navigation-prefix-transit-join.json')
        result.transit_factory=factory;return result

    def first_seven(self):
        self.flow.prepare()
        for verb in prefix.VERBS[:7]:self.flow.act(self.activate(verb))

    def test_actual_continuous_eight_steps_home_close_original_stereo_retirement_and_actor_sources(self):
        self.flow.prepare();self.flow.observe();actor=self.make('actor');actor.observe()
        for index,verb in enumerate(prefix.VERBS[:8]):
            self.flow.act(self.activate(verb));actual=self.flow.observe();peer=actor.observe()
            self.assertEqual(expand(SCENARIOS['world-navigation']['steps'][index]['state'],context(prefix.RUN)),actual['state'])
            self.assertEqual(actual['state'],peer['state'])
        owner=self.flow.transit();self.assertEqual('closed',owner.state['phase']);self.assertFalse(self.model.shown)
        self.assertEqual(['input.primary','input.primary','tablet.close'],[c['commands'][0]['operation'] for c in self.model.controller_calls])
        self.assertTrue(owner.transit.state['stereoDeferred']);self.assertIsNone(owner.transit.state['stereoSha256'])
        self.assertTrue(owner.transit.state['quiet']);self.assertTrue(owner.close_original().state['quiet'])
        stereo=owner.transit.stereo_factory(owner.state['ticket']);self.assertEqual('complete',stereo.state['phase'])
        frame=stereo.state['frame'];self.assertFalse(frame['uiBefore']['tabletShown']);self.assertFalse(frame['uiAfter']['tabletShown'])
        self.assertEqual('B',stereo_frame(frame,stereo.image_bytes(),prefix.RUN,self.binding,directory.INPUTS['sceneUrl'])['location'])
        self.assertFalse(stereo.state['proof']['memory']['present']);self.assertIsNone(self.world.owner_store('primary').read())
        self.assertEqual([],list(self.world.native_root.iterdir()));self.assertTrue(stereo.images.root.is_dir())
        self.assertFalse(actual['fullNavigationRecipe']);self.assertTrue(actual['journalsRetained'])

    def test_lost_applied_close_cold_reconciles_without_resending_home_close_or_capture(self):
        self.first_seven();call=self.activate('directory-select');self.model.lose_close=True
        with self.assertRaises(NativeUIError):self.flow.act(call)
        self.assertFalse(self.model.shown);self.assertEqual(3,len(self.model.controller_calls));self.assertFalse(self.world.gpu.commands)
        self.model.lose_close=False;self.flow=self.make('primary');self.flow.act(call)
        self.assertEqual(3,len(self.model.controller_calls));self.assertEqual(1,len(self.world.gpu.commands))
        self.assertEqual('B',self.flow.observe()['state']['location'])

    def test_phase_advance_in_last_close_guard_prevents_controller_toggle_and_capture(self):
        self.first_seven();call=self.activate('directory-select');guard=self.flow.source.guard;changed=[]
        def advance():
            owner=self.flow.transit_join
            if owner is not None and owner.state is not None and owner.state['phase']=='close-issued' and owner.close_owner is not None and owner.close_owner.state is not None and not changed:
                changed.append(True);self.activate('bookmark-add')
            return guard()
        self.flow.source.guard=advance
        with self.assertRaises(NativeUIError):self.flow.act(call)
        self.assertTrue(changed);self.assertEqual(2,len(self.model.controller_calls));self.assertTrue(self.model.shown)
        self.assertFalse(self.world.gpu.commands);self.assertEqual('close-issued',self.flow.transit_join.state['phase'])

    def test_retained_places_root_prevents_close_and_original_stereo_without_replaying_home(self):
        self.first_seven();call=self.activate('directory-select');self.model.retain_root=True
        with self.assertRaises(NativeUIError):self.flow.act(call)
        self.assertEqual(2,len(self.model.controller_calls));self.assertTrue(self.model.shown);self.assertFalse(self.world.gpu.commands)
        self.flow=self.make('primary')
        with self.assertRaises(NativeUIError):self.flow.act(call)
        self.assertEqual(2,len(self.model.controller_calls));self.assertTrue((self.root/'navigation-prefix-transit.json').exists())


if __name__=='__main__':unittest.main()
