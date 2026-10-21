"""Independent worker privacy/control boundaries; no device/network calls."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import unittest
from adapters.pico4.feature_observer import configuration,run
from adapters.authentication_journey.feature import AuthenticationPhasePending
from adapters.normal_ui import NativeUIError
from adapters.graphics_journey.fixture import GraphicsPhasePending,GraphicsRunRetired


class PicoFeatureObserverTests(unittest.TestCase):
    def setUp(self):
        self.clock=0.;self.count=0;self.invalid=False;self.finished=False
        self.config=dict(picoFeatureObserverVersion=1,area='authentication',target='synthetic-target',
            candidateArguments=['--apk','owned.apk'],fixtureUrl='https://owned.invalid/feature-fixture/v1',actorToken='b'*64,durationSeconds=30)
        self.owner=dict(runId='a'*32,fixtureUrl=self.config['fixtureUrl']+'/runs/'+'a'*32+'/')
        self.flow=SimpleNamespace(run='a'*32,fixture_url=self.owner['fixtureUrl'],publish=self.publish,
            role_store=SimpleNamespace(read=lambda:None if self.finished else {}))
        self.journey=SimpleNamespace(authentication_feature_store=lambda _target:SimpleNamespace(read=lambda:self.owner),
            authentication_retirement_store=lambda _target:SimpleNamespace(read=lambda:None),_authentication_feature=self.actor)
    def actor(self,target,run,*,role,client):
        self.assertEqual('actor',role);self.assertEqual('a'*32,run);self.assertEqual(self.config['actorToken'],client.token)
        return self.flow
    def publish(self):
        self.count+=1
        if self.invalid:raise ValueError('Invalid synthetic original')
        if self.count==1:raise AuthenticationPhasePending('Pending synthetic transaction')
        self.owner=None;self.finished=True
    def sleep(self,value):self.clock+=value
    def test_only_owned_actor_publication_and_pending_wait_are_allowed(self):
        self.assertEqual(0,run(self.journey,self.config,monotonic=lambda:self.clock,sleep=self.sleep))
        self.assertEqual(2,self.count)
    def test_invalid_original_is_fatal_and_does_not_request_repair_or_retry_input(self):
        self.invalid=True
        with self.assertRaises(ValueError):run(self.journey,self.config,monotonic=lambda:self.clock,sleep=self.sleep)
        self.assertEqual(1,self.count)
    def test_missing_or_foreign_owned_run_never_publishes_success(self):
        self.owner=None
        with self.assertRaises(NativeUIError):run(self.journey,self.config,monotonic=lambda:self.clock,sleep=self.sleep)
        self.assertEqual(0,self.count)
        self.clock=0.;self.owner=dict(runId='a'*32,fixtureUrl='https://foreign.invalid/run/')
        with self.assertRaises(NativeUIError):run(self.journey,self.config,monotonic=lambda:self.clock,sleep=self.sleep)
        self.assertEqual(0,self.count)
    def test_private_config_is_https_and_has_only_read_actor_authority(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);root.chmod(0o700);path=root/'actor.json'
            path.write_text(json.dumps(self.config));path.chmod(0o600)
            self.assertEqual(self.config,configuration(path))
            for change in (dict(fixtureUrl='http://owned.invalid/feature-fixture/v1'),dict(readerToken='x'*64),dict(area='audio')):
                path.write_text(json.dumps(self.config|change))
                with self.assertRaises(NativeUIError):configuration(path)
    def test_graphics_v2_config_pins_private_artifacts_and_does_not_promote_the_v1_reader(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);root.chmod(0o700);path=root/'actor.json'
            value=self.config|dict(picoFeatureObserverVersion=2,area='graphics',artifactRoot=str(root))
            path.write_text(json.dumps(value));path.chmod(0o600);self.assertEqual(value,configuration(path))
            for change in (dict(picoFeatureObserverVersion=1),dict(artifactRoot='relative'),dict(readerToken='x'*64)):
                path.write_text(json.dumps(value|change))
                with self.assertRaises(NativeUIError):configuration(path)
    def test_graphics_keeps_publishing_during_the_parent_plan_until_its_own_final_window_finishes(self):
        self.config.update(picoFeatureObserverVersion=2,area='graphics')
        plan=dict(kind='retirement',runId='a'*32,fixtureUrl=self.owner['fixtureUrl'])
        def publish():
            self.count+=1
            if self.count==1:raise GraphicsPhasePending('Original world restoration is pending')
            raise GraphicsRunRetired({})
        self.flow.publish=publish
        self.journey=SimpleNamespace(graphics_feature_store=lambda target:SimpleNamespace(read=lambda:self.owner),
            graphics_retirement_store=lambda target:SimpleNamespace(read=lambda:plan),_graphics_feature=self.actor)
        self.assertEqual(0,run(self.journey,self.config,monotonic=lambda:self.clock,sleep=self.sleep))
        self.assertEqual(2,self.count)


if __name__=='__main__':unittest.main()
