"""Graphics worker lifecycle; no device, native compiler or SDK execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios import graphics_observer as worker
from ios.adapters.graphics_fixture import GraphicsPhasePending,GraphicsRunRetired

RUN='a'*32
POLICY=dict(source='world-render-target',marker=[0,0,64,32],subject=[0,32,640,400])


class GraphicsWorkerTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        self.config=dict(iosGraphicsObserverVersion=1,target='owned',candidateArguments=['--artifact-root','/private/candidate'],
            fixtureUrl='http://127.0.0.1:12345/feature-fixture/v1',actorToken='a'*64,durationSeconds=30,
            artifactRoot=str(self.root),imagePolicy=deepcopy(POLICY))
        self.original=dict(runId=RUN,fixtureUrl=self.config['fixtureUrl']+'/runs/'+RUN+'/',
            artifactRoot=str(self.root),imagePolicy=deepcopy(POLICY))
        self.current=deepcopy(self.original);self.plan=None;self.clock=0;self.published=0;self.steps=0;self.created=[]
        self.on_sleep=lambda:None;self.on_publish=lambda:None;self.on_finalize=lambda:False
        self.flow=SimpleNamespace(run=RUN,fixture_url=self.original['fixtureUrl'],lock=ScriptSourceLock(self.root/'sources.lock'),publish=self.publish)

    def publish(self):
        self.flow.lock.assert_held();self.published+=1;self.on_publish()

    def finalize(self,_flow):
        self.assertIs(_flow,self.flow)
        def step():
            self.flow.lock.assert_held();self.steps+=1;return self.on_finalize()
        return SimpleNamespace(step=step)

    def factory(self,run):self.created.append(run);return self.flow
    def sleep(self,seconds):self.clock+=seconds;self.on_sleep()
    def run_worker(self):
        return worker.run_flow(self.config,lambda:self.current,lambda:self.plan,self.factory,
            finalizer=self.finalize,monotonic=lambda:self.clock,sleep=self.sleep)

    def test_private_configuration_fixes_world_policy_and_rejects_primary_credential(self):
        store=PrivateFeatureState(self.root/'config.json');store.write(self.config,None)
        self.assertEqual(self.config,worker.configuration(store.path))
        for fields in (dict(iosGraphicsObserverVersion=True),dict(readerToken='b'*64),dict(candidateArguments=[]),
                       dict(artifactRoot='relative'),dict(imagePolicy=POLICY|dict(source='native-screen')),
                       dict(imagePolicy=POLICY|dict(subject=[0,0,True,400])),dict(durationSeconds=0)):
            store.write(self.config|fields,store.read())
            with self.assertRaises((RuntimeError,ValueError)):worker.configuration(store.path)

    def test_retirement_intent_keeps_worker_alive_until_actual_final_receipt(self):
        self.plan=deepcopy(self.original)
        def step():
            self.assertEqual(0,self.published)
            if self.steps==1:self.current=None
            return self.steps==4
        self.on_finalize=step
        self.assertEqual(0,self.run_worker());self.assertEqual(4,self.steps);self.assertEqual([RUN],self.created)

    def test_fixture_retired_exception_starts_finalization_instead_of_exiting(self):
        def publish():raise GraphicsRunRetired({'original':'retired'})
        self.on_publish=publish;self.on_finalize=lambda:self.steps==3
        self.assertEqual(0,self.run_worker());self.assertEqual(1,self.published);self.assertEqual(3,self.steps)

    def test_ordinary_phase_pending_continues_without_poisoning_run(self):
        def publish():raise GraphicsPhasePending('Both original roles are pending')
        self.on_publish=publish
        self.on_sleep=lambda:setattr(self,'plan',deepcopy(self.original)) if self.published==2 else None
        self.on_finalize=lambda:True
        self.assertEqual(0,self.run_worker());self.assertEqual(2,self.published)
        self.assertFalse(worker.failure(self.flow,self.config))

    def test_lost_publication_is_not_retried_and_remains_failed_after_teardown(self):
        def publish():raise RuntimeError('Unknown POST outcome')
        self.on_publish=publish
        self.on_sleep=lambda:setattr(self,'plan',deepcopy(self.original)) if self.clock>=1 else None
        self.on_finalize=lambda:self.steps==2
        self.assertEqual(2,self.run_worker());self.assertEqual(1,self.published)
        self.assertTrue(worker.failure(self.flow,self.config))

    def test_restarted_worker_keeps_original_failure_instead_of_publishing_again(self):
        worker.failure(self.flow,self.config,record=True)
        self.on_sleep=lambda:setattr(self,'plan',deepcopy(self.original))
        self.on_finalize=lambda:True
        self.assertEqual(2,self.run_worker());self.assertEqual(0,self.published)

    def test_lost_finalization_result_recovers_receipt_but_never_reports_green(self):
        self.plan=deepcopy(self.original)
        def step():
            if self.steps==1:raise RuntimeError('Lost original result')
            return self.steps==3
        self.on_finalize=step
        self.assertEqual(2,self.run_worker());self.assertEqual(3,self.steps)

    def test_missing_owner_does_not_stand_in_for_final_receipt(self):
        self.plan=deepcopy(self.original);self.current=None
        self.on_finalize=lambda:False
        with self.assertRaises(NativeUIError):self.run_worker()
        self.assertGreater(self.steps,1);self.assertEqual(0,self.published)

    def test_late_worker_can_attach_to_durable_plan_after_feature_owner_removed(self):
        self.current=None;self.plan=deepcopy(self.original);self.on_finalize=lambda:True
        self.assertEqual(0,self.run_worker());self.assertEqual([RUN],self.created)

    def test_changed_run_root_or_policy_cannot_be_adopted(self):
        for fields in (dict(runId='b'*32),dict(artifactRoot='/foreign'),dict(imagePolicy=POLICY|dict(subject=[1,32,640,400]))):
            with self.subTest(fields=fields):
                self.current=self.original|fields
                with self.assertRaises(NativeUIError):self.run_worker()

    def test_foreign_failure_marker_cannot_be_ignored(self):
        worker.failure(self.flow,self.config,record=True)
        path=self.root/('graphics-worker-failed-'+RUN+'.json');store=PrivateFeatureState(path)
        store.write(store.read()|dict(runId='b'*32),store.read())
        with self.assertRaises(NativeUIError):self.run_worker()

    def test_monotonic_regression_is_not_retirement_evidence(self):
        self.on_sleep=lambda:setattr(self,'clock',-1)
        with self.assertRaises(NativeUIError):self.run_worker()


if __name__=='__main__':unittest.main()
