"""Private actor orchestration only; no source/effect proof is substituted here."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack
from feature_journeys.phase_fixture import PhasePending
from ios import emote_observer as worker
from ios.adapters.emote_observer import EmoteObservationPending
from ios.adapters.emote_runtime import IOSEmoteRuntime
from ios.self_tests.test_ios_emote_sources import RUN


class WorkerTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.root.chmod(0o700)
        self.value=dict(iosEmoteObserverVersion=1,target='actor',primaryTarget='primary',runId=RUN,
            candidateArguments=['--physical-candidate-metadata','private.json'],fixtureUrl='https://controlled.invalid/feature-fixture/v1',
            actorToken='a'*64,durationSeconds=30,artifactRoot=str(self.root),
            imagePolicy=dict(source='world-render-target',marker=[0,0,64,64],subject=[64,64,128,128]))
        self.store=PrivateFeatureState(self.root/'config.json');self.store.write(self.value,None)
    def test_closed_actor_configuration_keeps_separate_selector_and_token(self):
        self.assertEqual(self.value,worker.configuration(self.store.path))
        for changed in (dict(iosEmoteObserverVersion=True),dict(primaryTarget='actor'),dict(durationSeconds=0),
                        dict(candidateArguments=[]),dict(readerToken='b'*64),dict(imagePolicy=self.value['imagePolicy']|dict(source='native-screen'))):
            self.store.write(self.value|changed,self.store.read())
            with self.subTest(changed=changed),self.assertRaises((RuntimeError,ValueError)):worker.configuration(self.store.path)
    def flow(self,events,steps):
        plan=PrivateFeatureState(self.root/('ios-emote-actor-'+RUN+'-finalization.json'))
        root=self.root
        class Flow:
            run=RUN;role='actor';selector='actor';policy=self.value['imagePolicy']
            phase=SimpleNamespace(fixture_url=self.value['fixtureUrl']+'/runs/'+RUN+'/')
            runtime=SimpleNamespace(state_path=lambda _:root/'session.json')
            @contextmanager
            def held(_self):events.append('own-lock');yield
            def publish(_self):
                events.append('publish');step=steps.pop(0)
                if isinstance(step,Exception):raise step
                if step=='complete':plan.write(dict(payload=pack([dict(phase='complete')])),plan.read())
                return {'performed':True}
        result=Flow();result.root=self.root;return result
    def test_pending_baseline_then_actual_flow_retirement_exits_without_restarting_session(self):
        events=[];flow=self.flow(events,[PhasePending('not activated'),EmoteObservationPending('original pending'),'complete'])
        clock=[0.]
        result=worker.run_flow(flow,self.value,monotonic=lambda:clock[0],sleep=lambda seconds:clock.__setitem__(0,clock[0]+seconds))
        self.assertEqual(0,result);self.assertEqual(3,events.count('publish'))
        self.assertFalse((self.root/('emote-worker-failed-'+RUN+'.json')).exists())
    def test_unknown_delivery_remains_failed_after_later_own_finalization(self):
        events=[];flow=self.flow(events,[RuntimeError('uncertain original transport'),'complete']);clock=[0.]
        result=worker.run_flow(flow,self.value,monotonic=lambda:clock[0],sleep=lambda seconds:clock.__setitem__(0,clock[0]+seconds))
        self.assertEqual(2,result);self.assertTrue(worker.failure(flow,self.value))
        original=(self.root/('emote-worker-failed-'+RUN+'.json')).read_bytes()
        events=[];again=self.flow(events,['complete'])
        self.assertEqual(2,worker.run_flow(again,self.value,monotonic=lambda:clock[0],sleep=lambda _:None))
        self.assertEqual(original,(self.root/('emote-worker-failed-'+RUN+'.json')).read_bytes())
    def test_worker_deadline_and_clock_reversal_leave_durable_failure_and_no_extra_publish(self):
        for bad in (30.,-1.):
            with self.subTest(bad=bad):
                events=[];flow=self.flow(events,[PhasePending('not activated')]);clock=[0.]
                def sleep(_):clock[0]=bad
                self.assertEqual(2,worker.run_flow(flow,self.value,monotonic=lambda:clock[0],sleep=sleep))
                self.assertEqual(['publish'],events);self.assertTrue(worker.failure(flow,self.value))
    def test_runtime_factory_uses_only_both_existing_explicit_targets(self):
        events=[];flow=self.flow(events,['complete']);runtime=object.__new__(IOSEmoteRuntime)
        def factory(selector,run,**kwargs):
            self.assertEqual(('actor',RUN),(selector,run));self.assertEqual('actor',kwargs['role'])
            self.assertEqual('primary',kwargs['settings']['primaryTarget']);events.append('factory');return flow
        runtime._emote_feature=factory
        self.assertEqual(0,worker.run(runtime,self.value,sleep=lambda _:None));self.assertEqual(['factory','publish','own-lock'],events)
