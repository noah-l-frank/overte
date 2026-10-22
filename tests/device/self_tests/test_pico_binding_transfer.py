"""Actual private cursor/locks/OFDs; no Android process or SDK input executes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.device.openxr_input.adapter_session import PicoOpenXrAdapterSession,AdapterSessionError


class BindingTransferTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='pico-original-binding-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700);self.input_calls=[]
        self.session=PicoOpenXrAdapterSession(object(),'component-selector',self.root);self.session.begin('123:456')
        self.owners=[];self.addCleanup(lambda:[owner.close_host() for owner in self.owners])
        self.intents=[];self.intent=self.intents.append;self.before=lambda:None
        self.successor=dict(schemaVersion=1,processIdentity='789:999',sessionNonce='a'*64,nextSequence=1)
    def owner(self):
        owner=self.session.original_binding_transfer();self.owners.append(owner);return owner

    def test_exact_original_cursor_and_prepared_inode_are_preserved_before_single_atomic_replacement(self):
        owner=self.owner();original=owner.capture();state_path=self.session.state_path;raw=state_path.read_bytes()
        def intent(value):
            self.assertEqual(raw,state_path.read_bytes());self.assertEqual(original,value['original'])
            self.assertNotEqual(original['stamp']['inode'],value['prepared']['stamp']['inode']);self.intents.append(deepcopy(value))
            value['prepared']['state']['processIdentity']='foreign-callback-edit'
        value=owner.replace(self.successor,intent=intent,before_publish=self.before)
        self.assertEqual(original,value['original']);self.assertEqual(self.successor,value['current']['state'])
        self.assertEqual(self.successor,owner.session._load());self.assertEqual(1,len(self.intents))
        self.assertEqual(self.intents[0]['prepared']['stamp']['inode'],value['current']['stamp']['inode'])
        self.assertEqual(value,owner.reconcile());self.assertEqual(1,len(self.intents));self.assertEqual([],self.input_calls)
        value['current']['state']['processIdentity']='foreign-return-edit'
        self.assertEqual(self.successor,owner.session._load())

    def test_unknown_foreign_original_inode_or_cursor_advancement_is_never_replaced(self):
        for fault in ('inode','advance'):
            if fault!='inode':self.setUp()
            owner=self.owner();path=self.session.state_path
            if fault=='inode':
                raw=path.read_bytes();path.rename(path.with_name('original.json'));path.write_bytes(raw);path.chmod(0o600)
            else:
                current=self.session._load();self.session._save(current|dict(nextSequence=2))
            before=path.read_bytes()
            with self.subTest(fault=fault),self.assertRaises(AdapterSessionError):owner.replace(self.successor,intent=self.intent,before_publish=self.before)
            self.assertEqual(before,path.read_bytes());self.assertEqual([],self.intents)

    def test_lost_intent_receipt_never_publishes_or_replays_and_retains_prepared_original(self):
        owner=self.owner();before=self.session.state_path.read_bytes()
        def lost(value):self.intents.append(value);raise OSError('Original intent landed; acknowledgement lost')
        with self.assertRaises(AdapterSessionError):owner.replace(self.successor,intent=lost,before_publish=self.before)
        self.assertEqual(before,self.session.state_path.read_bytes());self.assertTrue(owner.temporary.exists())
        with self.assertRaises(AdapterSessionError):owner.replace(self.successor,intent=lost,before_publish=self.before)
        with self.assertRaises(AdapterSessionError):owner.reconcile()
        self.assertEqual(1,len(self.intents));self.assertEqual(before,self.session.state_path.read_bytes())

    def test_lost_publication_receipt_reconciles_only_matching_original_held_successor_without_another_replace(self):
        owner=self.owner();replace=os.replace;calls=[]
        def lost(source,target):
            calls.append((source,target));replace(source,target);raise OSError('Original rename applied; return lost')
        with patch('os.replace',lost),self.assertRaises(AdapterSessionError):
            owner.replace(self.successor,intent=self.intent,before_publish=self.before)
        self.assertEqual(self.successor,self.session._load());self.assertEqual(1,len(calls))
        with patch('os.replace',side_effect=AssertionError('No replacement replay')):
            value=owner.reconcile()
            self.assertEqual(self.successor,value['current']['state'])
            self.assertEqual(value,owner.replace(self.successor,intent=self.intent,before_publish=self.before))
        self.assertEqual(1,len(self.intents))
        with self.assertRaises(AdapterSessionError):owner.replace(self.successor,intent=lambda _:None,before_publish=self.before)

    def test_unapplied_or_byte_copied_publication_can_never_become_passive_owned_success(self):
        for copied in (False,True):
            if copied:self.setUp()
            owner=self.owner();replace=os.replace
            def unknown(source,target):
                if copied:replace(source,target)
                raise OSError('Publication unknown')
            with patch('os.replace',unknown),self.assertRaises(AdapterSessionError):
                owner.replace(self.successor,intent=self.intent,before_publish=self.before)
            if copied:
                path=self.session.state_path;raw=path.read_bytes();path.rename(path.with_name('actual-successor.json'))
                path.write_bytes(raw);path.chmod(0o600)
            before=self.session.state_path.read_bytes()
            with self.subTest(copied=copied),self.assertRaises((AdapterSessionError,ValueError)):owner.reconcile()
            self.assertEqual(before,self.session.state_path.read_bytes());self.assertEqual(1,len(self.intents))

    def test_last_host_age_hook_after_slow_intent_or_final_file_guard_prevents_replacement(self):
        for fault in ('intent','file-guard'):
            if fault!='intent':self.setUp()
            owner=self.owner();clock=[0.];original=owner.snapshot;calls=[0];before=self.session.state_path.read_bytes()
            def intent(value):
                self.intents.append(value)
                if fault=='intent':clock[0]+=2
            def snapshot(*args):
                value=original(*args);calls[0]+=1
                if fault=='file-guard' and calls[0]==4:clock[0]+=2
                return value
            def guard():
                if clock[0]>1.5:raise ValueError('Original actual-source host anchor expired')
            owner.snapshot=snapshot
            with (self.subTest(fault=fault),patch('os.replace',side_effect=AssertionError('Expired publication forbidden')),
                    self.assertRaises(AdapterSessionError)):owner.replace(self.successor,intent=intent,before_publish=guard)
            self.assertEqual(before,self.session.state_path.read_bytes());self.assertEqual(1,len(self.intents))

    def test_closed_successor_rejects_reused_nonce_pid_noninitial_sequence_and_extra_fields_before_intent(self):
        original=self.session._load()
        for edit in (dict(sessionNonce=original['sessionNonce']),dict(processIdentity=original['processIdentity']),
                dict(nextSequence=2),dict(nextSequence=True),dict(schemaVersion=True),dict(expected='retired')):
            owner=self.owner();before=self.session.state_path.read_bytes()
            with self.subTest(edit=edit),self.assertRaises(AdapterSessionError):
                owner.replace(self.successor|edit,intent=self.intent,before_publish=self.before)
            self.assertEqual(before,self.session.state_path.read_bytes());self.assertEqual([],self.intents)
            self.assertIsNone(owner.temporary)

    def test_duplicate_original_keys_or_hardlinked_state_cannot_be_captured_as_owned(self):
        path=self.session.state_path;raw=path.read_bytes()
        path.write_bytes(raw[:-2]+b',"nextSequence":1}\n');path.chmod(0o600)
        with self.assertRaises(AdapterSessionError):self.owner()
        path.write_bytes(raw);path.chmod(0o600);other=path.with_name('foreign-hardlink.json');os.link(path,other)
        with self.assertRaises(AdapterSessionError):self.owner()
        self.assertEqual(raw,path.read_bytes());self.assertEqual([],self.intents)

    def test_recycled_same_inode_original_fd_is_foreign_and_never_closed_by_cleanup(self):
        owner=self.owner();descriptor,anchor=owner.old.fd,owner.old.anchor
        os.close(descriptor);foreign=os.open(self.session.state_path,os.O_RDONLY|os.O_CLOEXEC)
        try:
            self.assertEqual(descriptor,foreign)
            with self.assertRaises(AdapterSessionError):owner.replace(self.successor,intent=self.intent,before_publish=self.before)
            self.assertFalse(owner.close_host());self.assertEqual(self.session.state_path.stat().st_ino,os.fstat(foreign).st_ino)
            self.assertEqual([],self.intents)
        finally:os.close(foreign);os.close(anchor)


if __name__=='__main__':unittest.main()
