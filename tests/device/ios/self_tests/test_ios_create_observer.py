"""Private independent actor loop/configuration, without native/SDK execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.phase_fixture import PhasePending
from ios import create_observer
from ios.adapters.create_runtime import IOSCreateRuntime


class CreateObserverTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.root.chmod(0o700)
        self.config=dict(iosCreateObserverVersion=1,target='actor',candidateArguments=['--physical-candidate-metadata','private-candidate.json'],
            fixtureUrl='https://controlled.invalid/feature-fixture/v1',actorToken='a'*64,durationSeconds=30,
            create=dict(artifactRoot=str(self.root),imagePolicy=dict(source='world-render-target',marker=[0,0,64,64],subject=[64,64,128,128]),primaryTarget='primary'))
        self.store=PrivateFeatureState(self.root/'config.json');self.store.write(self.config,None)
    def test_closed_actor_configuration_requires_explicit_independent_peer_policy_and_actual_candidate_arguments(self):
        self.assertEqual(self.config,create_observer.configuration(self.store.path))
        for fault in ('same','effect','candidate','version'):
            value=deepcopy(self.config)
            if fault=='same':value['create']['primaryTarget']='actor'
            elif fault=='effect':value['create']['objects']=[]
            elif fault=='candidate':value['candidateArguments']=[]
            else:value['iosCreateObserverVersion']=True
            self.store.write(value,self.store.read())
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):create_observer.configuration(self.store.path)
    def test_existing_run_metadata_admits_actor_once_then_waits_and_finalizes_without_describe_or_session_creation(self):
        metadata=PrivateFeatureState(self.root/'ios-create-primary-feature.json');clock=[0.];events=[]
        class Flow:
            run='b'*32;state=dict(phase='ready')
            @contextmanager
            def held(_self):yield
            def load(_self):pass
            def publish(_self):
                events.append('publish')
                if events.count('publish')==1:raise PhasePending('Original phase not activated yet')
                _self.state['phase']='retired'
        class Runtime(IOSCreateRuntime):
            def _create_store(_self,selector,name):
                self.assertEqual('primary',selector);self.assertEqual('ios-create-primary-feature.json',name);return metadata
            def _create_feature(_self,selector,run,**kwargs):
                self.assertEqual(('actor','b'*32),(selector,run));self.assertEqual('actor',kwargs['role']);events.append('factory');return Flow()
            def _existing(_self,*_args):raise AssertionError('Observer orchestration must not create or describe an SDK session')
        runtime=Runtime(SimpleNamespace(_candidate_guard=lambda:True,_binding=lambda:True))
        def sleep(seconds):
            clock[0]+=seconds
            if metadata.read() is None:metadata.write(dict(role='primary',runId='b'*32,fixtureUrl=self.config['fixtureUrl']+'/runs/'+'b'*32+'/'),None)
        self.assertEqual(0,create_observer.run(runtime,self.config,monotonic=lambda:clock[0],sleep=sleep))
        self.assertEqual(['factory','publish','publish'],events)


if __name__=='__main__':unittest.main()
