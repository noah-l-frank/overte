"""Original iOS native reply HTTP/AFC/clock/session join; native/OS synthetic."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from ios.adapters.feature_observation import FeatureObservation
from ios.adapters import adapter as component
from adapters.ios import binding
from fixture.serve import FixtureState
from self_tests.test_native_navigation_replies import Boundary,RUN
from self_tests.test_native_feature_observation import Boundary as ClockBoundary


class IOSNavigationRepliesTests(unittest.TestCase):
    def setUp(self):
        self.source=Boundary();self.source.edit=lambda value:value.update(processId=42)
        self.clock=ClockBoundary();self.clock.mutate=lambda value:value.update(processId=42,capturedEpochMs=self.source.epoch())
        self.process=dict(bundleId='org.example.overte',pid=42,foreground=True)
        self.actions=[];self.fixture=FixtureState();self.echo=b'';self.scope_checks=0
        self.target=dict(platform='ios',physical=True,probe={'kind':'ios-documents'},appId='org.example.overte',
            testBuild=dict(resultsDirectory='owned-results',fixtureOrigin='http://controlled.invalid:49121'))
        self.state=dict(sessionId='test-only',generation=1,processIdentity='42',targetFingerprint=self.fingerprint())
        test=self
        class Client:
            def execute(self,session,operation,values):
                test.assertEqual('test-only',session);test.assertEqual('mobile: pullFile',operation)
                path=values['remotePath']
                if path=='@org.example.overte:documents/owned-results/feature-navigation-replies.json':raw=test.source.original()
                elif path=='@org.example.overte:documents/owned-results/feature-native-observation.json':raw=json.dumps(test.clock.sample)
                else:raise AssertionError('foreign private document')
                return base64.b64encode(raw.encode()).decode()
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*_):return False
            def read(self,_limit):return test.echo
        def post(request,timeout):
            self.assertEqual(5,timeout);value=json.loads(request.data);self.fixture.set_client_command(value)
            self.actions.append(value['action']);self.echo=json.dumps(value).encode()
            if value['action']=='feature-navigation-replies':self.source.send(value)
            elif value['action']=='feature-native-observe':self.clock.send(value)
            else:raise AssertionError('unexpected native request')
            return Response()
        boundary=patch('ios.adapters.feature_observation.post_request',side_effect=post)
        boundary.start();self.addCleanup(boundary.stop)
        self.client=Client()
        self.observer=FeatureObservation(self.client,'test-only',self.target,lambda:deepcopy(self.process),
            monotonic=lambda:self.source.clock,sleep=self.source.sleep)
    def fingerprint(self):return hashlib.sha256(json.dumps(self.target,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    def factory(self):
        adapter=component.IOSAdapter.__new__(component.IOSAdapter)
        adapter.target=lambda _selector:self.target
        adapter.ensure_session=lambda _selector:(self.client,'test-only',self.state)
        adapter.read_session=lambda _selector:deepcopy(self.state)
        def original_scope(*args):
            self.scope_checks+=1
            if self.process is None or self.process['foreground'] is not True or str(self.process['pid'])!=self.state['processIdentity']:
                raise RuntimeError('Synthetic original process guard rejected')
            return self.state['processIdentity']
        adapter.assert_ios_process_identity=original_scope
        adapter.native_process=lambda *_args:deepcopy(self.process)
        adapter._scripts=lambda *_args:(_ for _ in ()).throw(AssertionError('Native replies must not open a Scripts editor'))
        return adapter._navigation_replies('owned')

    def test_actual_factory_uses_original_private_bytes_separate_clock_and_session_without_scripts_ui(self):
        reader=self.factory();self.source.error();joined=self.source.join(reader)
        self.assertEqual(self.source.events[0],joined['native']);self.assertEqual(self.source.provider()['responses'][0],joined['http'])
        self.assertGreater(self.scope_checks,3)
        self.assertEqual(['feature-navigation-replies','feature-native-observe'],self.actions)
        self.assertTrue(self.source.commands[0]['commandId'].startswith('ios-'))
        self.assertNotIn('normalScripts',self.target)

    def test_changed_session_generation_or_target_blocks_before_another_native_command(self):
        reader=self.factory();reader.read(RUN);before=len(self.source.commands)
        self.state['generation']+=1
        with self.assertRaises(RuntimeError):reader.read(RUN)
        self.assertEqual(before,len(self.source.commands));self.state['generation']-=1
        self.target['changed']='different target profile'
        with self.assertRaises(RuntimeError):reader.read(RUN)
        self.assertEqual(before,len(self.source.commands))

    def test_ignored_source_or_foreign_pid_and_independent_clock_cannot_be_success(self):
        reader=self.observer.navigation_replies();self.source.ignored=True
        with self.assertRaises(RuntimeError):reader.read(RUN)
        self.assertEqual(1,len(self.source.commands));self.assertLessEqual(self.source.clock,5.01)
        self.source.ignored=False;self.source.edit=lambda value:value.update(processId=43)
        with self.assertRaises(RuntimeError):reader.read(RUN)
        self.source.edit=lambda value:value.update(processId=42);self.clock.mutate=lambda value:value.update(processId=43)
        with self.assertRaises(RuntimeError):reader.read(RUN)

    def test_superseded_lookup_or_lost_original_foreground_cannot_lend_current_authority(self):
        reader=self.factory();self.source.error();self.source.generation+=1
        with self.assertRaises(RuntimeError):self.source.join(reader)
        before=len(self.source.commands);self.process['foreground']=False
        with self.assertRaises(RuntimeError):reader.read(RUN)
        self.assertEqual(before,len(self.source.commands))

    def test_unbound_canonical_cleanup_factory_cannot_bypass_installed_source_gate(self):
        with patch.object(component.AppiumAdapter,'load_targets',return_value={}):
            adapter=binding.create_adapter(SimpleNamespace(platform='ios',action='cleanup'),component.AppiumAdapter)
        with self.assertRaisesRegex(ValueError,'INSTALLED_CODE_BINDING_UNAVAILABLE'):adapter._navigation_replies('private-selector')


if __name__=='__main__':unittest.main()
