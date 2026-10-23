"""Per-CLI host lives and immutable native-life admissions, host models only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.tablet_web_admission import follows,installed_forward,validate
from ios.adapters.tablet_web_source_owner import TabletWebSourceOwner
from ios.self_tests import test_ios_tablet_web_admission as admission_tests
from ios.self_tests import test_ios_tablet_web_source_owner as source_tests


class TabletCLIAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.fixture=admission_tests.TabletWebAdmissionTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
    def test_next_real_verification_and_new_host_are_continuous_without_rewriting_bootstrap(self):
        before=self.fixture.admit();literal=deepcopy(before);literal['tabletWebObserverAdmissionVersion']=1
        self.assertEqual(self.fixture.physical,validate(literal,self.fixture.physical))
        self.fixture.fixture.make().verify()
        with patch('os.getpid',return_value=os.getpid()+100000):after=self.fixture.admit()
        self.assertNotEqual(before['hostProcessId'],after['hostProcessId']);self.assertEqual(after,follows(literal,after,self.fixture.physical))
        self.assertGreater(after['installedBefore']['observation']['sequence'],before['installedAfter']['observation']['sequence'])
        changed=deepcopy(after);changed['tabletWebObserverAdmissionVersion']=1
        changed['installedBefore']=deepcopy(before['installedAfter'])
        with self.assertRaises(NativeUIError):validate(changed,self.fixture.physical)
    def test_verify_between_readonly_before_and_after_is_explicit_v2_not_literal_v1(self):
        first=self.fixture.admit();self.fixture.fixture.make().verify();last=self.fixture.admit()
        original=deepcopy(last);original['installedBefore']=deepcopy(first['installedBefore'])
        self.assertEqual(self.fixture.physical,validate(original,self.fixture.physical))
        original['tabletWebObserverAdmissionVersion']=1
        with self.assertRaises(NativeUIError):validate(original,self.fixture.physical)
    def test_counter_nonce_native_birth_prepare_bytes_and_source_rewrites_are_not_continuity(self):
        before=self.fixture.admit();self.fixture.fixture.make().verify();after=self.fixture.admit()
        row=after['installedBefore'];old=before['installedAfter'];obs=old['observation']
        for fields in ({'sequence':obs['sequence']},{'commandId':obs['commandId']},{'capturedEpochMs':obs['capturedEpochMs']-1},
                       {'instance':'f'*32},{'preparedEpochMs':obs['preparedEpochMs']-1},
                       {'bundle':dict(obs['bundle'],bundleSha256='f'*64)}):
            mutated=deepcopy(row);mutated['observation'].update(fields)
            with self.subTest(fields=fields),self.assertRaises(NativeUIError):installed_forward(old,mutated)
        mutated=deepcopy(row);mutated['source']['instance']='f'*32
        with self.assertRaises(NativeUIError):installed_forward(old,mutated)


class TabletAcquisitionAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.fixture=source_tests.TabletWebSourceOwnerTests();self.fixture.setUpClass();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        admission=admission_tests.TabletWebAdmissionTests();admission.setUp();self.addCleanup(admission.doCleanups)
        self.proof=admission.admit();binding=deepcopy(source_tests.BINDING);scope={k:v for k,v in binding.items() if k!='processIdentity'}
        self.proof.update(binding=binding,scope=scope,acquisition=dict(hostBeforeEpochMs=self.fixture.boundary.host,hostAfterEpochMs=self.fixture.boundary.host,hostBeforeMonotonic=0.,hostAfterMonotonic=0.))
        for name in ('processBefore','processAfter'):self.proof[name]['pid']=31
        for name in ('installedBefore','installedAfter'):
            self.proof[name]['scope']=deepcopy(scope);self.proof[name]['process']['pid']=31;self.proof[name]['observation']['processId']=31
        validate(self.proof,binding)
    def test_actual_acquisition_admission_is_durable_before_any_native_query_and_pid_rewrite_fails(self):
        f=self.fixture
        source=TabletWebSourceOwner(f.root,source_tests.BINDING,source_tests.RUN,'actor',source_tests.ROOT,31,f.lock,lambda:True,
            epoch_ms=lambda:int(f.boundary.host+f.boundary.mono*1000),monotonic=lambda:f.boundary.mono,admission=self.proof)
        native=f.boundary.native();send=native.send;seen=[]
        def actual_send(query):
            pending=source.store.read()['pending'];self.assertEqual(2,pending['tabletWebAcquisitionVersion'])
            self.assertEqual(self.proof,pending['admission']);seen.append(query);return send(query)
        native.send=actual_send
        source.capture({name:f.boundary.reader(name) for name in source_tests.ORDER},native,f.boundary.phase,lambda:deepcopy(f.frame['browser']))
        self.assertEqual(2,len(seen));row=source.originals.read(source.originals.expand(source.state['records'][0]))
        self.assertEqual(self.proof,row['admission']);row['hostProcessId']+=1
        with self.assertRaises(NativeUIError):source._record(row,1,None)


if __name__=='__main__':unittest.main()
