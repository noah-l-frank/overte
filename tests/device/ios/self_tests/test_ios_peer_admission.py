"""Prepared existing SDK admission without native verification or store writes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest
from ios.adapters.peer_admission import admit_existing_peer,validate
from ios.adapters.script_runtime import IOSScriptRuntime
from ios.self_tests import test_ios_installed_code as installed


class PeerAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.fixture=installed.InstalledCodeTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups);self.fixture.active()
        self.primary=dict(self.fixture.scope,processIdentity='31',sessionId='separate-primary-session',targetFingerprint='b'*64)
        self.runtime=object.__new__(IOSScriptRuntime);self.gets=[]
        self.runtime._existing=self.existing
        self.runtime.adapter=SimpleNamespace(_binding=lambda *_args:self.fixture.make())
    def existing(self,selector):
        self.gets.append(selector);return None,self.fixture.scope['sessionId'],dict(sessionId=self.fixture.scope['sessionId']),{},deepcopy(self.fixture.scope)
    def admit(self):return admit_existing_peer(self.runtime,'private-actor-selector',self.primary,epoch_ms=lambda:90000.,monotonic=lambda:1.)
    def test_actual_prepared_original_and_current_process_are_retained_without_mutation(self):
        commands=deepcopy(self.fixture.native.commands);raw=self.fixture.store.path.read_bytes();value=self.admit()
        self.assertEqual('42',value['binding']['processIdentity']);self.assertEqual(self.fixture.store.read(),value['installedBefore'])
        self.assertEqual(commands,self.fixture.native.commands);self.assertEqual(raw,self.fixture.store.path.read_bytes())
        self.assertEqual(['private-actor-selector']*2,self.gets)
        self.assertNotIn('private-actor-selector',str(value));self.assertEqual(value['binding'],validate(value,self.primary))
    def test_missing_bound_owner_changed_process_or_source_never_triggers_native_repair(self):
        for fault in ('owner','process','source'):
            with self.subTest(fault=fault):
                record=self.fixture.store.read();process=deepcopy(self.fixture.process);source=deepcopy(self.fixture.source)
                if fault=='owner':self.fixture.store.discard(record)
                elif fault=='process':self.fixture.process['pid']=43
                else:self.fixture.source['instance']='f'*32
                before=len(self.fixture.native.commands)
                with self.assertRaises((ValueError,RuntimeError)):self.admit()
                self.assertEqual(before,len(self.fixture.native.commands))
                if fault=='owner':self.fixture.store.write(record,None)
                self.fixture.process,self.fixture.source=process,source
    def test_same_target_or_session_and_foreign_candidate_are_not_independent_admissions(self):
        for key in ('targetFingerprint','sessionId','artifactSha256'):
            original=deepcopy(self.primary)
            self.primary[key]=self.fixture.scope[key] if key!='artifactSha256' else 'f'*64
            with self.subTest(key=key),self.assertRaises((ValueError,RuntimeError)):self.admit()
            self.primary=original
    def test_changed_session_during_read_and_rewritten_historical_native_birth_are_rejected(self):
        existing=self.existing;count=[0]
        def changed(selector):
            result=existing(selector);count[0]+=1
            if count[0]==2:
                values=list(result);values[4]=dict(values[4],generation=values[4]['generation']+1);return tuple(values)
            return result
        self.runtime._existing=changed
        with self.assertRaises((ValueError,RuntimeError)):self.admit()
        self.runtime._existing=existing;value=self.admit();value['installedAfter']['observation']['instance']='f'*32
        with self.assertRaises((ValueError,RuntimeError)):validate(value,self.primary)


if __name__=='__main__':unittest.main()
