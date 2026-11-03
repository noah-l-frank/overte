"""Actual Actor loop/admission clocks with declared publication-work models.

The publication method is a timing model, never Native/VR/Witness evidence.
Real elapsed work and sleeps demonstrate the scheduler's sampling interval.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.browser_actor import run
from adapters.pico4.browser_actor_admission import BrowserActorAdmission
from adapters.pico4.operation_host import process_identity
from adapters.pico4.tablet_web_feature import PicoTabletWebFeature
from adapters.script_journey.lock import ScriptSourceLock


class ModelComplete(Exception):pass


class BrowserActorPeriodTests(unittest.TestCase):
    def setup_loop(self,*,version=6,seconds=120,work=.30):
        temp=tempfile.TemporaryDirectory(prefix='browser-actor-period-');self.addCleanup(temp.cleanup)
        root=Path(temp.name);root.chmod(0o700);now=time.monotonic()
        config=dict(picoFeatureObserverVersion=version,area='tablet-web',target='declared-timing-model',
            candidateArguments=['--declared-host-model'],fixtureUrl='http://127.0.0.1:32001/feature-fixture/v1',
            foreignFixtureUrl='http://127.0.0.1:32002/feature-fixture/v1',actorToken='b'*64,
            artifactRoot=str(root),durationSeconds=120,runId='a'*32,originalRequestId='c'*32)
        admission=None
        if version==6:
            config.update(browserOwnerBudget=dict(id='d'*32,startedMonotonic=now,deadlineMonotonic=now+seconds),
                browserParentHostProcessIdentity=process_identity(os.getppid()))
            original=PrivateFeatureState(root/'configuration.json');original.write(config,None)
            admission=BrowserActorAdmission(original.path,config);self.addCleanup(admission.close_host)
        actor=PicoTabletWebFeature.__new__(PicoTabletWebFeature)
        actor.require_new_actor=True;actor._actor_started=True
        actor.lock=ScriptSourceLock(root/'sources.lock');actor.store=PrivateFeatureState(root/'owner.json')
        actor.store.write(dict(runId=config['runId'],fixtureUrl=config['fixtureUrl']+'/runs/'+config['runId']+'/'),None)
        self.samples=[];self.sleeps=[]
        def publish():
            time.sleep(work);self.samples.append(time.monotonic())
            if len(self.samples)==3:raise ModelComplete()
        actor.publish=publish
        def sleep(delay):self.sleeps.append(delay);time.sleep(delay)
        journey=SimpleNamespace(feature=lambda *_args,**_kwargs:actor,_world_web_clock=lambda _target:time.time()*1000)
        return journey,config,admission,sleep

    def test_explicit_actor_six_period_includes_actual_publication_work(self):
        journey,config,admission,sleep=self.setup_loop()
        with self.assertRaises(ModelComplete):run(journey,config,sleep=sleep,admission=admission)
        deltas=[b-a for a,b in zip(self.samples,self.samples[1:])]
        self.assertEqual(2,len(deltas));self.assertTrue(all(0<delta<=.5 for delta in deltas),deltas)
        self.assertTrue(all(.05<=delay<.15 for delay in self.sleeps),self.sleeps)

    def test_legacy_actor_four_keeps_original_fixed_sleep(self):
        journey,config,admission,sleep=self.setup_loop(version=4,work=.01)
        with self.assertRaises(ModelComplete):run(journey,config,sleep=sleep)
        self.assertEqual([.25,.25],self.sleeps)

    def test_explicit_original_whole_deadline_expires_during_work_without_new_sleep_or_publication(self):
        journey,config,admission,sleep=self.setup_loop(seconds=.15,work=.20)
        with self.assertRaises(NativeUIError):run(journey,config,sleep=sleep,admission=admission)
        self.assertEqual(1,len(self.samples));self.assertEqual([],self.sleeps)


if __name__=='__main__':unittest.main()
