"""Existing candidate ownership and fail-closed SDK teardown without new sessions."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import os
from types import SimpleNamespace
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.witness import Client
from ios.adapters.world_web_feature import IOSWorldWebFeature
from ios.adapters.world_web_finalization import finalize_existing
from ios.adapters.world_web_runtime import IOSWorldWebRuntime
from ios.self_tests.test_ios_create_files import BINDING


class WorldWebRuntimeTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.root.chmod(0o700)
        for role in ('primary','actor'):(self.root/role).mkdir(mode=0o700)
        def forbidden(*_args,**_kwargs):raise AssertionError('Ownership reconstruction accessed a live SDK')
        self.checked=[]
        adapter=SimpleNamespace(state_path=lambda role:self.root/role/'session.json',_candidate_guard=lambda:True,_binding=lambda:True,
            _retired_candidate_scope=lambda target,scope:self.checked.append((target,deepcopy(scope))),
            ensure_session=forbidden,describe=forbidden,read_session=forbidden)
        self.runtime=IOSWorldWebRuntime(adapter);self.client=Client('https://controlled.invalid/feature-fixture/v1','r'*64)
        self.settings=dict(artifactRoot=str(self.root),imagePolicy=dict(source='world-render-target',marker=[0,0,64,64],subject=[64,64,128,128]),
            origins=dict(primary='https://controlled.invalid',foreign='https://foreign.invalid'),primaryTarget='primary')
    def coordinator(self):
        flow=self.runtime._world_web_feature('actor','a'*32,role='actor',client=self.client,settings=self.settings)
        with flow.held():
            flow.load();flow.state=dict(phase='ready',binding=BINDING|dict(sessionId='peer',targetFingerprint='a'*64),primaryBinding=BINDING,
                phaseInstance='b'*32,initialTicket='c'*32,actorAdmission=None,baseline=None,lease=None,beforeImage=None,images=[],retirement=None);flow.save()
        return flow
    def test_actual_factory_reconstructs_exact_actor_header_without_sdk_or_fixture_requests(self):
        flow=self.coordinator();self.assertIsInstance(flow,IOSWorldWebFeature)
        self.assertNotIn(self.client.token,str(flow.previous))
        rebuilt=self.runtime._world_web_feature('actor',flow.run,role='actor',client=self.client,settings=self.settings)
        with rebuilt.held():rebuilt.load();self.assertEqual(flow.state,rebuilt.state)
        original=flow.store.read();changed=deepcopy(original);changed['origins']['foreign']='https://different.invalid';flow.store.write(changed,original)
        with rebuilt.held(),self.assertRaises(NativeUIError):rebuilt.load()
        self.assertEqual([],self.checked)
    def test_original_body_failure_survives_both_actual_role_locks_normal_release(self):
        flow=self.coordinator();failure=RuntimeError('actual body predicate')
        with self.assertRaises(RuntimeError) as caught:
            with flow.held():
                flow.lock.assert_held();flow.primary_lock.assert_held();raise failure
        self.assertIs(failure,caught.exception)
        self.assertIsNone(flow.lock._owner);self.assertIsNone(flow.primary_lock._owner)
        for lock in (flow.lock,flow.primary_lock):
            with ScriptSourceLock(lock.path).held():pass
        self.assertEqual([],self.checked)
    def test_changed_actual_lock_inode_still_refuses_normal_exit_over_body_failure(self):
        flow=self.coordinator();replacement=flow.lock.path.with_suffix('.replacement')
        with self.assertRaises(NativeUIError):
            with flow.held():
                replacement.write_bytes(b'');replacement.chmod(0o600);os.replace(replacement,flow.lock.path)
                raise RuntimeError('body predicate must not bypass changed lock inode')
        self.assertIsNone(flow.lock._owner);self.assertIsNone(flow.primary_lock._owner)
        self.assertEqual([],self.checked)
    def test_absent_owner_is_empty_but_lost_owner_with_any_retained_worldweb_carrier_stays_owned(self):
        self.assertFalse(finalize_existing(self.runtime,'actor',None,None))
        flow=self.coordinator();original=flow.store.read();flow.store.path.unlink()
        for name in ('ios-world-web-actor-sources.json','ios-world-web-actor-'+flow.run+'-final.json',
                'world-web-a-ledgerbefore-unknown.json','worldweb-marker-read-abandoned-unknown.json',
                'wwc-unknown.json','wwrg-unknown.json','wwsu-unknown.json','ios-worldweb-pending.tmp',
                'phase-publication-world-web-'+flow.run+'-actor.json','phase-retirement-world-web-'+flow.run+'-actor.json'):
            carrier=PrivateFeatureState(flow.store.path.with_name(name));carrier.write(original,None)
            with self.subTest(name=name),self.assertRaises(NativeUIError):finalize_existing(self.runtime,'actor',None,None)
            self.assertEqual(original,carrier.read());carrier.path.unlink()
        self.assertFalse(finalize_existing(self.runtime,'actor',None,None));self.assertEqual([],self.checked)
    def test_unfinished_actor_cannot_fall_through_to_sdk_delete_and_malformed_headers_fail_before_candidate_access(self):
        flow=self.coordinator();original=flow.store.read()
        for field,value in (('runId','wrong'),('role','primary'),('iosWorldWebFeatureVersion',True)):
            changed=dict(original,**{field:value});flow.store.write(changed,original)
            with self.subTest(field=field),self.assertRaises((NativeUIError,ValueError)):finalize_existing(self.runtime,'actor',None,None)
            flow.store.write(original,changed)
        self.assertEqual([],self.checked)
        with self.assertRaises(NativeUIError):finalize_existing(self.runtime,'actor',None,None)
        self.assertEqual(original,flow.store.read());self.assertEqual(1,len(self.checked));self.assertNotIn('processIdentity',self.checked[0][1])
    def test_self_peer_and_unknown_configuration_fields_are_refused_without_sdk(self):
        for change in ({'primaryTarget':'actor'},{'actorTarget':'other'},{'state':{}},{'origins':dict(primary='https://controlled.invalid',foreign='https://controlled.invalid')}):
            with self.subTest(change=change),self.assertRaises((NativeUIError,ValueError)):
                self.runtime._world_web_feature('actor','a'*32,role='actor',client=self.client,settings=self.settings|change)


if __name__=='__main__':unittest.main()
