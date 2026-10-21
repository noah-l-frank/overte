"""Both actual old-process roles must join before ordinary iOS restart input."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from ios.adapters.graphics_fixture import GraphicsPhasePending
from ios.self_tests.test_ios_graphics_feature import FeatureHarness
from ios.self_tests.test_ios_graphics_scene import RUN
from feature_journeys.scenarios import VERSION


class RestartBarrierTests(FeatureHarness,unittest.TestCase):
    def planned(self):
        self.baseline()
        for verb,inputs in (('open',{}),('set-haze',dict(enabled=True)),('set-mirrors',dict(enabled=True)),('close',{})):
            self.feature().act(self.activate(verb,inputs))
        call=self.activate('restart-app');primary=self.feature()
        with primary.lock.held():
            primary.source.status();state=primary.control()
            state.update(phase='acting',ticket=call['ticket'],call=call,backend=primary.source.previous);primary.save(state)
            primary.reserve_calibration(state,'restart','acting');self.assertFalse(primary.progress_calibration(state))
        with self.assertRaises(GraphicsPhasePending):self.feature('actor').publish()
        with primary.lock.held():
            state=primary.control();self.assertTrue(primary.progress_calibration(state));primary.reserve_barrier(state)
        return call
    def primary_join(self):
        primary=self.feature()
        with primary.lock.held():self.assertFalse(primary.progress_barrier(primary.control()))
        return primary

    def restarting(self):
        call=self.planned();primary=self.primary_join()
        with self.assertRaises(GraphicsPhasePending):self.feature('actor').publish()
        with primary.lock.held():
            state=primary.control();self.assertTrue(primary.progress_barrier(state));primary.restart().act(call)
            state.update(stage=1,binding=deepcopy(primary.scene().binding),phase='restart-observing');primary.save(state)
        return call,primary

    def test_foreign_rejoined_actor_original_cannot_become_a_successful_restart_ack(self):
        call,primary=self.restarting()
        with primary.lock.held():self.assertFalse(primary.progress_rejoined(primary.control()))
        with self.assertRaises(GraphicsPhasePending):self.feature('actor').publish()
        with primary.lock.held():
            store=type(primary.store)(primary.root/('graphics-restart-rejoined-'+RUN+'-actor.json'))
            before=store.read();changed=deepcopy(before);changed['role']='primary';store.write(changed,before)
        with self.assertRaises(NativeUIError):self.feature().act(call)
        self.assertEqual('restart-observing',self.feature().control()['phase'])
        self.assertEqual(['app.stop','app.launch'],self.inputs)

    def test_lost_committed_rejoined_copy_adopts_same_capture_without_repeating_input(self):
        call,primary=self.restarting();store=type(primary.store);write=store.write
        def lost(target,value,previous):
            write(target,value,previous)
            if target.path.name=='graphics-restart-rejoined-'+RUN+'-primary.json':
                raise OSError('Synthetic lost committed new-process original return')
        with primary.lock.held(),patch.object(store,'write',new=lost),self.assertRaises(OSError):
            primary.progress_rejoined(primary.control())
        count=len(self.gpu.commands)
        with primary.lock.held():self.assertFalse(primary.progress_rejoined(primary.control()))
        self.assertEqual(count,len(self.gpu.commands));self.assertEqual(['app.stop','app.launch'],self.inputs)
        with self.assertRaises(GraphicsPhasePending):self.feature('actor').publish()
        self.assertEqual({'performed':True},self.feature().act(call))
        self.assertEqual(['app.stop','app.launch'],self.inputs)

    def test_both_roles_take_current_old_images_after_restoration_before_any_stop(self):
        call=self.planned();primary=self.primary_join();self.assertEqual([],self.inputs)
        state=primary.control();self.assertIsNone(state['restartBarrier']['roles']['actor'])
        with self.assertRaises(GraphicsPhasePending):self.feature('actor').publish()
        self.assertEqual([],self.inputs)
        with primary.lock.held():
            state=primary.control();self.assertTrue(primary.progress_barrier(state));barrier=deepcopy(state['restartBarrier'])
            self.assertTrue(barrier['native']['graphics']['hazeSetting']);self.assertTrue(barrier['native']['graphics']['mirrorsSetting'])
            frames=[]
            for role in ('primary','actor'):
                _record,scope,_sha=primary.barrier_record(role,'after',barrier['binding'])
                frame=scope.frame(scope.state['last'],barrier['binding'])[0];frames.append(frame)
                self.assertEqual(42,frame['nativeAfter']['processId']);self.assertTrue(frame['nativeAfter']['graphics']['hazeSetting'])
                self.assertEqual(call['ticket'],frame['provider']['ticket'])
            self.assertNotEqual(frames[0]['capture']['requestId'],frames[1]['capture']['requestId'])
        with primary.lock.held():
            state=primary.control();primary.restart().act(call);scene=primary.scene()
            state.update(stage=1,binding=deepcopy(scene.binding),phase='restart-observing');primary.save(state)
            self.assertFalse(primary.progress_rejoined(state))
        with self.assertRaises(GraphicsPhasePending):self.feature('actor').publish()
        self.feature().act(call);self.assertEqual(['app.stop','app.launch'],self.inputs)
        self.assertEqual(43,self.sdk.pid)
        value=self.feature().observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=0));self.feature('actor').publish()
        self.assertTrue(value['state']['haze']);self.assertTrue(value['state']['mirror'])
        self.assertEqual(42,frames[1]['nativeAfter']['processId']);self.feature().act(call)
        self.assertEqual(['app.stop','app.launch'],self.inputs)

    def test_lost_committed_after_record_return_adopts_the_same_original_capture(self):
        self.planned();primary=self.feature();actual=primary.barrier_record
        def lost(role,kind,binding,value=None):
            result=actual(role,kind,binding,value)
            if kind=='after' and value is not None:raise OSError('Synthetic lost committed barrier-copy return')
            return result
        with primary.lock.held(),patch.object(primary,'barrier_record',side_effect=lost),self.assertRaises(OSError):primary.progress_barrier(primary.control())
        count=len(self.gpu.commands);recovered=self.primary_join()
        self.assertEqual(count,len(self.gpu.commands));self.assertEqual([],self.inputs)
        self.assertEqual('observed',recovered.control()['restartBarrier']['roles']['primary']['phase'])

    def test_foreign_actor_copy_prevents_stop_even_after_both_nominal_acknowledgments(self):
        call=self.planned();primary=self.primary_join()
        with self.assertRaises(GraphicsPhasePending):self.feature('actor').publish()
        with primary.lock.held():
            state=primary.control();store=primary.barrier_store('actor','after');value=store.read();changed=deepcopy(value);changed['role']='primary'
            store.write(changed,value)
        with self.assertRaises(NativeUIError):self.feature().act(call)
        self.assertEqual([],self.inputs);self.assertEqual(42,self.sdk.pid)

    def test_later_fixture_phase_does_not_authorize_old_restart_input(self):
        call=self.planned();self.primary_join();self.activate('cleanup')
        with self.assertRaises(NativeUIError):self.feature().act(call)
        self.assertEqual([],self.inputs);self.assertTrue(self.sdk.running)


if __name__=='__main__':unittest.main()
