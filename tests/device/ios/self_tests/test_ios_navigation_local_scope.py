"""Real SDK/installed metadata with explicitly modeled native bundle originals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError
from ios.adapters.installed_code import InstalledCodeBinding
from ios.adapters.navigation_local_scope import guard
from ios.self_tests import test_ios_installed_code as installed_fixture


class NavigationLocalScopeTests(unittest.TestCase):
    def setUp(self):
        self.f=f=installed_fixture.InstalledCodeTests();f.setUp();self.addCleanup(f.doCleanups);f.active()
        class Base:
            sdk=deepcopy(f.scope);good=True
            def _candidate_guard(self):need(self.good)
            def read_session(self,_selector):return deepcopy(self.sdk)
            def _target(self,_selector):self._candidate_guard();return {}
            def _scope(self,_selector,_session,state,_target):return {key:state[key] for key in f.scope}
            def _binding(self,*_args):return f.make()
            def _binding_store(self,_selector):return f.store
        self.base=Base();self.source=dict(binding=dict(f.scope,processIdentity='42'),client=None,state=deepcopy(f.scope),target={})

    def test_pure_guard_accepts_actual_forward_observation_without_any_live_sdk_or_native_query(self):
        check=guard(self.base,'owned',self.source);self.f.make().verify()
        native=deepcopy(self.f.native.commands);original=self.f.store.path.read_bytes();inode=self.f.store.path.stat().st_ino
        with (patch.object(InstalledCodeBinding,'verify',side_effect=AssertionError('No live verification')),
              patch.object(InstalledCodeBinding,'continuity',side_effect=AssertionError('No live continuity'))):
            self.assertTrue(check());self.assertTrue(check())
        self.assertEqual(native,self.f.native.commands);self.assertEqual(original,self.f.store.path.read_bytes())
        self.assertEqual(inode,self.f.store.path.stat().st_ino)

    def test_changed_candidate_sdk_session_generation_and_pid_refuse_local_authority(self):
        check=guard(self.base,'owned',self.source);native=deepcopy(self.f.native.commands);original=self.f.store.path.read_bytes()
        for fault in ('missing','session','generation','target','pid','candidate'):
            self.base.sdk=deepcopy(self.f.scope);self.base.good=True
            if fault=='missing':self.base.sdk=None
            elif fault=='session':self.base.sdk['sessionId']='foreign'
            elif fault=='generation':self.base.sdk['generation']+=1
            elif fault=='target':self.base.sdk['targetFingerprint']='f'*64
            elif fault=='pid':self.base.sdk['processIdentity']='43'
            else:self.base.good=False
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):check()
        self.assertEqual(native,self.f.native.commands);self.assertEqual(original,self.f.store.path.read_bytes())

    def test_retirement_or_native_observation_rollback_never_reauthorizes_input(self):
        check=guard(self.base,'owned',self.source);old=self.f.store.read();self.f.make().verify();self.assertTrue(check())
        newer=self.f.store.read();self.f.store.write(old,newer)
        with self.assertRaises((NativeUIError,ValueError)):check()
        self.f.store.write(dict(newer,phase='retiring'),old)
        with self.assertRaises((NativeUIError,ValueError)):check()


if __name__=='__main__':unittest.main()
