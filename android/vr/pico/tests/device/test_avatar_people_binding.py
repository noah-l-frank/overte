"""Actual canonical People dispatch with declared candidate/UI/native models.

The original Pal engines and real Parent/role journals execute; no compiler,
account backend, device or native ray is started or qualified by these tests.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import hashlib
import os
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(HERE)]
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.history import unpack
from feature_journeys import phase_fixture
import test_avatar_people_owner as original


class AvatarPeopleBindingTests(unittest.TestCase):
    def setUp(self):
        self.peer='independent-original-peer'
        self.enterContext(patch.dict(os.environ,OVERTE_PICO_AVATAR_PEER_TARGET=self.peer))
        self.original=original.AvatarPeopleOwnerTests(methodName='runTest')
        self.original.setUp();self.addCleanup(self.original.doCleanups)
        self.f=self.original.f;self.adapter=self.f.instance
        self.targets={self.f.target:'primary',self.peer:'peer'};self.resolutions=[]
        owner=self.original;f=self.f
        def locked(target,source_lock=None):
            lock=owner.roles[self.targets[target]]['lock']
            if source_lock is not None:self.assertIs(lock,source_lock)
            return lock
        self.enterContext(patch.object(self.adapter,'_script_journey',return_value=SimpleNamespace(_lock=locked)))
        def runtime(target):
            role=self.targets[target];owner.roles[role]['lock'].assert_held()
            self.assertIsNone(owner.roles['peer' if role=='primary' else 'primary']['lock']._owner)
            self.resolutions.append(role)
            return SimpleNamespace(io=SimpleNamespace(capture=lambda:owner.widgets(role))),None,deepcopy(owner.bindings[role])
        self.enterContext(patch.object(self.adapter,'_script_runtime',side_effect=runtime))
        original_native=self.adapter._native_feature_observer
        def native(target):
            role=self.targets[target]
            if role=='primary':
                result=original_native(target);result.sleep=owner.sleep;return result
            return SimpleNamespace(pid=int(owner.bindings[role]['processIdentity'].split(':')[0]),
                guard=lambda:owner.guard(role),monotonic=lambda:f.clock,clock_ms=lambda:f.epoch,sleep=owner.sleep)
        self.enterContext(patch.object(self.adapter,'_native_feature_observer',side_effect=native))
        self.enterContext(patch.object(self.adapter,'require_pico_session_identity',
            side_effect=lambda target:owner.bindings[self.targets[target]]['processIdentity']))
        self.enterContext(patch.object(self.adapter,'_avatar_state_observer',side_effect=lambda target:owner.native(self.targets[target])))
        self.enterContext(patch.object(self.adapter,'_avatar_people_controls',
            side_effect=lambda target,intent,*,before_send=None:owner.controls(self.targets[target],intent,before_send)))
        base=phase_fixture.PhaseFixtureReader
        class OriginalClockPhaseReader(base):
            def __init__(self,*args,**kwargs):
                kwargs.update(epoch_ms=lambda:f.epoch,monotonic=lambda:f.clock)
                super().__init__(*args,**kwargs)
        self.enterContext(patch.object(phase_fixture,'PhaseFixtureReader',OriginalClockPhaseReader))

    def request(self,verb):return self.original.request(verb)
    def invoke(self,request):return self.adapter.invoke(self.f.target,'feature.avatar-people.act',request)

    def test_real_canonical_dispatch_resolves_roles_separately_and_completes_original_request_cancel(self):
        self.assertEqual(dict(performed=True),self.invoke(self.request('connection-request')))
        self.assertEqual(dict(performed=True),self.invoke(self.request('connection-cancel')))
        self.assertTrue(self.original.sleep_records)
        self.assertEqual(['primary','peer'],self.resolutions[:2])
        roles=self.adapter._avatar_people_roles(self.f.target,self.peer,source_lock=self.f.lock)
        with self.f.lock.held():
            parent=self.adapter._avatar_parent(self.f.target,self.original.parent.run,source_lock=self.f.lock,people_roles=roles)
        state=unpack(parent.store.read()['payload'])[0]
        self.assertEqual(2,parent.store.read()['picoAvatarParentVersion'])
        self.assertIsNone(state['pending']);self.assertEqual(2,len(state['calls']))
        self.assertTrue(all(row['child']['kind']=='people' for row in state['calls']))
        reply=self.original.rpc(operation='capture')
        self.assertEqual('idle',reply['primary']['state']['phase']);self.assertEqual('idle',reply['peer']['state']['phase'])
        self.assertTrue(self.adapter._avatar_parent_owned(self.f.target))
        self.assertFalse(any(c.startswith('feature.avatar-people.') for c in self.adapter.capabilities(self.f.target)))
        # Existing People history must restore before an unavailable whole
        # observation is refused; it must not query Peer while holding Parent.
        from adapters.pico4.avatar_parent import PicoAvatarParent
        called=[];observe=PicoAvatarParent.observe
        def original_observe(parent,request):
            called.append(True);return observe(parent,request)
        with patch.object(PicoAvatarParent,'observe',original_observe),self.assertRaises(ValueError):
            self.adapter.invoke(self.f.target,'feature.avatar-people.observe',
                dict(contractVersion=16,runId=self.original.parent.run,afterSequence=0))
        self.assertEqual([True],called)

    def test_missing_or_same_target_peer_refuses_without_reservation_or_input(self):
        request=self.request('connection-request');before=self.original.parent.store.path.read_bytes()
        for peer in ('',self.f.target):
            with self.assertRaises(ValueError):
                self.adapter._avatar_people_roles(self.f.target,peer,source_lock=self.f.lock)
        self.assertEqual(before,self.original.parent.store.path.read_bytes())
        self.assertFalse(any(row.get('operation')=='input' for row in self.original.sent))

    def test_role_resolution_refuses_when_either_original_lock_is_already_held(self):
        for role in ('primary','peer'):
            with self.original.roles[role]['lock'].held(),self.assertRaises(ValueError):
                self.adapter._avatar_people_roles(self.f.target,self.peer,source_lock=self.f.lock)
        self.assertEqual([],self.resolutions)

    def test_resolved_peer_process_binding_cannot_be_changed_before_source_access(self):
        roles=self.adapter._avatar_people_roles(self.f.target,self.peer,source_lock=self.f.lock)
        self.original.bindings['peer']['processIdentity']='777:200'
        with self.original.peer_lock.held(),self.assertRaises((ValueError,RuntimeError)):
            roles['peer']['guard']()
        self.assertFalse(any(row.get('operation')=='input' for row in self.original.sent))

    def test_orphan_people_journals_and_original_frames_keep_application_cleanup_owned(self):
        # Separate target keys avoid adopting or removing this test's Parent.
        parent=self.adapter.pico_configuration[1];run='a'*32
        for index,(prefix,suffix) in enumerate((('avatar-people-owner-',run),('avatar-people-frame-',run+'-'+'b'*32),
                ('avatar-people-role-primary-owner-',run),('avatar-people-role-peer-owner-',run))):
            target='orphan-only-target-'+str(index);key=hashlib.sha256(('org.overte.pico\0'+target).encode()).hexdigest()[:32]
            self.assertFalse(self.adapter._avatar_parent_owned(target))
            path=parent/(prefix+key+'-'+suffix+'.json');store=PrivateFeatureState(path)
            store.write({'original':'unresolved'},None)
            self.assertTrue(self.adapter._avatar_parent_owned(target));self.assertEqual({'original':'unresolved'},store.read())


if __name__=='__main__':unittest.main()
