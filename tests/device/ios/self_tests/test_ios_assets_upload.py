"""Ordinary original-QML upload journey; native/Qt/server boundaries modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import canonical,pack,unpack
from ios.adapters.assets_runtime import IOSAssetsRuntime
from ios.self_tests.assets_upload_fixture import Fixture,RUN,TICKET,URL


class AssetsUploadTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        self.path=Path(directory.name);self.path.chmod(0o700);self.f=Fixture(self.path);self.addCleanup(self.f.close)
        self.b=self.f.boundary;self.f.start();self.owner=self.f.owner();self.owner.reserve()

    def destination(self):self.owner.review();self.owner.destination()
    def uploaded(self):self.destination();self.owner.start_upload();return self.owner.uploaded()

    def test_original_qml_companions_primary_destination_upload_and_independent_bytes_then_client_cleanup(self):
        result=self.uploaded();self.assertEqual('uploaded',self.owner.state['phase']);self.assertEqual(1,self.b.host_state['uploads'])
        self.assertEqual({'main.gltf','mesh/triangle.bin','textures/checker.png'},{row['relativePath'] for row in result['files']})
        self.assertEqual('inventory',self.f.replies.proof('upload-before')['kind']);self.assertEqual([],self.f.replies.proof('upload-before')['mappings'])
        for row in result['files']:
            self.assertEqual(self.b.reads.data['/e2e-'+RUN+'/'+row['relativePath']],__import__('base64').b64decode(row['body']['base64']))
        packets=[self.owner.originals.read(self.owner.originals.expand(ref)) for ref in self.owner.state['frames']]
        self.assertTrue(all(len(packet['clocks'])>=2 and packet['queries'] for packet in packets))
        final=self.owner.cleanup();self.assertEqual({'exists':False,'files':[]},final['source']['files']);self.assertFalse(self.b.root.exists())
        self.assertEqual('retired',self.owner.state['phase']);self.assertEqual('closed',self.f.replies.state['phase'])
        # Client input/read retirement deliberately leaves independently read
        # server mappings present; this is not whole-feature server cleanup.
        self.assertEqual(3,len(self.b.reads.data));self.assertEqual('retired',self.f.owner().state['phase'])

    def test_ignored_review_ack_cannot_create_a_manifest_or_upload_and_can_be_aborted(self):
        self.b.configure(ignore='asset-file.select')
        with self.assertRaises(NativeUIError):self.owner.review()
        self.assertEqual('ready',self.owner.state['phase']);self.assertEqual(0,self.b.host_state['uploads'])
        pending=[row for row in self.owner.state['inputs'] if row['resolvedBy'] is None];self.assertEqual(1,len(pending));self.assertIsNotNone(pending[0]['receipt'])
        self.owner.cleanup(abort=True);self.assertTrue(self.owner.state['aborted']);self.assertEqual('retired',self.owner.state['phase']);self.assertEqual({},self.b.reads.data)

    def test_lost_destination_accept_return_observes_completion_without_a_second_upload(self):
        self.destination();self.b.configure(lost='assets.destination.accept')
        with self.assertRaises(NativeUIError):self.owner.start_upload()
        count=len(self.b.inputs);owner=self.f.owner();result=owner.uploaded()
        self.assertEqual(count,len(self.b.inputs));self.assertEqual(1,self.b.host_state['uploads']);self.assertEqual(3,len(result['files']))
        self.assertEqual(1,sum(row['slot']=='accept-destination' for row in owner.state['inputs']));owner.cleanup()

    def test_ignored_accept_never_substitutes_its_ack_for_upload_or_mapping_evidence(self):
        self.destination();self.b.configure(ignore='assets.destination.accept')
        with self.assertRaises(NativeUIError):self.owner.start_upload()
        with self.assertRaises(NativeUIError):self.owner.uploaded()
        self.assertEqual('starting',self.owner.state['phase']);self.assertEqual(0,self.b.host_state['uploads']);self.assertEqual({},self.b.reads.data)
        self.owner.cleanup(abort=True);self.assertEqual('retired',self.owner.state['phase'])

    def test_intervening_actual_destination_text_change_invalidates_accept_before_delivery(self):
        self.destination();actual=self.f.input.assets_input
        def changed(identifier,*args,**kwargs):
            if identifier=='assets.destination.accept':
                # Explicit external-user boundary: type into the already
                # focused rendered editor before the owner's final recapture.
                self.b.exchange(dict(op='input',id='assets.destination',action='replace',text='/foreign/'))
            return actual(identifier,*args,**kwargs)
        self.f.input.assets_input=changed
        with self.assertRaises(NativeUIError):self.owner.start_upload()
        self.assertEqual(0,self.b.host_state['uploads']);entry=next(row for row in self.owner.state['inputs'] if row['slot']=='accept-destination')
        self.assertIsNone(entry['command']);self.assertIsNone(entry['receipt']);self.assertEqual({},self.b.reads.data)
        self.owner.cleanup(abort=True);self.assertEqual('retired',self.owner.state['phase'])

    def test_an_existing_destination_mapping_blocks_accept_before_upload(self):
        self.destination();self.b.reads.data['/e2e-'+RUN+'/foreign.txt']=b'preexisting original server bytes'
        with self.assertRaises(NativeUIError):self.owner.start_upload()
        self.assertEqual(0,self.b.host_state['uploads']);self.assertFalse(any(row['slot']=='accept-destination' for row in self.owner.state['inputs']))
        self.owner.cleanup(abort=True);self.assertEqual({'/e2e-'+RUN+'/foreign.txt':b'preexisting original server bytes'},self.b.reads.data)

    def test_actual_weak_consumer_blocks_local_file_release_after_upload(self):
        self.uploaded();self.b.hold_consumer(pending=1)
        with self.assertRaises(NativeUIError):self.owner.cleanup()
        self.assertEqual('page-dead',self.owner.state['phase']);self.assertTrue(self.b.root.exists());self.assertEqual('staged',self.f.files.state['phase'])
        self.assertFalse(any(row['operation']=='release' for row in self.b.requests))

    def test_changed_immutable_original_is_rejected_without_new_input_or_queries(self):
        self.owner.capture();ref=self.owner.state['frames'][0];path=self.owner.originals.path(self.owner.originals.expand(ref))
        path.write_bytes(path.read_bytes()+b' ');count=len(self.b.inputs);queries=len(self.b.native_clock.commands)
        with self.assertRaises(NativeUIError):self.f.owner()
        self.assertEqual(count,len(self.b.inputs));self.assertEqual(queries,len(self.b.native_clock.commands))

    def test_rehashed_foreign_native_history_is_revalidated_in_live_and_restored_owners(self):
        self.owner.capture();saved=self.f.upload_store.read();state=unpack(saved['payload'])[0];reference=state['frames'][0]
        body=json.loads(self.owner.originals.path(self.owner.originals.expand(reference)).read_text())
        body['frame']['clocks'][-1]['sequence']=body['frame']['clocks'][0]['sequence'];raw=canonical(body)
        changed=dict(reference,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
        path=self.owner.originals.path(self.owner.originals.expand(changed));path.write_bytes(raw);path.chmod(0o600);info=path.stat();changed.update(device=info.st_dev,inode=info.st_ino)
        state['frames'][0]=changed;forged=dict(saved,payload=pack([state]));self.f.upload_store.write(forged,saved)
        queries=len(self.b.native_clock.commands)
        with self.assertRaises(NativeUIError):self.owner.decode(forged)
        with self.assertRaises(NativeUIError):self.f.owner()
        self.assertEqual(queries,len(self.b.native_clock.commands))

    def test_a_cached_original_never_reuses_the_live_native_guard(self):
        self.owner.capture();queries=len(self.b.native_clock.commands);inputs=len(self.b.inputs);self.b.live=False
        with self.assertRaises(NativeUIError):self.owner.capture()
        self.assertEqual(queries,len(self.b.native_clock.commands));self.assertEqual(inputs,len(self.b.inputs))

    def test_a_cached_original_never_substitutes_for_a_fresh_nonce_bound_clock(self):
        self.owner.capture();queries=len(self.b.native_clock.commands);self.b.native_clock.ignored=True
        with self.assertRaises(NativeUIError):self.owner.capture()
        self.assertEqual(queries+1,len(self.b.native_clock.commands));self.assertEqual(1,len(self.owner.state['frames']))
        self.assertIsNotNone(self.owner.state['pending']);self.assertIsNone(self.owner.state['pending']['original'])

    def test_lost_local_release_return_recovers_original_absence_without_second_release(self):
        self.uploaded();self.b.lost='release'
        with self.assertRaises(NativeUIError):self.owner.cleanup()
        self.assertEqual('releasing',self.owner.state['phase']);self.assertEqual('releasing',self.f.files.state['phase']);self.assertFalse(self.b.root.exists())
        final=self.owner.cleanup();self.assertEqual({'exists':False,'files':[]},final['source']['files'])
        self.assertEqual(1,sum(row['operation']=='release' for row in self.b.requests));self.assertEqual('retired',self.owner.state['phase'])


class AssetsUploadRuntimeTests(unittest.TestCase):
    """Actual runtime orchestration; only its candidate/source factory is modeled.

    Separate AssetsRuntimeTests exercise that factory through its real existing
    session/HTTP/AFC paths. No assembled test claims native/device qualification.
    """
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup);self.path=Path(directory.name);self.path.chmod(0o700)
        self.f=Fixture(self.path);self.addCleanup(self.f.close);self.b=self.f.boundary;self.owner=self.f.owner()
        self.runtime=IOSAssetsRuntime(SimpleNamespace(_candidate_guard=lambda:True,_binding=lambda:None),monotonic=self.b.monotonic)
        self.parts=dict(owned_files=self.f.files,picker=self.f.picker,owned_replies=self.f.replies,upload=self.owner,check=self.owner.guard)
        self.enterContext(patch.object(self.runtime,'_assets_components',return_value=self.parts))

    def invoke(self):return self.runtime._assets_upload_readback('test-only',RUN,'primary',URL,TICKET,self.f.lock)

    def test_actual_runtime_assembles_original_qml_upload_independent_readback_and_client_retirement(self):
        result=self.invoke();self.assertEqual(3,len(result['files']));self.assertEqual(1,self.b.host_state['uploads'])
        self.assertEqual('retired',self.owner.state['phase']);self.assertEqual('retired',self.f.files.state['phase']);self.assertEqual('closed',self.f.replies.state['phase'])
        self.assertEqual([],self.runtime.cleanup_errors);self.assertEqual(3,len(self.b.reads.data))

    def lost(self,*,lose_guard=False):
        errors=[];deliver=self.f.input.deliver
        def record(command,**kwargs):
            try:return deliver(command,**kwargs)
            except BaseException as error:
                errors.append(error)
                if lose_guard:self.b.live=False
                raise
        self.f.input.deliver=record;self.b.configure(lost='assets.destination.accept');return errors

    def test_original_lost_delivery_error_survives_successful_cleanup_without_another_upload(self):
        errors=self.lost()
        with self.assertRaises(NativeUIError) as caught:self.invoke()
        self.assertIs(errors[0],caught.exception);self.assertEqual([],self.runtime.cleanup_errors);self.assertEqual(1,self.b.host_state['uploads'])
        self.assertEqual('retired',self.owner.state['phase']);self.assertFalse(self.b.root.exists());self.assertEqual(3,len(self.b.reads.data))

    def test_secondary_guard_loss_does_not_replace_original_error_or_erase_issued_upload(self):
        errors=self.lost(lose_guard=True)
        with self.assertRaises(NativeUIError) as caught:self.invoke()
        self.assertIs(errors[0],caught.exception);self.assertEqual(1,len(self.runtime.cleanup_errors));self.assertIsNot(errors[0],self.runtime.cleanup_errors[0])
        saved=unpack(self.f.upload_store.read()['payload'])[0];self.assertEqual('starting',saved['phase']);self.assertEqual('staged',self.f.files.state['phase'])
        pending=[entry for entry in saved['inputs'] if entry['resolvedBy'] is None];self.assertEqual(['accept-destination'],[entry['slot'] for entry in pending])
        self.assertIsNotNone(pending[0]['command']);self.assertIsNone(pending[0]['receipt']);self.assertTrue(self.b.root.exists());self.assertEqual(1,self.b.host_state['uploads'])
