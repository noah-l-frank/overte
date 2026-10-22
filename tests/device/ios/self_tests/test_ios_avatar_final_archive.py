"""Actual immutable files/CAS/lost-return archive boundary, no feature verdict.

The small standalone decoder below checks its original data only. The paired
whole Avatar scene/account/UI proof remains the caller's separate obligation.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import secrets
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.witness import Journal
from ios.adapters.avatar_final_archive import IOSAvatarFinalArchive
from ios.self_tests.test_ios_avatar_input_owner import BINDING


class AvatarFinalArchiveTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.root.chmod(0o700)
        self.locks={role:ScriptSourceLock(self.root/('script-feature-sources.lock' if role=='primary' else 'actor-sources.lock')) for role in ('primary','actor')}
        for lock in self.locks.values():held=lock.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        self.run='a'*32;self.values={'first':dict(actual=secrets.token_hex(25000)),'second':dict(value=2),'missing':None}
        self.paths=[PrivateFeatureState(self.root/(name+'.json')) for name in self.values]
        for path,value in zip(self.paths,self.values.values()):
            if value is not None:path.write(value,None)
        self.store=PrivateFeatureState(self.root/('ios-avatar-primary-'+self.run+'-finalization.json'))
        journal=Journal(clock=lambda:1700000000000)
        with patch.object(secrets,'token_hex',return_value=self.run):journal.register('avatar-people')
        journal.activate(self.run,'b'*32,'cleanup');journal.close(self.run);self.phase=journal.phase(self.run,'c'*32);self.validations=[]
    def validate(self,copies):
        self.assertEqual({str(path.path):value for path,value in zip(self.paths,self.values.values())},copies)
        self.validations.append(deepcopy(copies))
    def owner(self):return IOSAvatarFinalArchive(self.store,self.root,BINDING,self.run,'primary',self.locks,self.paths,lambda:True,self.validate)
    def test_full_original_values_before_any_fixed_metadata_retirement_and_repeat_is_pure(self):
        owner=self.owner();owner.begin(self.phase);self.assertEqual(dict(performed=True),owner.retire())
        self.assertTrue(all(path.read() is None for path in self.paths));self.assertEqual('complete',owner.state['phase']);self.assertTrue(self.validations)
        copies=owner.copies();self.assertEqual(self.values['first'],copies[str(self.paths[0].path)])
        self.assertGreater(len(owner.snapshots().originals.path(owner.state['snapshots'][0]).read_bytes()),40000)
        rebuilt=self.owner();self.assertEqual(dict(performed=True),rebuilt.retire());self.assertEqual(copies,rebuilt.copies())
    def test_lost_source_discard_return_is_not_repeated_and_existing_original_remains_readable(self):
        owner=self.owner();owner.begin(self.phase);discard=PrivateFeatureState.discard;lost=[];calls=[]
        def deleting(store,old):
            calls.append(str(store.path));discard(store,old)
            if store.path==self.paths[0].path and not lost:lost.append(True);raise OSError('Lost fixed metadata discard return')
        with patch.object(PrivateFeatureState,'discard',deleting),self.assertRaises(OSError):owner.retire()
        self.assertIsNone(self.paths[0].read());rebuilt=self.owner()
        with patch.object(PrivateFeatureState,'discard',deleting):self.assertEqual(dict(performed=True),rebuilt.retire())
        self.assertEqual(1,calls.count(str(self.paths[0].path)));self.assertEqual(self.values['first'],rebuilt.copies()[str(self.paths[0].path)])
    def test_changed_source_cannot_be_retired(self):
        owner=self.owner();owner.begin(self.phase);self.paths[0].write(dict(changed=True),self.paths[0].read())
        with self.assertRaises(NativeUIError):owner.retire()
        self.assertIsNotNone(self.paths[1].read());self.assertEqual(0,owner.state['retired'])
    def test_hardlinked_original_refuses_retirement_before_any_source_discard(self):
        import os
        owner=self.owner();owner.begin(self.phase);owner.freeze();raw=owner.snapshots().originals.path(owner.state['snapshots'][0])
        os.link(raw,self.root/'unexpected-link')
        with self.assertRaises(NativeUIError):owner.retire()
        self.assertIsNotNone(self.paths[0].read());self.assertEqual(0,owner.state['retired'])

    def test_lost_copy_file_completion_is_adopted_without_reopening_source_or_rewriting_original(self):
        owner=self.owner();owner.begin(self.phase);write=self.store.write;lost=[]
        def saving(value,previous):
            write(value,previous)
            if owner.state['snapshots'] and owner.state['snapshots'][-1]['phase']=='saved' and not lost:
                lost.append(True);raise OSError('Lost completed immutable copy return')
        with patch.object(self.store,'write',saving),self.assertRaises(OSError):owner.freeze()
        descriptor=deepcopy(owner.state['snapshots'][-1]);path=owner.snapshots().originals.path(descriptor);before=(path.stat().st_ino,path.read_bytes())
        rebuilt=self.owner();self.assertEqual(dict(performed=True),rebuilt.retire())
        self.assertEqual(before,(path.stat().st_ino,path.read_bytes()));self.assertEqual(3,len(rebuilt.state['snapshots']))


if __name__=='__main__':unittest.main()
