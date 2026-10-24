"""Unchanged common primary waits through the actual OverteSession contract.

Explicit private diagnostic: no peer, image, execute or acceptance substitute.
The original Lifecycle fixture supplies its existing native/OS/Qt model seams.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid

from feature_journeys.engine import Journey
from feature_journeys.fixtures import context
from feature_journeys.scenarios import SCENARIOS,expand
from adapters.normal_feature_state import PrivateFeatureState
from self_tests import test_pico_lifecycle_observation_baseline as original


class LifecyclePrimaryWaitTests(unittest.TestCase):
    def setUp(self):
        self.fixture=original.LifecycleObservationBaselineTests();self.addCleanup(self.fixture.doCleanups)
        self.frames=[];self.calls=[];self.forbidden_calls=[]
        self.fixture.collect_baseline=self.baseline
        self.fixture.before_participant=self.before_participant
        self.fixture.setUp()

    def forbidden(self,*_args,**_kwargs):
        self.forbidden_calls.append(True)
        raise AssertionError('Primary-only diagnostic has no peer or image authority')

    def count(self,label):
        self.frames.append(dict(stage=label,frames=len(self.world.state['frames'])))

    def baseline(self):
        self.source=self.fixture.observer;self.world=self.source.world;self.native=self.fixture.editor.native
        root=Path(__file__).resolve().parents[1]
        environment=dict(OVERTE_DEVICE_ADAPTER_MANIFEST=str(self.source.store.path.with_name('unused-adapter.json')),
            OVERTE_DEVICE_TARGET_SELECTOR='unit-lifecycle-primary-only',OVERTE_DEVICE_ARTIFACT_DIR=str(self.source.store.path.parent))
        # Load the unchanged session implementation. Isolate its import-time
        # environment from other unit modules; never call the device transport.
        saved=sys.modules.pop('module_support',None)
        try:
            with patch.dict('os.environ',environment):
                spec=importlib.util.spec_from_file_location('lifecycle_actual_overte_session',root/'overte_session.py')
                self.session_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.session_module)
        finally:
            sys.modules.pop('module_support',None)
            if saved is not None:sys.modules['module_support']=saved
        self.session=self.session_module.OverteSession()
        def operation(name,fields):
            self.calls.append((name,deepcopy(fields)))
            return self.source.observe_operation(name,fields)
        dispatch=patch.object(self.session_module,'operation',operation);dispatch.start();self.addCleanup(dispatch.stop)
        def invoke(name,fields):
            _prefix,area,kind=name.split('.')
            return self.session.feature_operation(area,kind,fields)
        def continuity(*_args):self.assertTrue(self.native.alive)
        self.journey=Journey('lifecycle-input',self.source.run,
            'http://controlled.invalid/feature-fixture/v1/runs/'+self.source.run+'/',invoke=invoke,
            witness=self.forbidden,activate=self.forbidden,read_artifact=self.forbidden,image_policy={},
            continuity=continuity,monotonic=self.world.monotonic,epoch_ms=self.native.epoch,
            sleep=self.native.sleep,report=self.forbidden)
        self.count('before-baseline')
        expected=expand(SCENARIOS['lifecycle-input']['baseline'],context(self.source.run))
        actual=self.journey.wait('primary-only-baseline',uuid.uuid4().hex,self.native.epoch(),expected,[],duration=.5)
        self.assertEqual([],actual['resources']);self.count('after-baseline')

    def before_participant(self,role,_owner):
        if role!='chat':return
        self.count('after-original-create-world-back')
        expected=expand(SCENARIOS['lifecycle-input']['steps'][3]['state'],context(self.source.run))
        self.journey.required_lifecycle=deepcopy(self.journey.lifecycle)
        self.journey.wait('04-back-primary-only',uuid.uuid4().hex,self.native.epoch(),expected,[],duration=3.)
        self.count('after-back-negative-wait')

    def test_actual_session_primary_baseline_and_back_wait_share_the_unchanged_world_budget(self):
        self.count('after-original-pending-prefix')
        stages={row['stage']:row['frames'] for row in self.frames}
        # Persist actual counts/epochs before any measurement assertion. The
        # unchanged floating-point wait may legitimately need its next .25s
        # sample when the nominal 3s difference is still 2.999999999999999.
        PrivateFeatureState(self.source.store.path.with_name('lifecycle-primary-wait-diagnostics.json')).write(
            dict(diagnosticVersion=1,scope='private-primary-only',stages=self.frames,
                samples=deepcopy(self.journey.samples),phases=deepcopy(self.journey.phases)),None)
        print('Actual same-World Primary-only frame deltas: '+str(self.frames),flush=True)
        self.assertEqual(3,stages['after-baseline']-stages['before-baseline'])
        back=[row for row in self.journey.samples if row['phase']=='04-back-primary-only']
        self.assertEqual(len(back),stages['after-back-negative-wait']-stages['after-original-create-world-back'])
        self.assertEqual(self.journey.phases[1]['advancingSamples'],len(back));self.assertGreaterEqual(len(back),13)
        consumed=len(self.journey.samples)
        self.assertEqual(consumed,self.journey.sequence);self.assertEqual(consumed,len(self.calls))
        self.assertEqual(consumed,len(self.source.disk['records']));self.assertLessEqual(len(self.world.state['frames']),128)
        self.assertEqual([],self.forbidden_calls)
        for sequence,(name,fields) in enumerate(self.calls):
            self.assertEqual('feature.lifecycle-input.observe',name)
            self.assertEqual({'contractVersion','runId','afterSequence'},set(fields))
            self.assertEqual(sequence,fields['afterSequence'])
        self.assertEqual(3,self.journey.phases[0]['advancingSamples'])
        self.assertGreaterEqual(self.journey.phases[1]['stableSeconds'],3.)
        self.assertLess(self.journey.phases[1]['stableSeconds'],20.)
        self.assertTrue(self.source.store.path.exists());self.assertTrue(self.world.store.path.exists())


if __name__=='__main__':unittest.main()
