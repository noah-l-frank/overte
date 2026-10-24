"""True readonly primary triples have distinct readers and complete originals.

The existing session/wait and native/Qt/OS/physics seams stay explicit. No
device, peer, image, complete shared journey or mutating World is synthesized.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from adapters.chat_journey import source_bundles
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_observation import PicoLifecycleObservation
from adapters.pico4 import lifecycle_source as ui
from self_tests import test_pico_lifecycle_observation_baseline as baseline_fixture
from self_tests import test_pico_lifecycle_primary_wait as wait_fixture


def readonly_entry(fixture):
    def create(cls,restore,editor,pending,path):
        native=fixture.editor.native
        source,axes,avatar=native.sources()
        for reader in (source,axes,avatar):reader.source_lock=restore.lock
        return cls.readonly_before_inputs(restore,editor,pending,source,axes,avatar,path)
    return patch.object(PicoLifecycleObservation,'before_inputs',classmethod(create))


class LifecycleReadOnlyPrimaryTests(wait_fixture.LifecyclePrimaryWaitTests):
    def setUp(self):
        self.fixture=baseline_fixture.LifecycleObservationBaselineTests();self.addCleanup(self.fixture.doCleanups)
        self.frames=[];self.calls=[];self.forbidden_calls=[]
        self.fixture.collect_baseline=self.baseline;self.fixture.before_participant=self.before_participant
        with readonly_entry(self.fixture):self.fixture.setUp()

    def test_actual_session_primary_baseline_and_back_wait_share_the_unchanged_world_budget(self):
        self.count('after-original-pending-prefix')
        stages={row['stage']:row['frames'] for row in self.frames}
        self.assertEqual(stages['before-baseline'],stages['after-baseline'])
        self.assertEqual(stages['after-original-create-world-back'],stages['after-back-negative-wait'])
        consumed=len(self.journey.samples)
        self.assertEqual(consumed,self.journey.sequence);self.assertEqual(consumed,len(self.source.disk['records']))
        self.assertEqual([],self.forbidden_calls);self.assertEqual(3,self.source.disk['lifecyclePrimaryObservationVersion'])
        seen={key:set() for key in ('ui','gesture','drive')}
        for record in self.source.disk['records']:
            row,_=source_bundles.original(self.source.history,self.source.disk['chunks'],self.source.disk['bundles'],record)
            self.assertNotIn('worldFrameIndex',row);self.assertIn('worldOwnerContinuity',row)
            original,_=source_bundles.original(self.source.history,self.source.disk['chunks'],self.source.disk['bundles'],row['worldBundle'])
            packets=self.source.acquisition.originals(original['world'])
            for key,packet in packets.items():
                self.assertNotIn(packet['commandId'],seen[key]);seen[key].add(packet['commandId'])
        with self.world.lock.held():self.world.load()
        last=self.world.originals(self.world.state['frames'][-1])
        self.assertEqual(self.world.source.previous,ui.summary(last['ui']))
        self.assertIsNot(self.world.source,self.source.acquisition.source)
        report=dict(scope='private-readonly-primary',stages=self.frames,mutatingWorldFrames=len(self.world.state['frames']),
            readonlyTriples=consumed,totalPhysicalTriples=len(self.world.state['frames'])+consumed,
            parts=len(self.source.disk['chunks']),physicalRawBytes=self.source.history.raw_bytes,
            logicalOriginalBytes=source_bundles.logical_bytes(self.source.disk['bundles']))
        PrivateFeatureState(self.source.store.path.with_name('lifecycle-readonly-diagnostics.json')).write(report,None)
        self.assertLessEqual(report['parts'],512);self.assertLessEqual(report['physicalRawBytes'],16*1024*1024)
        self.assertLessEqual(report['logicalOriginalBytes'],16*1024*1024);self.assertLessEqual(consumed,128)
        print('Actual readonly/owner acquisition bill: '+str(report),flush=True)


class LifecycleReadOnlyRefusalTests(unittest.TestCase):
    def early(self,probe):
        fixture=baseline_fixture.LifecycleObservationBaselineTests();self.addCleanup(fixture.doCleanups)
        reached=[];completed=[]
        def collect():
            reached.append(True);probe(fixture);completed.append(True)
            raise NativeUIError('Explicit stop after readonly source counter; no normal Create input')
        fixture.collect_baseline=collect
        with readonly_entry(fixture):
            with self.assertRaises(NativeUIError):fixture.setUp()
        self.assertEqual([True],reached)
        self.assertEqual([True],completed)
        self.assertEqual([],fixture.editor.transport.envelopes)
        return fixture

    def test_original_readonly_cursor_regression_refuses_before_another_query(self):
        def probe(fixture):
            source=fixture.observer;source.read(after_sequence=0);before=len(source.world.state['frames'])
            source.acquisition.source.previous['sequence']-=1
            calls=[]
            def forbidden(*_args,**_kwargs):calls.append(True);raise AssertionError('Query after changed cursor')
            for reader in source.acquisition.readers:reader.send=forbidden
            source.reader.send=source.native.send=forbidden
            with self.assertRaises(NativeUIError):source.read(after_sequence=1)
            self.assertTrue(source.failed);self.assertEqual([],calls)
            self.assertEqual(before,len(source.world.state['frames']));self.assertEqual(1,len(source.disk['records']))
        self.early(probe)

    def test_foreign_native_generation_original_is_kept_before_pending_or_feature_query(self):
        def probe(fixture):
            source=fixture.observer;avatar=source.acquisition.avatar;original=avatar.original
            def foreign():
                value=json.loads(original());value['instance']='f'*32
                return json.dumps(value)
            avatar.original=foreign;calls=[]
            def forbidden(*_args,**_kwargs):calls.append(True);raise AssertionError('Query after foreign generation')
            source.reader.send=source.native.send=forbidden
            with self.assertRaises(NativeUIError):source.read(after_sequence=0)
            self.assertTrue(source.failed);self.assertEqual([],calls);self.assertEqual([],source.disk['records'])
            index=source.disk['pending']['worldBundle'];self.assertIsNotNone(index)
            packet,_=source_bundles.original(source.history,source.disk['chunks'],source.disk['bundles'],index)
            actual=json.loads(packet['world']['drive']['raw']);self.assertEqual('f'*32,actual['instance'])
            self.assertEqual(2,len(source.world.state['frames']))
        self.early(probe)

    def test_landed_readonly_final_save_does_not_refresh_original_native_age(self):
        def probe(fixture):
            source=fixture.observer;save=source.save;clock=source.native.clock_ms;landed=[]
            def delayed(value):
                save(value)
                if value['pending'] is None and value['records']:
                    landed.append(True);source.native.clock_ms=lambda:clock()+2000
            source.save=delayed
            with self.assertRaises(NativeUIError):source.read(after_sequence=0)
            self.assertEqual([True],landed);self.assertTrue(source.failed)
            self.assertEqual(1,len(source.disk['records']));self.assertEqual(2,len(source.world.state['frames']))
        self.early(probe)


if __name__=='__main__':unittest.main()
