"""Actual admission/private files and native-reader hooks, host models only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.tablet_web_context import TabletWebContext
from ios.self_tests import test_ios_tablet_web_admission as admission_tests
from self_tests import test_native_feature_observation as native_tests


class TabletWebContextTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');held=self.lock.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        self.admission=admission_tests.TabletWebAdmissionTests('test_actual_same_physical_binding_is_retained_without_new_session_native_query_or_record_write');self.admission.setUp();self.addCleanup(self.admission.doCleanups)
        self.proof=self.admission.admit();self.binding=self.admission.physical;self.native=native_tests.Boundary()
        def mutate(value):
            epoch=95000 if value['sequence']==1 else 100000
            def clocks(node):
                if type(node) is dict:
                    for key,child in node.items():
                        if key.endswith('EpochMs'):node[key]=epoch
                        else:clocks(child)
                elif type(node) is list:
                    for child in node:clocks(child)
            clocks(value);value['processId']=42
        self.native.mutate=mutate;self.native.send(dict(commandId='ios-'+'1'*32));self.setup=deepcopy(self.native.sample)
    def owner(self,**kwargs):
        return TabletWebContext(self.root,self.binding,'a'*32,'actor',self.lock,self.proof,self.setup,lambda:True,monotonic=lambda:0.,**kwargs)
    def reader(self):
        return NativeFeatureObservation(self.native.send,self.native.original,lambda:100000,lambda:True,42,ios=True,monotonic=lambda:0.,sleep=lambda _:None)
    def test_bootstrap_original_raw_precedes_interpretation_and_reconstructs_actual_native_birth(self):
        owner=self.owner();reader=self.reader();send,original=reader.send,reader.original;packet=owner.bootstrap(reader)
        self.assertIs(send,reader.send);self.assertIs(original,reader.original);self.assertEqual(self.setup['instance'],packet['instance'])
        self.assertEqual(2,len(self.native.commands));historical=self.owner(historical=True);self.assertEqual(packet,historical.original())
        with self.assertRaises(NativeUIError):historical.bootstrap(self.reader())
        with self.assertRaises(NativeUIError):owner.bootstrap(self.reader())
        self.assertEqual(2,len(self.native.commands))
    def test_safe_matching_wrong_pid_or_source_birth_stays_in_immutable_original_and_never_retries(self):
        for fault in ('pid','birth'):
            with self.subTest(fault=fault):
                root=self.root/fault;root.mkdir(mode=0o700);lock=ScriptSourceLock(root/'script-feature-sources.lock')
                with lock.held():
                    owner=TabletWebContext(root,self.binding,'a'*32,'actor',lock,self.proof,self.setup,lambda:True,monotonic=lambda:0.)
                    mutate=self.native.mutate
                    def wrong(value):
                        mutate(value);value['processId' if fault=='pid' else 'instance']=43 if fault=='pid' else '0'*32
                    self.native.mutate=wrong
                    with self.assertRaises(NativeUIError):owner.bootstrap(self.reader())
                    self.native.mutate=mutate;count=len(self.native.commands);rebuilt=TabletWebContext(root,self.binding,'a'*32,'actor',lock,self.proof,self.setup,lambda:True,monotonic=lambda:0.)
                    self.assertEqual('failed',rebuilt.state['status']);raw=rebuilt.originals.read(rebuilt.state['pending'])['rawJSON']
                    self.assertIn('"processId": 43' if fault=='pid' else '"instance": "'+'0'*32+'"',raw)
                    with self.assertRaises(NativeUIError):rebuilt.bootstrap(self.reader())
                    with self.assertRaises(NativeUIError):rebuilt.recover()
                    self.assertEqual(count,len(self.native.commands))
    def test_unknown_send_never_becomes_new_raw_host_artifact(self):
        owner=self.owner();reader=self.reader();send=reader.send
        def lost(query):send(query);raise OSError('Actual native query send return lost')
        reader.send=lost
        with self.assertRaises(NativeUIError):owner.bootstrap(reader)
        self.assertIsNone(owner.state['pending']);self.assertEqual([],list(self.root.glob('*-frame-*')))
        rebuilt=self.owner();count=len(self.native.commands)
        with self.assertRaises(NativeUIError):rebuilt.bootstrap(self.reader())
        self.assertEqual(count,len(self.native.commands))
    def test_private_or_unknown_native_fields_are_not_written_as_new_raw_host_artifacts(self):
        owner=self.owner();mutate=self.native.mutate
        def private(value):mutate(value);value['privateText']='Do not persist this unexpected field'
        self.native.mutate=private
        with self.assertRaises(NativeUIError):owner.bootstrap(self.reader())
        self.assertIsNone(owner.state['pending']);self.assertEqual([],list(self.root.glob('*-frame-*')))
        self.assertEqual(1,len(owner.state['unsafe']));self.assertEqual({'bytes','sha256'},set(owner.state['unsafe'][0]))
        rebuilt=self.owner();count=len(self.native.commands)
        with self.assertRaises(NativeUIError):rebuilt.bootstrap(self.reader())
        self.assertEqual(count,len(self.native.commands))

    def test_empty_opened_prefix_stays_owned_and_hardlink_cannot_be_adopted(self):
        owner=self.owner();intent=owner.originals.intent
        def opened(kind,value):
            intent(kind,value)
            if value['phase']=='opened':raise OSError('Actual opened empty bootstrap prefix')
        owner.originals.intent=opened
        with self.assertRaises(NativeUIError):owner.bootstrap(self.reader())
        rebuilt=self.owner();ref=rebuilt.state['pending'];self.assertEqual(0,rebuilt.state['inspection']['bytes'])
        path=rebuilt.originals.path(ref);self.assertEqual(b'',path.read_bytes())
        with self.assertRaises(NativeUIError):rebuilt.recover()
        os.link(path,self.root/'foreign-hardlink')
        with self.assertRaises(NativeUIError):self.owner(historical=True)

    def test_actual_complete_opened_raw_recovers_without_new_query_or_inode_rewrite(self):
        owner=self.owner();fsync=os.fsync;failed=[False]
        def flush(descriptor):
            if not failed[0] and 'tabletweb-bootstrap-frame-' in os.readlink('/proc/self/fd/'+str(descriptor)):
                failed[0]=True;raise OSError('Actual raw flush return lost')
            return fsync(descriptor)
        with patch('os.fsync',side_effect=flush),self.assertRaises(NativeUIError):owner.bootstrap(self.reader())
        rebuilt=self.owner();ref=deepcopy(rebuilt.state['pending']);self.assertEqual('opened',ref['phase']);self.assertTrue(rebuilt.state['inspection']['complete'])
        path=rebuilt.originals.path(ref);raw=path.read_bytes();before=path.stat();count=len(self.native.commands);packet=rebuilt.recover()
        self.assertEqual(raw,path.read_bytes());self.assertEqual(before,path.stat());self.assertEqual(count,len(self.native.commands));self.assertEqual(packet,self.owner(historical=True).original())


if __name__=='__main__':unittest.main()
