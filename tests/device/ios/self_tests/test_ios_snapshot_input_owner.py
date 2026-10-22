"""Actual private journals/normal transport, modeled native UI and event source."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters import normal_input,snapshot_capture_controls as controls
from ios.adapters.snapshot_input_owner import SnapshotInputOwner,SnapshotInputPending
from ios.self_tests.test_ios_snapshot_inputs import Native,RUN


class SnapshotInputOwnerTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup);self.root=Path(folder.name);self.root.chmod(0o700)
        self.native=Native();self.normal=self.native.input();self.store=PrivateFeatureState(self.root/'ios-snapshot-primary-inputs.json')
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock')
        self.binding=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity='42',sessionId='owned-session',generation=0,targetFingerprint='c'*64)
        transport=patch.object(normal_input,'urlopen',self.native.post);transport.start();self.addCleanup(transport.stop)
    def owner(self):return SnapshotInputOwner(self.store,self.lock,self.binding,RUN,'primary',self.normal,lambda:True)
    def reserve(self,owner):
        ref=controls.project(self.normal.capture());return owner.reserve('snapshot.capture',ref)
    def edits(self):return [q for q in self.native.requests if q['operation']=='edit']

    def test_exact_native_uuid_is_durable_before_real_edit_and_delivery_never_claims_capture(self):
        with self.lock.held():
            owner=self.owner();command=self.reserve(owner);self.assertEqual('reserved',self.owner().state['events'][0]['phase'])
            actual=self.native.post
            def boundary(request,timeout):
                import json
                query=json.loads(request.data)
                if query['operation']=='edit':
                    stored=self.owner().state['events'][0];self.assertEqual('issued',stored['phase']);self.assertEqual(command,stored['command'])
                return actual(request,timeout)
            with patch.object(normal_input,'urlopen',boundary):result=owner.send()
            self.assertEqual(dict(productOutcomeRequired=True),result);self.assertEqual('delivered',self.owner().state['events'][0]['phase'])
            with self.assertRaises(SnapshotInputPending):owner.send()
        self.assertEqual(1,len(self.edits()));self.assertEqual(command,self.edits()[0]['input'])

    def test_unknown_return_survives_reconstruction_and_passive_source_recovers_without_second_send(self):
        with self.lock.held():
            owner=self.owner();self.reserve(owner);self.native.lost=True
            with self.assertRaises(NativeUIError):owner.send()
            before=len(self.native.requests);restored=self.owner();self.assertEqual('issued',restored.state['events'][0]['phase'])
            with self.assertRaises(SnapshotInputPending):restored.send()
            packet=self.native.reader().read(RUN);restored.recover(packet)
            recovered=self.owner();self.assertEqual('delivered',recovered.state['events'][0]['phase']);self.assertIsNotNone(recovered.state['events'][0]['proof'])
            self.assertEqual(before,len(self.native.requests))
        self.assertEqual(1,len(self.edits()))

    def test_lost_saved_proof_return_is_adopted_locally_without_native_read_or_file_rewrite(self):
        with self.lock.held():
            owner=self.owner();self.reserve(owner);self.native.lost=True
            with self.assertRaises(NativeUIError):owner.send()
            packet=self.native.reader().read(RUN);original=owner.storage
            def lost(kind,value):
                original(kind,value)
                if value['phase']=='saved':raise OSError('Original saved result lost')
            owner.storage=lost
            with self.assertRaises(OSError):owner.recover(packet)
            stored=self.owner();record=stored.state['storage']['1'];path=stored.proof_store().path(record);before=path.stat()
            queries=len(self.native.queries);inputs=len(self.native.requests);stored.recover()
            self.assertEqual(queries,len(self.native.queries));self.assertEqual(inputs,len(self.native.requests))
            self.assertEqual((before.st_ino,before.st_mtime_ns),(path.stat().st_ino,path.stat().st_mtime_ns))
            self.assertEqual('delivered',self.owner().state['events'][0]['phase'])

    def test_interrupted_opened_proof_keeps_original_inode_bytes_and_blocks_any_input_replay(self):
        with self.lock.held():
            owner=self.owner();self.reserve(owner);self.native.lost=True
            with self.assertRaises(NativeUIError):owner.send()
            packet=self.native.reader().read(RUN);original=owner.storage
            def lost(kind,value):
                original(kind,value)
                if value['phase']=='opened':raise OSError('Original write interrupted')
            owner.storage=lost
            with self.assertRaises(OSError):owner.recover(packet)
            restored=self.owner();path=restored.proof_store().path(restored.state['storage']['1']);inode=path.stat().st_ino
            self.assertEqual(b'',path.read_bytes())
            with self.assertRaises(NativeUIError):restored.recover()
            with self.assertRaises(SnapshotInputPending):restored.send()
            with self.assertRaises(NativeUIError):self.reserve(restored)
            self.assertEqual(b'',path.read_bytes());self.assertEqual(inode,path.stat().st_ino)
            self.assertEqual('issued',self.owner().state['events'][0]['phase'])
        self.assertEqual(1,len(self.edits()))

    def test_wrong_original_root_and_negative_receipt_cannot_resolve_or_discard_issued_owner(self):
        with self.lock.held():
            owner=self.owner();self.reserve(owner);self.native.lost=True
            with self.assertRaises(NativeUIError):owner.send()
            packet=self.native.reader().read(RUN);before=self.store.path.read_bytes()
            for fault in ('root','rejected','partial'):
                changed=deepcopy(packet)
                if fault=='root':changed['source']['events'][0]['details']['root']['rootId']='11111111-2222-4333-8444-888888888888'
                elif fault=='rejected':changed['source']['events'][-1]['details']['status']['performed']=False
                else:changed['source']['events'].pop()
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):owner.recover(changed)
                self.assertEqual(before,self.store.path.read_bytes())
        self.assertEqual(1,len(self.edits()))

    def test_changed_root_blocks_before_real_input_and_new_root_cannot_extend_an_old_owner(self):
        with self.lock.held():
            owner=self.owner();self.reserve(owner);actual=self.native.observed
            def replaced():
                value=actual();value['controls'][0]['snapshotRootId']='11111111-2222-4333-8444-888888888888';return value
            self.native.observed=replaced
            with self.assertRaises(NativeUIError):owner.send()
            self.assertEqual('reserved',self.owner().state['events'][0]['phase']);self.assertEqual([],self.edits())
            self.native.observed=actual;owner.send();self.native.observed=replaced
            with self.assertRaises(NativeUIError):self.reserve(owner)

    def test_stored_recovery_proof_is_inode_and_byte_bound_and_never_an_ack_only_cache(self):
        with self.lock.held():
            owner=self.owner();self.reserve(owner);self.native.lost=True
            with self.assertRaises(NativeUIError):owner.send()
            owner.recover(self.native.reader().read(RUN));proof=owner.state['events'][0]['proof'];store=owner.proof_store();path=store.path(store.expand(proof))
            original=path.read_bytes();path.write_bytes(original.replace(b'"performed":true',b'"performed":false'))
            with self.assertRaises(NativeUIError):self.owner()
            path.write_bytes(original);temporary=path.with_name('replacement.json');temporary.write_bytes(original);temporary.chmod(0o600);os.replace(temporary,path)
            with self.assertRaises(NativeUIError):self.owner()

    def test_historical_original_reader_never_constructs_or_queries_native_sdk_and_cannot_send(self):
        with self.lock.held():
            owner=self.owner();self.reserve(owner);self.native.lost=True
            with self.assertRaises(NativeUIError):owner.send()
            owner.recover(self.native.reader().read(RUN));expected=owner.validate_original(1)
            def forbidden(*_args,**_kwargs):raise AssertionError('Historical proof touched SDK')
            self.native.post=self.native.execute=self.normal._check=forbidden
            history=SnapshotInputOwner.history(self.store,self.lock,self.binding,RUN,'primary')
            self.assertEqual(expected,history.validate_original(1));self.assertIsNone(history.native)
            with self.assertRaises(NativeUIError):history.send()


if __name__=='__main__':unittest.main()
