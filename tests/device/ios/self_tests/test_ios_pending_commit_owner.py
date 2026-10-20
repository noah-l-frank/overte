"""Original iOS HTTP/AFC/native-clock join; native/OS sources are synthetic."""
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
from self_tests.test_pending_commit_owner import Boundary,RUN
from self_tests.test_native_feature_observation import Boundary as ClockBoundary


class IOSPendingCommitOwnerTests(unittest.TestCase):
    def setUp(self):
        self.source=Boundary()
        def edit(value):
            value['processId']=42
            if value['commit']:value['commit']['observation']['processId']=42
        self.source.edit=edit
        self.clock=ClockBoundary();self.clock.mutate=lambda v:v.update(processId=42,capturedEpochMs=self.source.epoch())
        self.process=dict(bundleId='org.example.overte',pid=42,foreground=True)
        self.actions=[];self.fixture=FixtureState();self.echo=b''
        self.target=dict(platform='ios',physical=True,probe={'kind':'ios-documents'},appId='org.example.overte',
            testBuild=dict(resultsDirectory='owned-results',fixtureOrigin='http://controlled.invalid:49121'))
        test=self
        class Client:
            def execute(self,session,operation,values):
                test.assertEqual('test-only',session);test.assertEqual('mobile: pullFile',operation)
                path=values['remotePath']
                if path=='@org.example.overte:documents/owned-results/feature-pending-commit-owner.json':raw=test.source.original()
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
            if value['action']=='feature-pending-commit-owner':self.source.send(value)
            elif value['action']=='feature-native-observe':self.clock.send(value)
            else:raise AssertionError('unexpected native request')
            return Response()
        boundary=patch('ios.adapters.feature_observation.post_request',side_effect=post)
        boundary.start();self.addCleanup(boundary.stop)
        self.client=Client()
        self.observer=FeatureObservation(self.client,'test-only',self.target,lambda:deepcopy(self.process),
            monotonic=lambda:self.source.clock,sleep=self.source.sleep)

    def test_actual_component_factory_retains_original_event_and_native_clock_over_private_afc(self):
        adapter=component.IOSAdapter.__new__(component.IOSAdapter)
        native=SimpleNamespace(client=self.client,session='test-only',target=self.target,observe_process=lambda:deepcopy(self.process))
        adapter._scripts=lambda _selector:SimpleNamespace(ui=SimpleNamespace(io=SimpleNamespace(native=native)))
        owner=adapter._pending_owner('owned',self.source.intents.append)
        owner.focus(RUN);owner.type_owned(RUN);held=owner.hold(RUN);event=held['commit']['observation']['eventId']
        self.source.replace_context();owner.attempt_retired(RUN,event)
        self.assertEqual([],owner.release_owned(RUN,event)['resources']['pendingRuns'])
        self.assertEqual(self.source.intents,[c for c in self.source.commands if c['operation']!='observe'])
        self.assertTrue(all(c['commandId'].startswith('ios-') for c in self.source.commands))
        self.assertEqual(['feature-pending-commit-owner','feature-native-observe'],self.actions[:2])

    def test_ignored_input_or_cleanup_cannot_become_success(self):
        owner=self.observer.pending_owner(self.source.intents.append);self.source.fault='focus-ignored'
        with self.assertRaises(RuntimeError):owner.focus(RUN)
        self.assertEqual(1,sum(c['operation']=='focus' for c in self.source.commands))
        self.source.fault='';owner.focus(RUN);owner.type_owned(RUN);held=owner.hold(RUN);self.source.fault='release-ignored'
        with self.assertRaises(RuntimeError):owner.release_owned(RUN,held['commit']['observation']['eventId'])

    def test_foreign_pid_clock_or_foreground_loss_blocks_original_join(self):
        owner=self.observer.pending_owner(self.source.intents.append);owner.read(RUN);before=len(self.source.commands)
        self.process['foreground']=False
        with self.assertRaises(RuntimeError):owner.read(RUN)
        self.assertEqual(before,len(self.source.commands));self.process['foreground']=True
        self.clock.mutate=lambda v:v.update(processId=43)
        with self.assertRaises(RuntimeError):owner.read(RUN)
        self.clock.mutate=lambda v:v.update(processId=42);self.source.edit=lambda v:v.update(processId=43)
        with self.assertRaises(RuntimeError):owner.read(RUN)

    def test_read_only_and_unbound_canonical_factories_cannot_authorize_mutations(self):
        owner=self.observer.pending_owner()
        with self.assertRaises(RuntimeError):owner.focus(RUN)
        self.assertFalse(any(c['operation']!='observe' for c in self.source.commands))
        with patch.object(component.AppiumAdapter,'load_targets',return_value={}):
            adapter=binding.create_adapter(SimpleNamespace(platform='ios',action='cleanup'),component.AppiumAdapter)
        with self.assertRaisesRegex(ValueError,'INSTALLED_CODE_BINDING_UNAVAILABLE'):adapter._pending_owner('private-selector')


if __name__=='__main__':unittest.main()
