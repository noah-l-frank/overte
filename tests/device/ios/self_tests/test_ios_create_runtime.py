"""Candidate runtime factories and private role ownership without app setup."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.create_feature import IOSCreateFeature
from ios.adapters.create_runtime import IOSCreateRuntime
from feature_journeys.witness import Client
from ios.self_tests.test_ios_create_files import BINDING


class CreateRuntimeTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.root.chmod(0o700)
        for role in ('primary','actor'):(self.root/role).mkdir(mode=0o700)
        def forbidden(*_args,**_kwargs):raise AssertionError('A factory created/queried a live SDK session')
        adapter=SimpleNamespace(_candidate_guard=lambda:True,_binding=lambda:True,state_path=lambda role:self.root/role/'session.json',
            ensure_session=forbidden,describe=forbidden,read_session=forbidden)
        self.runtime=IOSCreateRuntime(adapter);self.client=Client('https://controlled.invalid/feature-fixture/v1','r'*64)
        self.settings=dict(artifactRoot=str(self.root),imagePolicy=dict(source='world-render-target',marker=[0,0,64,64],subject=[64,64,128,128]),primaryTarget='primary')
    def test_existing_candidate_factory_serializes_actor_without_install_session_or_secret_configuration(self):
        flow=self.runtime._create_feature('actor','a'*32,role='actor',client=self.client,settings=self.settings)
        self.assertIsInstance(flow,IOSCreateFeature);self.assertNotIn(self.client.token,str(flow.envelope({'phase':'preparing'})))
        with flow.held():
            flow.load();flow.state=dict(phase='ready',binding=BINDING|dict(sessionId='peer',targetFingerprint='a'*64),primaryBinding=BINDING,
                phaseInstance='b'*32,initialTicket='c'*32,actorAdmission=None,beforeImage=None,images=[],exports=[],retirement=None);flow.save()
            original=deepcopy(flow.store.read());flow.load();self.assertEqual('ready',flow.state['phase'])
        rebuilt=self.runtime._create_feature('actor','a'*32,role='actor',client=self.client,settings=self.settings)
        with rebuilt.held():rebuilt.load();self.assertEqual(flow.state,rebuilt.state)
        foreign=dict(original,runId='d'*32);flow.store.write(foreign,original)
        with rebuilt.held(),self.assertRaises(NativeUIError):rebuilt.load()
    def test_no_fallback_runtime_accepts_self_peer_foreign_role_or_unknown_product_result_fields(self):
        for change in ({'primaryTarget':'actor'},{'objects':[]},{'rezAuthority':{}},{'actorTarget':'other'}):
            with self.subTest(change=change),self.assertRaises((NativeUIError,ValueError)):
                self.runtime._create_feature('actor','a'*32,role='actor',client=self.client,settings=self.settings|change)


if __name__=='__main__':unittest.main()
