"""Same continuous normal15 scene owner and canonical G1/Origin3 source join.

Qt/OS/tracking/GPU are explicit existing native boundary models. The static
fixture is content-only; no Overte Domain, device, build or compiler runs.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import partial
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch
import uuid

from adapters.native_navigation_environment import NativeNavigationEnvironment
from adapters.native_graphics_subject import NativeGraphicsSubject
from adapters.native_navigation_directory import NativeNavigationDirectory
from adapters.native_navigation_replies import NativeNavigationReplies
from adapters.pico4.navigation_originals import read_original
from adapters.pico4.navigation_scene_generation import NavigationSceneGeneration
from adapters.script_journey.history import same
from navigation_observation import viewpoint_urls
from self_tests import test_pico_navigation_scene_prefix as scene
from self_tests import test_pico_navigation_generation_prefix as generation
from self_tests import test_pico_navigation_generation_frames as frames
from self_tests import test_pico_navigation_generation_restoration as restoration


class Model(scene.Model,restoration.Model):
    def send(self,command):
        if command=={}:return restoration.Model.send(self,command)
        return super().send(command)


class NavigationSceneGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):generation.NavigationGenerationPrefixTests.setUpClass()
    @classmethod
    def tearDownClass(cls):generation.NavigationGenerationPrefixTests.tearDownClass()
    def setUp(self):
        root=Path(__file__).resolve().parents[1]/'fixture';sys.path.insert(0,str(root))
        from fixture.serve import FixtureServer,FixtureHandler
        manifest=json.loads((root/'fixture-manifest.json').read_text())
        self.foundation=FixtureServer(('127.0.0.1',0),partial(FixtureHandler,directory=str(root)),manifest)
        self.thread=threading.Thread(target=self.foundation.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.foundation.server_close);self.addCleanup(self.thread.join,2);self.addCleanup(self.foundation.shutdown)
        self.scene=scene.NavigationScenePrefixTests();self.scene.fixture_type=generation.NavigationGenerationPrefixTests;self.scene.model_type=Model
        self.scene.use_probe_sdk=True
        self.scene.original_scene_url=self.foundation.public_origin+'/scene.json'
        self.scene.setUp();self.addCleanup(self.scene.doCleanups);self.f=f=self.scene.f;self.owner=self.scene.owner
        launch=f.launch_receiver
        def receiver():
            with patch.object(generation,'Model',Model):launch()
            f.new_model.scene_url=self.scene.inputs['sceneUrl']
            f.new_world.probe_edit=lambda value:value['nativeMotion'].update(processId=32)
            self.scene.bind_world(f.new_world,self.scene.inputs['sceneUrl'])
            # Startup consumes the actual preceding backing state in the
            # existing launcher model. Its real HTTP scene load supplies the
            # new process's original document, never the expected recipe state.
            prior_world=f.world;f.world=f.new_world
            try:f.new_model.fetch_scene(f.new_world.current_scene_url)
            finally:f.world=prior_world
            self.scene.install_scene_renderer(f.new_world,f.new_model)
        f.launch_receiver=receiver
        def first_eleven():
            self.scene.run_eleven(stereo=getattr(self,'include_stereo',True))
            f.original_parent=self.owner.parents['primary'];f.original_actor=self.owner.parents['actor'];f.original_model=f.model
            f.original_prefix=f.original_parent.store.path.read_bytes()
            f.original_ui=read_original(f.original_parent.source.normal.io.original.navigation.path)
            transit=f.original_parent.transit()
            f.original_native=transit.transit.stereo_factory(transit.state['ticket']).native_factory()
            f.running=True;f.sdk_calls=[];f.new_model=None;f.current_identity=f.binding['processIdentity'];f.scope_configuration=('owned-layer',f.root)
        f.first_eleven=first_eleven
    def prepare(self):
        self.g=frames.NavigationGenerationFramesTests();self.g.f=self.f;self.addCleanup(self.g.doCleanups)
        original_compose=frames.compose
        def composed(adapter,target,parent):
            from self_tests.pico_navigation_probe_fixture import install_sdk
            install_sdk(self,adapter,self.f.world,self.f.model)
            self.fresh_readers(adapter);return original_compose(adapter,target,parent)
        with patch.object(frames,'compose',side_effect=composed):self.g.prepare()
        f=self.f;m=f.model
        read=f.adapter.adb.read_debug_app_file
        def observed_home(target,package,path,**options):
            raw=read(target,package,path,**options)
            if path.endswith('tablet-home-observation.json'):
                # Extend this explicit native producer for the newly modeled
                # ordinary Go To page. It reports the actually consumed Qt
                # editor state, rather than assuming every non-Login page is Home.
                value=json.loads(raw);value['onHomeScreen']=not (m.login or m.page or m.editor)
                return json.dumps(value)
            return raw
        f.adapter.adb.read_debug_app_file=observed_home
        # A new original environment reader belongs to each cleanup owner.
        f.adapter._navigation_environment=lambda _target:NativeNavigationEnvironment(m.source_send,lambda:json.dumps(m.packet),
            m.epoch,m.guard,32,monotonic=lambda:m.clock,sleep=m.sleep)
        self.owner_generation=NavigationSceneGeneration(self.owner,f.flow,f.actor)
        return self.owner_generation
    def fresh_readers(self,adapter):
        f=self.f;m=f.model;w=f.world
        adapter._location_bookmarks=lambda _target:m.bookmarks()
        adapter._navigation_panels=lambda _target:m.reader_for('panels')
        adapter._navigation_modals=lambda _target:m.reader_for('modals')
        adapter._navigation_environment=lambda _target:NativeNavigationEnvironment(m.source_send,lambda:json.dumps(m.packet),m.epoch,m.guard,32,
            monotonic=lambda:m.clock,sleep=m.sleep)
        adapter._navigation_directory_source=lambda _target:NativeNavigationDirectory(m.source_read,lambda:json.dumps(m.source_packet),m.epoch,m.guard,32,
            monotonic=lambda:m.clock,sleep=m.sleep)
        adapter._navigation_replies=lambda _target:NativeNavigationReplies(m.modal.replies.send,m.modal.replies.original,m.epoch,m.guard,32,
            monotonic=lambda:m.clock,sleep=m.sleep)
        def subject(_target):
            def send(request):w.update_subject();w.subject.send(request)
            return NativeGraphicsSubject(send,w.subject.original,m.epoch,m.guard,32,require_framework=True,monotonic=lambda:m.clock,sleep=m.sleep)
        adapter._graphics_subject_observer=subject
    def test_same_original_user_c_lease_fifteen_actions_g1_stereo_and_typed_directory_restore(self):
        owner=self.prepare();f=self.f;lease=self.owner.lease()
        self.assertNotEqual(lease['originalSceneUrl'],self.scene.inputs['sceneUrl'])
        self.assertEqual(viewpoint_urls(self.scene.original_scene_url)['C'],lease['originalUrl'])
        first=owner.frames('primary',0);second=owner.frames('actor',0)
        self.assertNotEqual(first['journalId'],second['journalId']);self.g.preserved()
        with f.lock.held():
            left=f.flow.generation_owner.source();right=f.actor.generation_owner.source()
            self.assertIsNot(left,right)
            for key in left.readers:self.assertIsNot(left.readers[key],right.readers[key])
        old_files=[read_original(row['path']) for row in self.g.originals]
        ticket=uuid.uuid4().hex;f.server.journal.activate(generation.prefix.RUN,ticket,'cleanup',{});f.model.provider.activate(generation.prefix.RUN,ticket)
        owner.restore_directory(dict(contractVersion=generation.CONTRACT_VERSION,runId=generation.prefix.RUN))
        actual=f.flow.generation_owner.restoration_owner
        self.assertEqual(2,actual.disk['navigationGenerationRestorationVersion']);self.assertEqual('complete',actual.state['phase'])
        self.assertTrue(actual.state['nativeOriginals']);self.assertTrue(all('reference' in row and 'raw' not in row for row in actual.state['nativeOriginals']))
        self.assertTrue(all(type(actual.native_literal(row)) is str for row in actual.state['nativeOriginals']))
        self.assertEqual(lease['environment']['selectedServer'],f.model.selected)
        self.assertEqual(old_files,[read_original(row['path']) for row in self.g.originals])
        self.assertEqual(self.owner.started+120,self.owner.deadline)
        report=owner.report();self.assertFalse(report['fullNavigationRecipe']);self.assertTrue(report['originalUserWorldRestorationPending'])
        self.assertTrue(report['roleRetirementPending']);self.assertTrue(report['hostRetirementPending'])
        self.assertLessEqual(self.owner.bill()['parts'],512)
    def test_original_c_restoration_component_after_same_normal_fifteen_actions_without_stereo_qualification(self):
        # A component test, explicitly excluding the six enclosing scene-proof
        # captures and G1 acquisitions. It supplies no whole-flow qualification.
        self.include_stereo=False;owner=self.prepare();f=self.f
        self.assertEqual([],self.owner.state['scenes']);self.g.preserved()
        originals=[read_original(row['path']) for row in self.g.originals];sdk=deepcopy(f.sdk_calls)
        ticket=uuid.uuid4().hex
        f.server.journal.activate(generation.prefix.RUN,ticket,'cleanup',{});f.model.provider.activate(generation.prefix.RUN,ticket)
        call=dict(contractVersion=generation.CONTRACT_VERSION,runId=generation.prefix.RUN)
        owner.restore_directory(call);directory=f.flow.generation_owner.restoration_owner
        self.assertEqual('complete',directory.state['phase'])
        result=owner.restore_world(call);world=owner.user_world
        self.assertTrue(result['originalWorldRestored']);self.assertFalse(result['fullNavigationRecipe'])
        self.assertEqual(self.owner.lease()['originalUrl'],f.world.current_scene_url)
        self.assertEqual('complete',world.state['phase']);self.assertGreaterEqual(len(world.state['quiet']),3)
        self.assertFalse(f.model.shown);self.assertFalse(f.model.editor)
        self.assertEqual(originals,[read_original(row['path']) for row in self.g.originals])
        self.assertEqual(f.original_prefix,f.original_parent.store.path.read_bytes())
        self.assertEqual(f.original_ui,read_original(f.original_parent.source.normal.io.original.navigation.path))
        self.assertEqual(sdk,f.sdk_calls)
        self.assertEqual(self.owner.started+120,self.owner.deadline)
        self.assertLessEqual(self.owner.bill()['parts'],512)
        report=owner.report();self.assertTrue(report['roleRetirementPending']);self.assertTrue(report['hostRetirementPending'])


if __name__=='__main__':unittest.main()
