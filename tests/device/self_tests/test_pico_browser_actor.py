"""Closed observer configuration and no cold live Actor acquisition."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import tempfile
from pathlib import Path
import unittest

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.feature_observer import configuration
from self_tests import test_pico_tablet_web_stereo_flow as existing


class PicoBrowserActorTests(unittest.TestCase):
    def test_browser_configuration_requires_its_exact_version_bound_run_original_request_and_foreign_origin(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);store=PrivateFeatureState(root/'config.json')
            good=dict(picoFeatureObserverVersion=4,area='tablet-web',target='synthetic',candidateArguments=['--apk','owned.apk'],
                fixtureUrl='http://127.0.0.1:32001/feature-fixture/v1',foreignFixtureUrl='http://127.0.0.1:32002/feature-fixture/v1',
                actorToken='b'*64,artifactRoot=str(root),durationSeconds=30,runId='a'*32,originalRequestId='c'*32)
            store.write(good,None);self.assertEqual(good,configuration(store.path));previous=good
            bad=[]
            for key in ('runId','originalRequestId','foreignFixtureUrl','artifactRoot'):
                value=deepcopy(good);del value[key];bad.append(value)
            for changes in ({'picoFeatureObserverVersion':3},{'runId':'../foreign'},
                {'foreignFixtureUrl':good['fixtureUrl']},{'input':'open'},{'actorToken':'wrong'}):
                bad.append(dict(good,**changes))
            for value in bad:
                store.write(value,previous);previous=value
                with self.assertRaises((ValueError,RuntimeError,TypeError)):configuration(store.path)

    def fixture(self):
        harness=existing.PicoTabletWebStereoFlowTests();harness.setUp();self.addCleanup(harness.doCleanups)
        f=harness.fixture;f.activate();f.primary.prepare();return f

    def test_new_actor_refuses_original_role_or_orphan_before_native_query(self):
        for orphan in (False,True):
            with self.subTest(orphan=orphan):
                f=self.fixture();f.actor.require_new_actor=True
                store=f.actor.role_store
                if orphan:store=PrivateFeatureState(store.path.with_name(store.path.name+'.frame-000.json'))
                store.write(dict(retainedOriginal=True),None);original=store.path.read_bytes()
                before=len(f.target.command_log)
                with self.assertRaises(NativeUIError):f.actor.publish()
                self.assertEqual(before,len(f.target.command_log));self.assertEqual(original,store.path.read_bytes())
                self.assertFalse(f.actor._actor_started);self.assertIsNone(f.actor.actor_retirement)

    def test_new_actor_admission_is_rechecked_under_original_lock_after_pending_input(self):
        from feature_journeys.phase_fixture import PhasePending
        f=self.fixture();f.actor.require_new_actor=True
        with f.target.lock.held():
            owner=f.primary.owner();owner['phase']='acting';f.primary.save(owner)
        with self.assertRaises(PhasePending):f.actor.publish()
        self.assertFalse(f.actor._actor_started)
        store=f.actor.role_store;store.write(dict(retainedOriginal=True),None);before=len(f.target.command_log)
        with self.assertRaises(NativeUIError):f.actor.publish()
        self.assertEqual(before,len(f.target.command_log));self.assertEqual({'retainedOriginal':True},store.read())


if __name__=='__main__':unittest.main()
