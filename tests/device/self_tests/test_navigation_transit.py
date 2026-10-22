"""Normal Pico Python input with synthetic widgets/native poses/stereo GPU/OS.

The original journals, image writer, native receipt files and protocol readers
run on the host. No compiled source, headset or physical input is executed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json
import sys
import uuid
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_location_bookmarks import NativeLocationBookmarks
from adapters.native_navigation_directory import NativeNavigationDirectory,joined_directory
from adapters.pico4.tablet_home import PicoTabletHome
from adapters.navigation_transit import NavigationTransit
from adapters.normal_ui import NativeUIError
from adapters.pico4.navigation import PicoNavigation
from adapters.pico4.normal_places import PicoPlacesIO,project
from adapters.token_places_ui import TokenPlacesUI,sha
from adapters.script_journey.history import unpack,pack
from feature_journeys.fixtures import context
from feature_journeys.navigation_fixture import DIRECTORY,QUERY
from navigation_observation import viewpoint_urls
from self_tests.test_navigation_arrival import Model as PoseModel,SCENE
from self_tests.test_navigation_directory import Model as DirectoryModel,INPUTS,PROFILE,ORIGIN,TICKET,RUN
from self_tests.test_native_navigation_panels import Boundary as PanelsBoundary
from self_tests.test_pico_tablet_home import original as home_original

SELECT='9'*32

class Widgets(DirectoryModel):
    @property
    def clock(self):return self.world.clock
    @clock.setter
    def clock(self,value):self.world.clock=value
    def __init__(self,world):
        self.world=world;super().__init__(world.root)
        self.retained_root=False;self.skip_arrival=False;self.lost=None;self.omit_row=False;self.home_ignored=False
        self.root_dead=False;self.scrolling=False;self.scroll_ignored=False;self.scroll_token=str(uuid.uuid4())
        self.map[context(RUN)['renamed']]=viewpoint_urls(SCENE)['A'];self.persist()
        self.query=context(RUN)['name']
        with self.provider.response(DIRECTORY,QUERY) as response:_,body,header=response
        self.received(body,header)
    def native_send(self,c):super().native_send(c);self.native_packet['processId']=31
    def bookmarks(self):
        return NativeLocationBookmarks(self.native_send,lambda:json.dumps(self.native_packet),self.epoch,self.guard,31,
            monotonic=lambda:self.clock,sleep=self.sleep)
    def source_read(self,c):
        super().source_read(c);self.source_packet['processId']=31
        self.source_packet['roots'][0].update(alive=not self.root_dead,current=self.page)
    def reader(self):
        return NativeNavigationDirectory(self.source_read,lambda:json.dumps(self.source_packet),self.epoch,self.guard,31,
            monotonic=lambda:self.clock,sleep=self.sleep)
    def raw(self):
        value=super().raw();value['processId']=31
        for row in value['controls']:
            if row['id'].startswith('places.visit.'):row['addressSha256']=sha(viewpoint_urls(SCENE)['B'])
        if self.scrolling and self.page:
            area='directory' if self.tab==0 else 'bookmarks'
            value['controls'].append(dict(id='places.scroll.'+area,token=self.scroll_token,enabled=True,focused=False,
                inputReady=True,position=self.position,size=.2))
        if self.omit_row or self.scrolling and self.position<.5:value['controls']=[r for r in value['controls'] if not r['id'].startswith(('places.visit.','places.bookmark.visit.'))]
        return value
    def send(self,c):
        reply,epoch=super().send(c);reply['processId']=31
        if not self.ignore and not self.ignore_effect:
            if c['action']=='scroll' and not self.scroll_ignored:
                self.position=0. if c['direction']=='up' else .5
            if c['controlId'].startswith(('places.visit.','places.bookmark.visit.')) and not self.skip_arrival:
                self.world.position='B' if c['controlId'].startswith('places.visit.') else 'A'
            elif c['controlId']=='tablet.home' and not self.home_ignored:
                self.page=False;self.root_dead=not self.retained_root
        if c['controlId']==self.lost:raise NativeUIError('Synthetic lost applied input result')
        return reply,epoch

class RayBoundary:
    """Synthetic entity input, distinct from the original Qt command counter."""
    def __init__(self,test):
        self.test=test;self.widgets=test.widgets;self.world=test.world;self.gestures=[]
        self.on_home=False;self.ignore=False;self.lose=False;self.home_edit=None;self.extra_roots=[]
        self.home_sequence=0;self.panel_boundary=PanelsBoundary();self.panel_edit=None
        self.source=SimpleNamespace(pid=31,clock_ms=self.world.epoch,monotonic=lambda:self.world.clock,
            sleep=self.world.sleep,guard=self.world.guard,capture=self.capture)
        self.home=PicoTabletHome(self.source,self.stage)
    def capture(self):
        self.home_sequence+=1
        value=home_original()|dict(commandId=uuid.uuid4().hex,processId=31,sourceSequence=self.home_sequence,
            elapsedMs=100+round(self.world.clock*1000),capturedEpochMs=self.world.epoch(),onHomeScreen=self.on_home)
        if self.home_edit:self.home_edit(value)
        return value
    def stage(self,pose):
        disk=json.loads(self.test.path.read_text());state=unpack(disk['payload'])[0]
        self.test.assertTrue(state['pending']['home']);self.test.assertIsNotNone(state['homeBefore'])
        self.test.assertIsNone(state['homeAfter']);self.gestures.append(deepcopy(pose))
        if not self.ignore:
            self.on_home=True;self.widgets.page=False;self.widgets.root_dead=not self.widgets.retained_root
        if self.lose:raise NativeUIError('Synthetic lost applied OpenXR Home result')
    def panels(self):
        boundary=self.panel_boundary;widgets=self.widgets
        def send(request):
            boundary.clock=self.world.clock;boundary.input_sequence=widgets.sequence
            boundary.bridge=widgets.bridge;boundary.generation=widgets.generation
            boundary.rows=[dict(rootId='e'*32,profile='pico-places-v1',sourceSha256='d'*64,firstObservedEpochMs=20000,
                alive=not widgets.root_dead,inCurrentTree=widgets.page,visible=widgets.page)]+deepcopy(self.extra_roots)
            boundary.edit=self.panel_edit;boundary.send(request)
        return type(boundary.reader())(send,lambda:json.dumps(boundary.packet),self.world.epoch,self.world.guard,31,
            monotonic=lambda:self.world.clock,sleep=self.world.sleep)

class NavigationTransitTests(unittest.TestCase):
    def setUp(self):
        self.world=PoseModel(run=RUN);self.addCleanup(self.world.close);self.widgets=Widgets(self.world)
        self.world.binding.update(sessionId=self.widgets.bridge)
        self.world.position='B'
        self.navigation=PicoNavigation(self.widgets,self.world.root/'navigation-ui.json',
            dict(schemaVersion=1,sourceRevision='a'*40,artifactSha256='b'*64,installedCandidateVerified=True),
            '31:synthetic-start',SCENE,monotonic=lambda:self.world.clock,sleep=self.world.sleep)
        self.original=SimpleNamespace(capture=self.navigation.snapshot,navigation=self.navigation)
        self.path=self.world.root/'transit.json';self.witnesses=0
    def witness(self,ticket):
        self.witnesses+=1;self.widgets.provider.activate(RUN,ticket)
        ui=project(self.navigation.snapshot());native=self.widgets.reader().read(RUN)
        joined_directory(native,ui,self.widgets.provider.snapshot(RUN),run=RUN,ticket=ticket,after_epoch=20000,
            owned_origin=ORIGIN,provider_instance=self.widgets.provider.instance,provider_inputs=INPUTS,
            source_profile=PROFILE,receipt_ticket=TICKET)
        return dict(ui=ui,native=native)
    def owner(self):
        return NavigationTransit(lambda intent:TokenPlacesUI(PicoPlacesIO(self.original),intent,RUN,
            monotonic=lambda:self.world.clock,sleep=self.world.sleep),self.world.arrival(),self.widgets.reader(),self.widgets.bookmarks(),
            lambda ticket:self.world.stereo(self.world.root/('navigation-stereo-'+ticket+'.json')),
            self.path,RUN,self.world.binding,SCENE,self.world.guard,directory=SimpleNamespace(observe_current=self.witness),
            monotonic=lambda:self.world.clock,sleep=self.world.sleep)
    def act(self,kind='bookmark'):return self.owner().act(SELECT,kind)
    def test_normal_bookmark_selection_native_arrival_stereo_home_and_true_quiet_survive_recreation(self):
        original=self.widgets.storage();self.assertEqual(dict(performed=True),self.act())
        state=self.owner().state
        self.assertEqual(['places.tab.1','places.bookmark.visit.'+sha(context(RUN)['renamed']),'tablet.home'],[c['controlId'] for c in self.widgets.calls])
        self.assertEqual(7,len(state['quiet']));self.assertEqual(original,self.widgets.storage())
        self.assertFalse(state['last']['roots']['roots'][0]['alive']);self.assertEqual('A',self.world.position)
        self.assertIsNone(self.world.owner_store('primary').read());self.assertFalse(list(self.world.native_root.iterdir()))
        count=len(self.widgets.calls);captures=len(self.world.gpu.commands);self.act()
        self.assertEqual(count,len(self.widgets.calls));self.assertEqual(captures,len(self.world.gpu.commands))
    def test_directory_selection_requires_original_consumption_join_before_normal_input(self):
        self.world.position='A';self.act('directory')
        self.assertEqual(1,self.witnesses);self.assertEqual('B',self.world.position)
        self.assertEqual(['places.visit.'+sha(context(RUN)['name']),'tablet.home'],[c['controlId'] for c in self.widgets.calls])
    def test_lost_tab_visit_and_home_results_are_observed_without_resending(self):
        for control in ('places.tab.1','places.bookmark.visit.'+sha(context(RUN)['renamed']),'tablet.home'):
            self.setUp();self.widgets.lost=control
            with self.subTest(control=control),self.assertRaises(NativeUIError):self.act()
            self.assertIsNotNone(self.owner().state['pending']);count=len(self.widgets.calls)
            self.widgets.lost=None;self.act();self.assertGreaterEqual(len(self.widgets.calls),count)
            self.assertEqual(1,sum(c['controlId']==control for c in self.widgets.calls))
    def test_ignored_consumed_selection_or_home_and_live_original_root_never_pass(self):
        for fault in ('skip_arrival','home_ignored','retained_root'):
            self.setUp();setattr(self.widgets,fault,True)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.act()
            count=len(self.widgets.calls)
            with self.assertRaises(NativeUIError):self.act()
            self.assertEqual(count,len(self.widgets.calls));self.assertFalse(self.world.gpu.commands)
    def test_preexisting_destination_missing_row_wrong_row_or_missing_consumption_cannot_pass(self):
        for fault in ('already','missing','wrong','read'):
            self.setUp()
            if fault=='already':self.world.position='A'
            elif fault=='missing':self.widgets.omit_row=True
            elif fault=='wrong':
                self.widgets.map[context(RUN)['renamed']]=viewpoint_urls(SCENE)['B'];self.widgets.persist()
            else:self.world.position='A';self.widgets.reads=[];self.widgets.messages=[];self.widgets.revision=0;self.widgets.last_message=None;self.widgets.records_hash=None
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.act('directory' if fault=='read' else 'bookmark')
            self.assertFalse(any('.visit.' in c['controlId'] for c in self.widgets.calls))
    def test_foreign_input_clock_unowned_bookmark_or_native_source_changes_interrupt_quiet(self):
        for fault in ('input','clock','bookmarks','native'):
            self.setUp();sleep=self.world.sleep
            def changed(seconds):
                sleep(seconds)
                if fault=='input':self.widgets.sequence+=1
                elif fault=='clock':self.widgets.edit=lambda v:v.update(elapsedMs=100)
                elif fault=='bookmarks':self.widgets.map['Foreign']='hifi://foreign.invalid';self.widgets.persist()
                else:self.world.subject.edit=lambda v:v.update(instance='8'*32)
            self.world.sleep=changed
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.act()
            self.assertEqual(0,len(self.owner().state['quiet']))
    def test_normal_scroll_reveals_owned_row_and_lost_scroll_does_not_resend(self):
        self.widgets.scrolling=True;self.widgets.position=.4;self.widgets.lost='places.scroll.bookmarks'
        with self.assertRaises(NativeUIError):self.act()
        self.assertEqual(0.,self.widgets.position);self.widgets.lost=None;self.act()
        scrolls=[c for c in self.widgets.calls if c['action']=='scroll']
        self.assertEqual(['up','down'],[c['direction'] for c in scrolls])
        self.assertEqual(2,self.owner().state['scrolls'])
    def test_ignored_scroll_and_changed_dialog_maturity_or_ui_generation_stop_before_visit(self):
        for fault in ('scroll','dialog','maturity','generation'):
            self.setUp()
            if fault=='scroll':self.widgets.scrolling=True;self.widgets.position=.4;self.widgets.scroll_ignored=True
            else:
                send=self.widgets.send
                def changed(c):
                    result=send(c)
                    if c['controlId']=='places.tab.1':
                        if fault=='dialog':self.widgets.dialog=True
                        elif fault=='generation':self.widgets.generation=str(uuid.uuid4())
                        else:
                            def edit(v):
                                for r in v['controls']:
                                    if r['id']=='places.page':r['maturity']=['everyone','teen']
                            self.widgets.edit=edit
                    return result
                self.widgets.send=changed
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.act()
            self.assertFalse(any('.visit.' in c['controlId'] for c in self.widgets.calls))
    def test_actual_private_factories_share_original_arrival_source_and_existing_world_lock(self):
        root=Path(__file__).resolve().parents[3]
        sys.path.insert(0,str(root/'android/vr/pico/tests/device'))
        import test_native_execution_binding as native_fixture
        fixture=native_fixture.NativeExecutionBindingTest();fixture.setUp();self.addCleanup(fixture.doCleanups)
        adapter=fixture.instance();adapter._scripts=lambda target:SimpleNamespace(ui=SimpleNamespace(io=self.original),binding=self.world.binding)
        adapter._native_feature_observer=lambda target:SimpleNamespace(clock_ms=self.world.epoch,guard=self.world.guard,pid=31,
            monotonic=lambda:self.world.clock,sleep=self.world.sleep)
        def probe(target,package,after):
            self.assertEqual(('owned','org.overte.pico'),(target,package));return self.world.probe(after)
        adapter.read_probe_snapshot=probe
        adapter._graphics_subject_observer=lambda target:self.world.subject_reader()
        adapter._navigation_directory_source=lambda target:self.widgets.reader()
        adapter._location_bookmarks=lambda target:self.widgets.bookmarks()
        ray=RayBoundary(self);adapter._navigation_panels=lambda target:ray.panels()
        adapter._world_render_capture=self.world._world_render_capture
        def lock(_self,target,provided=None):
            self.assertEqual('owned',target);self.assertIs(self.world.lock,provided);return provided
        with patch('adapters.pico4.graphics_binding.PicoGraphicsBinding._lock',lock), \
                patch('adapters.pico4.tablet_home.bind_home',return_value=ray.home):
            owner=adapter._navigation_transit('owned',self.path,self.world.artifacts,RUN,SCENE,source_lock=self.world.lock)
            with self.assertRaises(NativeUIError):owner.act(SELECT,'bookmark')
            self.assertFalse(self.widgets.calls)
            with self.world.lock.held():self.assertEqual(dict(performed=True),owner.act(SELECT,'bookmark'))
        self.assertEqual(1,len(self.world.gpu.commands));self.assertIsNone(self.world.owner_store('primary').read())
        self.assertEqual(1,len(ray.gestures));self.assertNotIn('tablet.home',[c['controlId'] for c in self.widgets.calls])

    def test_changed_original_image_refuses_completed_transit_without_new_input_or_capture(self):
        self.act();stereo=self.world.stereo(self.world.root/('navigation-stereo-'+SELECT+'.json'))
        path=self.world.artifacts/stereo.state['image']['name'];path.write_bytes(path.read_bytes()[:-1])
        count=len(self.widgets.calls);captures=len(self.world.gpu.commands)
        with self.assertRaises(NativeUIError):self.owner()
        self.assertEqual(count,len(self.widgets.calls));self.assertEqual(captures,len(self.world.gpu.commands))

    def test_altered_journal_intent_never_causes_another_input(self):
        self.widgets.lost='places.tab.1'
        with self.assertRaises(NativeUIError):self.act()
        disk=json.loads(self.path.read_text());state=unpack(disk['payload'])[0]
        state['pending']['input']['controlId']='tablet.home';disk['payload']=pack([state])
        self.path.write_text(json.dumps(disk));self.path.chmod(0o600)
        with self.assertRaises(NativeUIError):self.owner()
        self.assertEqual(1,len(self.widgets.calls))

if __name__=='__main__':unittest.main()
