"""Same actual physical SDK admission, with no native verification/mutation."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from ios.adapters.tablet_web_admission import admit_existing_tablet_observer,validate
from ios.adapters.script_runtime import IOSScriptRuntime
from ios.self_tests import test_ios_installed_code as installed


class TabletWebAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.fixture=installed.InstalledCodeTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups);self.fixture.active()
        self.physical=dict(self.fixture.scope,processIdentity='42');self.runtime=object.__new__(IOSScriptRuntime);self.gets=[]
        self.runtime._existing=self.existing;self.runtime.adapter=SimpleNamespace(_binding=lambda *_:self.fixture.make())
    def existing(self,selector):
        self.gets.append(selector);return None,self.fixture.scope['sessionId'],dict(sessionId=self.fixture.scope['sessionId']),{},deepcopy(self.fixture.scope)
    def admit(self,**kwargs):return admit_existing_tablet_observer(self.runtime,'private-existing-selector',self.physical,epoch_ms=lambda:90000.,monotonic=lambda:1.,**kwargs)
    def test_actual_same_physical_binding_is_retained_without_new_session_native_query_or_record_write(self):
        commands=deepcopy(self.fixture.native.commands);raw=self.fixture.store.path.read_bytes();value=self.admit()
        self.assertEqual(self.physical,validate(value,self.physical));self.assertEqual(raw,self.fixture.store.path.read_bytes())
        self.assertEqual(commands,self.fixture.native.commands);self.assertEqual(['private-existing-selector']*2,self.gets)
        self.assertEqual(os.getpid(),value['hostProcessId']);self.assertNotIn('private-existing-selector',str(value));self.assertNotIn('remote',value)
    def test_another_target_session_candidate_or_process_cannot_be_admitted_as_same_client(self):
        for field,replacement in [('targetFingerprint','b'*64),('sessionId','separate-actor-session'),('artifactSha256','f'*64),('processIdentity','43')]:
            original=deepcopy(self.physical);self.physical[field]=replacement
            with self.subTest(field=field),self.assertRaises((ValueError,RuntimeError)):self.admit()
            self.physical=original
    def test_missing_binding_changed_DVT_source_or_restarted_process_never_repairs_or_verifies(self):
        for fault in ('record','source','process'):
            original=self.fixture.store.read();before_process=deepcopy(self.fixture.process);before_source=deepcopy(self.fixture.source)
            if fault=='record':self.fixture.store.discard(original)
            elif fault=='source':self.fixture.source['instance']='f'*32
            else:self.fixture.process['pid']=43
            count=len(self.fixture.native.commands)
            with self.subTest(fault=fault),self.assertRaises((ValueError,RuntimeError)):self.admit()
            self.assertEqual(count,len(self.fixture.native.commands))
            if fault=='record':self.fixture.store.write(original,None)
            self.fixture.process,self.fixture.source=before_process,before_source
    def test_session_change_during_read_rewritten_native_birth_or_slow_acquisition_is_not_admission(self):
        existing=self.existing;calls=[0]
        def changed(selector):
            result=list(existing(selector));calls[0]+=1
            if calls[0]==2:result[4]=dict(result[4],generation=result[4]['generation']+1)
            return tuple(result)
        self.runtime._existing=changed
        with self.assertRaises((ValueError,RuntimeError)):self.admit()
        self.runtime._existing=existing;value=self.admit()
        value['installedAfter']['observation']['instance']='f'*32
        with self.assertRaises((ValueError,RuntimeError)):validate(value,self.physical)
        epochs=iter([90000.,92000.])
        with self.assertRaises((ValueError,RuntimeError)):
            admit_existing_tablet_observer(self.runtime,'private-existing-selector',self.physical,epoch_ms=lambda:next(epochs),monotonic=lambda:1.)


if __name__=='__main__':unittest.main()
