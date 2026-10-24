"""Actual normal World path and original two-eye source ownership (host seams)."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from contextlib import contextmanager
from adapters.normal_ui import NativeUIError

from adapters.pico4.world_web_stereo_join import WorldStereoJoin
from self_tests import test_pico_world_web_normal_close as existing
from self_tests.pico_world_web_render_fixture import WorldRenderModel
from self_tests import test_pico_world_web_source_process as process_existing
from self_tests.pico_world_web_process_fixture import WorldProductSources
from copy import deepcopy
import uuid
from adapters.pico4.world_web_source_pass import WorldSourceReturn
from adapters.pico4.world_web_stereo_join import original_join


class WorldWebStereoJoinTests(unittest.TestCase):
    run=existing.WorldWebNormalCloseTests.run
    stop=existing.WorldWebNormalCloseTests.stop
    activate=existing.WorldWebNormalCloseTests.activate
    call=existing.WorldWebNormalCloseTests.call
    baseline=existing.WorldWebNormalCloseTests.baseline
    prefix=existing.WorldWebNormalCloseTests.prefix
    cleanup_call=existing.WorldWebNormalCloseTests.cleanup_call
    def setUp(self):
        existing.WorldWebNormalCloseTests.setUp(self);self.artifacts=self.root/'world-artifacts';self.artifacts.mkdir(mode=0o700)
        self.model=WorldRenderModel(self.target,self.artifacts)
        print('Retained analytical World renderer:',self.model.root,flush=True)
        sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'android/vr/pico/tests/device'))
        import test_native_execution_binding as original
        fixture=original.NativeExecutionBindingTest();fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.model.bind_factory(fixture.instance())
        # The native-factory fixture deliberately defaults these gates off.
        # This independently configured normal-World test enables only its
        # own already-authorized test gates after that fixture is installed.
        gates=patch.dict('os.environ',dict(OVERTE_PICO_NORMAL_SCRIPTS='1',OVERTE_ANDROID_E2E_DEBUG='1',
            OVERTE_PICO_OPENXR_INPUT='1',OVERTE_E2E_SCENE_URL=self.target.scene_url))
        gates.start();self.addCleanup(gates.stop)
    def test_normal_open_and_both_source_roles_join_existing_original_world_stereo(self):
        self.baseline();self.primary.act(self.call(0))
        for flow in (self.primary,self.actor):
            join=WorldStereoJoin(flow,str(self.artifacts));row=join.capture()
            self.assertEqual('ready',join.state['phase']);self.assertIsNone(join.state['active'])
            self.assertTrue((self.artifacts/row['metadata']['name']).is_file());self.assertTrue((self.artifacts/row['png']['name']).is_file())
            self.assertEqual('world',join.owner.surface);self.assertEqual('complete',join.owner.state['phase'])
            self.assertLess(row['before']['sequence'],row['after']['sequence'])
        self.assertEqual(2,len(self.model.gpu.commands));self.assertEqual([],list(self.model.native_root.iterdir()))
        self.assertIsNone(self.model.owner_store('primary').read());self.assertIsNone(self.model.owner_store('actor').read())

    def test_original_mono_frame_cannot_be_relabelled_or_reacquired_after_capture(self):
        self.baseline();self.primary.act(self.call(0));join=WorldStereoJoin(self.primary,str(self.artifacts))
        mutate=self.model.gpu.mutate
        def mono(value):mutate(value);value['source']['view']='main-mono'
        self.model.gpu.mutate=mono
        with self.assertRaises(NativeUIError):join.capture()
        count=len(self.model.gpu.commands);self.assertEqual(1,count);self.assertTrue(join.failed)
        with self.assertRaises(NativeUIError):join.capture()
        self.assertEqual(count,len(self.model.gpu.commands));self.assertIsNotNone(self.model.owner_store('primary').read())
        normal=deepcopy(self.target.normal_inputs)
        with self.assertRaises(NativeUIError):self.primary.act(self.call(1))
        self.assertEqual(normal,self.target.normal_inputs)

    def test_actual_tablet_visibility_cannot_be_hidden_by_world_render_fixture_default(self):
        self.baseline();self.primary.act(self.call(0));join=WorldStereoJoin(self.primary,str(self.artifacts))
        # Independent analytic Qt producer changes, rather than an expected
        # source packet or a new ordinary-input path.
        self.target.qt.opened=True
        with self.assertRaises(NativeUIError):join.capture()
        self.assertTrue(self.model.ui.sample['tabletShown']);self.assertTrue(join.failed)
        self.assertTrue(join.store.path.exists());self.assertIsNotNone(self.model.owner_store('primary').read())

    def test_mutated_warm_scope_is_refused_before_original_capture(self):
        self.baseline();self.primary.act(self.call(0));join=WorldStereoJoin(self.primary,str(self.artifacts))
        join.scope['ownerToken']=uuid.uuid4().hex
        with self.assertRaises(NativeUIError):join.capture()
        self.assertEqual([],self.model.gpu.commands)

    def test_ready_sidecar_real_outer_exit_cannot_hide_native_age_with_frozen_host(self):
        self.baseline();self.primary.act(self.call(0));join=WorldStereoJoin(self.primary,str(self.artifacts));held=self.target.lock.held;exits=[]
        @contextmanager
        def release():
            with held():yield
            if self.target.lock._owner is None and join.state is not None and join.state['phase']=='ready' and not exits:
                exits.append(True);self.clock.base+=2000
        with patch.object(self.target.lock,'held',side_effect=release):
            with self.assertRaises(NativeUIError):join.capture()
        self.assertEqual([True],exits);self.assertTrue(join.failed);self.assertTrue(self.primary.failed)
        self.assertEqual('ready',join.store.read()['payload']['phase']);self.assertEqual(1,len(self.model.gpu.commands))



class WorldWebStereoProcessTests(unittest.TestCase):
    run=WorldWebStereoJoinTests.run
    stop=WorldWebStereoJoinTests.stop
    activate=WorldWebStereoJoinTests.activate
    call=WorldWebStereoJoinTests.call
    cleanup_call=WorldWebStereoJoinTests.cleanup_call
    launch=process_existing.WorldWebSourceProcessTests.launch
    receive=process_existing.WorldWebSourceProcessTests.receive
    command=process_existing.WorldWebSourceProcessTests.command
    close_worker=process_existing.WorldWebSourceProcessTests.close_worker
    def setUp(self):
        WorldWebStereoJoinTests.setUp(self);self.sources=WorldProductSources(self,self.model);self.addCleanup(self.sources.close)
        self.request=uuid.uuid4().hex;self.marker=uuid.uuid4().hex;self.worker=None;self.process=None;self.addCleanup(self.close_worker)
    def original_pass(self):
        self.primary.prepare();self.primary.observe();self.launch(stereo=True);self.command('publish','publication')
        primary=WorldStereoJoin(self.primary,str(self.artifacts));actor_scope=None
        for index in range(14):
            self.primary.act(self.call(index));sample=self.primary.observe();peer=self.command('publish','publication')['sample']
            self.assertEqual(sample['state'],peer['state'])
            if index in (0,13):
                self.receive('publication');row=self.receive('stereo')['original']
                self.assertTrue((self.artifacts/row['png']['name']).is_file());primary.capture(sample)
        self.primary.normal_close(self.cleanup_call());self.primary.observe();self.command('publish','publication');self.receive('exported')
        sidecar=self.target.feature_root/'pico-world-web-actor-stereo.json'
        from adapters.normal_feature_state import PrivateFeatureState
        actor_scope=PrivateFeatureState(sidecar).read()['scope']
        expected=dict(runId=self.run,fixtureUrl=self.fixture_url,foreignFixtureUrl=self.primary.foreign,prefixScope=deepcopy(self.primary.scope),
            binding=deepcopy(self.primary.state['binding']),ownerToken=self.primary.state['ownerToken'],
            producerHostProcessIdentity=self.process.process_identity,originalRequestId=self.request,stereoScope=dict(primary.scope,role='actor'))
        return primary,expected
    def returned(self,primary,expected):return self.facade.source_return(self.target.selector,self.primary,self.process,expected,stereo=primary)
    def test_normal_fourteen_both_roles_stereo_then_original_actor_png_return_and_esrch(self):
        primary,expected=self.original_pass();returned=self.returned(primary,expected)
        self.assertEqual(2,returned.graph.version);self.assertEqual(2,len(returned.graph.images));self.assertEqual(2,len(primary.state['images']))
        self.assertEqual({'actor'}, {returned.graph.expected['stereoScope']['role']});self.assertEqual(4,len(self.model.gpu.commands))
        returned.acknowledge();self.command('consume','consumed');self.command('exit');self.worker.wait(timeout=5);receipt=returned.finish()
        self.assertEqual('ESRCH',receipt['result']['processReturn']['processAbsence']['errorSymbol'])
        self.assertEqual(['script:world-web-client'],receipt['result']['retainedResources'])
        self.assertFalse(returned.graph.vm.facts['retired']);self.assertEqual([],list(self.model.native_root.iterdir()))
        self.assertEqual(receipt,returned.receipt())

    def test_actor_png_same_bytes_replacement_inode_refuses_return_before_parent_nonce(self):
        primary,expected=self.original_pass()
        from adapters.normal_feature_state import PrivateFeatureState
        body=PrivateFeatureState(self.target.feature_root/'pico-world-web-actor-stereo.json').read();row=body['payload']['images'][0]['png']
        path=self.artifacts/row['name'];old=path.with_name('retained-old-actor.png');path.rename(old)
        path.write_bytes(old.read_bytes());path.chmod(0o600)
        with self.assertRaises(NativeUIError):self.returned(primary,expected)
        self.assertTrue(old.exists());self.assertFalse((self.target.feature_root/'pico-world-web-actor-source-pass-consumption.json').exists())

    def test_foreign_scene_and_mutated_original_image_facts_refuse_before_parent_nonce(self):
        primary,expected=self.original_pass();expected=deepcopy(expected);expected['stereoScope']['sceneUrl']='http://foreign.invalid/scene.json'
        calls=list(self.sources.calls)
        with self.assertRaises(NativeUIError):self.returned(primary,expected)
        self.assertEqual(calls,self.sources.calls)
        self.assertFalse((self.target.feature_root/'pico-world-web-actor-source-pass-consumption.json').exists())
        expected['stereoScope']=dict(primary.scope,role='actor');owner=self.returned(primary,expected)
        from adapters.normal_feature_state import PrivateFeatureState
        from adapters.pico4.browser_actor_graph import original
        wrong=PrivateFeatureState(self.target.feature_root/'pico-world-web-actor-stereo.json').read()
        wrong['payload']['images'][0]['phase']['runId']=uuid.uuid4().hex
        with self.target.lock.held(),self.assertRaises(ValueError):
            original_join(wrong,expected['stereoScope'],owner.graph.history,lambda name:original(self.artifacts/name))
        owner.graph.images[0]['facts']['state']['page']='foreign'
        with self.assertRaises(NativeUIError):owner.acknowledge()
        self.assertEqual(calls,self.sources.calls)
        self.assertFalse((self.target.feature_root/'pico-world-web-actor-source-pass-consumption.json').exists())

    def test_lost_applied_actor_capture_keeps_native_owner_and_never_acquires_a_cold_replacement(self):
        self.primary.prepare();self.primary.observe();self.launch(stereo=True);self.command('publish','publication')
        self.primary.act(self.call(0));self.primary.observe();self.model.capture_error=True
        self.command('publish','publication');self.worker.wait(timeout=10);self.assertNotEqual(0,self.worker.returncode)
        self.assertEqual(1,len(self.model.gpu.commands));self.assertIsNotNone(self.model.owner_store('actor').read())
        self.assertFalse((self.target.feature_root/'pico-world-web-actor-source-pass.json').exists())
        before=len(self.sources.calls);commands=deepcopy(self.model.gpu.commands)
        cold=self.facade.prefix(self.target.selector,self.actor.source,self.foreign,role='actor',require_new_actor=True)
        with self.assertRaises(NativeUIError):cold.publish()
        self.assertEqual(before,len(self.sources.calls));self.assertEqual(commands,self.model.gpu.commands)


if __name__=='__main__':unittest.main()
