"""Independent worker control/privacy checks; no transport or device invocation."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from types import SimpleNamespace
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.pico4.script_observer import configuration, run
from adapters.script_journey.feature import ScriptPhasePending
from adapters.normal_ui import NativeUIError


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.run_id = 'a'*32
        self.config = dict(picoScriptObserverVersion=1,target='synthetic-target',candidateArguments=['--apk','owned.apk'],
            fixtureUrl='http://127.0.0.1:12345/feature-fixture/v1',actorToken='b'*64,durationSeconds=30)
        self.clock = 0.; self.publications = 0; self.failed = False; self.retired = False
        self.owner = dict(runId=self.run_id,fixtureUrl=self.config['fixtureUrl']+'/runs/'+self.run_id+'/')
        self.flow = SimpleNamespace(run=self.run_id,fixture_url=self.owner['fixtureUrl'],
            role_store=SimpleNamespace(read=lambda:None if self.retired else {}),publish=self.publish)
        self.journey = SimpleNamespace(script_feature_store=lambda target:SimpleNamespace(read=lambda:self.owner),
            script_retirement_store=lambda target:SimpleNamespace(read=lambda:None),_script_feature=self.make)
    def make(self,target,run_id,*,role,client):
        self.assertEqual('actor',role);self.assertEqual(self.run_id,run_id)
        self.assertEqual(self.config['actorToken'],client.token)
        return self.flow
    def publish(self):
        self.publications += 1
        if self.failed:raise ValueError('synthetic invalid original')
        if self.publications==1:raise ScriptPhasePending('synthetic in-flight input')
        self.owner = None;self.retired = True
    def sleep(self,seconds):self.clock+=seconds
    def test_independent_actor_waits_only_pending_then_publishes_and_observes_retirement(self):
        self.assertEqual(0,run(self.journey,self.config,monotonic=lambda:self.clock,sleep=self.sleep))
        self.assertEqual(2,self.publications);self.assertEqual(.5,self.clock)
    def test_invalid_original_is_fatal_and_not_retried_as_pending_input(self):
        self.failed=True
        with self.assertRaises(ValueError):run(self.journey,self.config,monotonic=lambda:self.clock,sleep=self.sleep)
        self.assertEqual(1,self.publications)
    def test_missing_owner_is_bounded_and_foreign_owner_is_rejected(self):
        self.owner=None
        with self.assertRaises(NativeUIError):run(self.journey,self.config,monotonic=lambda:self.clock,sleep=self.sleep)
        self.assertEqual(0,self.publications)
        self.clock=0.;self.owner=dict(runId=self.run_id,fixtureUrl='http://foreign.invalid/run/')
        with self.assertRaises(NativeUIError):run(self.journey,self.config,monotonic=lambda:self.clock,sleep=self.sleep)
        self.assertEqual(0,self.publications)
    def test_private_config_rejects_shared_link_unknown_fields_and_unsafe_permissions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);root.chmod(0o700);path=root/'observer.json'
            path.write_text(json.dumps(self.config));path.chmod(0o600)
            self.assertEqual(self.config,configuration(path))
            os.link(path,root/'second.json')
            with self.assertRaises(NativeUIError):configuration(path)
            (root/'second.json').unlink();path.chmod(0o644)
            with self.assertRaises(NativeUIError):configuration(path)
            path.chmod(0o600);path.write_text(json.dumps(self.config|dict(readerToken='never-allowed')))
            with self.assertRaises(NativeUIError):configuration(path)


if __name__=='__main__':unittest.main()
