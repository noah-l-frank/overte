"""Original iOS Web HTTP/AFC/clock/factory logic, synthetic native/OS sources."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
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
from self_tests.test_native_web_dom import Boundary,RUN,URL
from self_tests.test_native_feature_observation import Boundary as ClockBoundary


class IOSWebDOMTests(unittest.TestCase):
    def setUp(self):
        self.source=Boundary();self.source.mutate=lambda v:v.update(processId=42)
        self.clock=ClockBoundary();self.clock.mutate=lambda v:v.update(processId=42)
        self.process=dict(bundleId='org.example.overte',pid=42,foreground=True)
        self.actions=[];self.fixture=FixtureState();self.echo=b''
        self.target=dict(platform='ios',physical=True,probe={'kind':'ios-documents'},appId='org.example.overte',
            testBuild=dict(resultsDirectory='owned-results',fixtureOrigin='http://controlled.invalid:49121'))
        test=self
        class Client:
            def execute(self,session,operation,values):
                test.assertEqual('test-only',session);test.assertEqual('mobile: pullFile',operation)
                path=values['remotePath']
                if path=='@org.example.overte:documents/owned-results/feature-web-dom-observation.json':raw=test.source.original()
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
            if value['action']=='feature-web-dom-observe':self.source.send(value)
            elif value['action']=='feature-native-observe':self.clock.send(value)
            else:raise AssertionError('unexpected native request')
            return Response()
        boundary=patch('ios.adapters.feature_observation.post_request',side_effect=post)
        boundary.start();self.addCleanup(boundary.stop)
        self.client=Client()
        self.observer=FeatureObservation(self.client,'test-only',self.target,lambda:deepcopy(self.process),
            monotonic=lambda:self.source.clock,sleep=self.source.sleep)

    def test_actual_component_factory_uses_original_afc_bytes_then_independent_native_clock(self):
        adapter=component.IOSAdapter.__new__(component.IOSAdapter)
        native=SimpleNamespace(client=self.client,session='test-only',target=self.target,observe_process=lambda:deepcopy(self.process))
        adapter._scripts=lambda _selector:SimpleNamespace(ui=SimpleNamespace(io=SimpleNamespace(native=native)))
        reader=adapter._web_dom('owned');value=reader.read(RUN,'world',URL)
        self.assertEqual(42,value['processId']);self.assertEqual('Grüße 🌍',value['source']['dom']['editor']['text'])
        self.assertEqual(['feature-web-dom-observe','feature-native-observe'],self.actions)
        self.assertTrue(self.source.commands[0]['commandId'].startswith('ios-'))
        self.assertEqual({'schemaVersion','commandId','action','runId','surface','fixtureUrl'},set(self.source.commands[0]))
        self.assertEqual(0,value['source']['nativeView']['httpErrorStatus'])

    def test_ignored_foreign_or_stale_original_source_is_not_retained_as_success(self):
        self.source.ignored=True
        with self.assertRaises(RuntimeError):self.observer.web_dom().read(RUN,'world',URL)
        self.assertEqual(1,len(self.source.commands));self.assertLessEqual(self.source.clock,5)
        self.assertNotIn('feature-native-observe',self.actions)
        self.source.ignored=False;self.source.mutate=lambda v:v.update(processId=43)
        with self.assertRaises(RuntimeError):self.observer.web_dom().read(RUN,'world',URL)
        self.source.mutate=lambda v:v.update(processId=42,capturedEpochMs=18000)
        with self.assertRaises(RuntimeError):self.observer.web_dom().read(RUN,'world',URL)

    def test_changed_pid_or_foreign_independent_clock_blocks_the_actual_join(self):
        reader=self.observer.web_dom();reader.read(RUN,'world',URL);before=len(self.source.commands)
        self.process['pid']=43
        with self.assertRaises(RuntimeError):reader.read(RUN,'world',URL)
        self.assertEqual(before,len(self.source.commands))
        self.process['pid']=42;self.clock.mutate=lambda v:v.update(processId=43)
        with self.assertRaises(RuntimeError):reader.read(RUN,'world',URL)

    def test_cleanup_only_canonical_adapter_cannot_bypass_installed_binding_for_new_factory(self):
        with patch.object(component.AppiumAdapter,'load_targets',return_value={}):
            adapter=binding.create_adapter(SimpleNamespace(platform='ios',action='cleanup'),component.AppiumAdapter)
        with self.assertRaisesRegex(ValueError,'INSTALLED_CODE_BINDING_UNAVAILABLE'):adapter._web_dom('private-selector')


if __name__=='__main__':unittest.main()
