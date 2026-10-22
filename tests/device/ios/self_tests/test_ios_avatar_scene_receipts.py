"""Real private file ownership and Qt originals under closed marker profiles."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from adapters.original_marker_file_receipts import OriginalMarkerFileReceipts
from adapters.original_marker_pointers import OriginalMarkerPointers
from ios.adapters.avatar_file_receipts import IOSAvatarFileReceipts,receipt as file_receipt
from ios.adapters.avatar_marker_files import OwnedAvatarMarkerFiles
from ios.adapters.avatar_pointers import IOSAvatarPointers,receipt as pointer_receipt
from ios.self_tests.test_ios_emote_sources import BINDING,RUN
from self_tests.test_native_script_files import Boundary as Files
from self_tests.test_native_feature_observation import Boundary as Native
from ios.self_tests.test_ios_pointer_state import NativePointerBoundary
from ios.self_tests import test_ios_pointer_state as qt_fixture


class AvatarSceneReceiptTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.root.chmod(0o700);self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock')
        held=self.lock.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        self.native=Native();self.native.mutate=lambda packet:packet.update(processId=31)
        self.files_boundary=Files(self.root);self.files_boundary.root=self.root/('feature-script-'+RUN);self.files=self.files_boundary.native(ios=True)
        self.owned=OwnedAvatarMarkerFiles(self.files,PrivateFeatureState(self.root/'owned.json'),BINDING)
        self.ownership=self.owned.reserve_marker(RUN,'http://fixture.invalid/feature-fixture/v1/runs/'+RUN+'/','a'*32)
        self.owned.stage_reserved();tone=patch.object(qt_fixture,'EPOCH',20000);tone.start();self.addCleanup(tone.stop)
        self.qt=NativePointerBoundary()
        def native_packet(packet):
            packet.update(processId=31,capturedEpochMs=self.qt.now,requestedEpochMs=self.qt.now)
            packet['animationFence']['requestedEpochMs']=self.qt.now
        self.native.mutate=native_packet
        send=self.qt.send
        def sending(query):send(query);self.qt.packet['processId']=31
        self.qt.send=sending

    def clock(self):return NativeFeatureObservation(self.native.send,self.native.original,lambda:self.qt.now,lambda:True,31,ios=True,
        native_clock_bound=False,monotonic=lambda:0.,sleep=lambda _:None)

    def file_owner(self):return IOSAvatarFileReceipts(PrivateFeatureState(self.root/'ios-avatar-primary-file-receipts.json'),self.root,BINDING,RUN,
        'primary',self.lock,lambda:True,native=self.clock(),files=self.files,epoch_ms=lambda:90000.,monotonic=lambda:0.)

    def pointer_owner(self):
        pointer=self.qt.reader();pointer.pid=31
        return IOSAvatarPointers(PrivateFeatureState(self.root/'ios-avatar-primary-pointers.json'),self.root,BINDING,RUN,'primary',self.lock,
            lambda:True,native=self.clock(),pointer=pointer,epoch_ms=lambda:90000.,monotonic=lambda:0.)

    def test_avatar_file_bytes_and_original_absence_survive_pure_historical_reconstruction(self):
        owner=self.file_owner();first=owner.capture('bytes',self.ownership);original=owner.original(first)
        self.assertIn('avatarMarkerFilesVersion',original['ownership']);self.assertIn('iosAvatarNativeFileReceiptVersion',original)
        self.assertTrue(owner.record_store(1).path.name.startswith('avatar-native-files-'))
        self.owned.release();last=owner.capture('absent',self.ownership);before=deepcopy(self.files_boundary.commands)
        archive=IOSAvatarFileReceipts.archive(owner.previous,store=owner.store,root=self.root,binding=BINDING,run=RUN,role='primary',lock=self.lock)
        self.assertEqual(dict(exists=False,files=[]),archive.original(last)['packet']['source'])
        with self.assertRaises(NativeUIError):archive.capture('absent',self.ownership)
        self.assertEqual(before,self.files_boundary.commands)
        for wrong in ('emote','unknown'):
            with self.assertRaises(NativeUIError):
                from adapters.original_marker_file_receipts import receipt
                receipt(original,root=self.root,binding=BINDING,run=RUN,role='primary',profile=wrong)

    def test_file_query_is_owned_before_send_and_unknown_return_is_never_resent(self):
        owner=self.file_owner();send=self.files.send
        def lost(query):
            self.assertEqual(query,owner.state['pending']['query']);self.assertIsNotNone(owner.store.read())
            send(query);raise OSError('Lost actual file source return')
        with patch.object(self.files,'send',side_effect=lost),self.assertRaises(NativeUIError):owner.capture('bytes',self.ownership)
        requests=deepcopy(self.files_boundary.commands);rebuilt=self.file_owner();rebuilt.abandon();self.assertEqual(requests,self.files_boundary.commands)
        current=rebuilt.capture('bytes',self.ownership)
        self.assertNotEqual(requests[-1]['commandId'],rebuilt.original(current)['query']['commandId'])

    def test_every_passive_native_clock_nonce_is_owned_before_send_and_lost_query_stays_abandoned(self):
        for factory in (self.file_owner,self.pointer_owner):
            owner=factory();send=owner.native.send
            def lost(query):
                self.assertEqual(query,owner.state['pending']['nativeQueries'][-1]['query'])
                self.assertIsNotNone(owner.store.read());send(query);raise OSError('Lost native clock query return')
            with patch.object(owner.native,'send',side_effect=lost),self.assertRaises(NativeUIError):
                if isinstance(owner,IOSAvatarPointers):owner.capture()
                else:owner.capture('bytes',self.ownership)
            queries=deepcopy(self.native.commands);again=factory();again.abandon();self.assertEqual(queries,self.native.commands)
            partial=again.abandoned(again.state['abandoned'][0]);self.assertEqual(queries[-1],partial['nativeQueries'][-1]['query'])
            if isinstance(again,IOSAvatarPointers):ref=again.capture()
            else:ref=again.capture('bytes',self.ownership)
            self.assertNotEqual(queries[-1]['commandId'],again.original(ref)['nativeQueries'][0]['query']['commandId'])

    def test_native_original_returned_before_interruption_remains_an_immutable_future_source_floor(self):
        owner=self.pointer_owner();read=owner.native.original;first=[]
        def lost():
            raw=read();value=__import__('json').loads(raw)
            if not first:first.append(value['requestId'])
            if value['requestId']==first[0]:value['instance']='f'*32
            return __import__('json').dumps(value)
        with patch.object(owner.native,'original',side_effect=lost),self.assertRaises(NativeUIError):owner.capture()
        rebuilt=self.pointer_owner();rebuilt.abandon();partial=rebuilt.abandoned(rebuilt.state['abandoned'][0])
        self.assertIn('ffffffff',partial['nativeQueries'][0]['raws'][0])
        with self.assertRaises(NativeUIError):rebuilt.capture()

    def test_bound_native_reader_with_unowned_inner_clock_source_is_refused(self):
        clock=self.clock();clock.native_clock_bound=True
        with self.assertRaises(NativeUIError):
            IOSAvatarPointers(PrivateFeatureState(self.root/'invalid-pointers.json'),self.root,BINDING,RUN,'primary',self.lock,
                lambda:True,native=clock,pointer=self.qt.reader(),epoch_ms=lambda:90000.,monotonic=lambda:0.)

    def test_avatar_pointer_preserves_actual_qt_source_and_closed_profile_namespace(self):
        owner=self.pointer_owner();ref=owner.capture();original=owner.original(ref);requests=deepcopy(self.qt.requests)
        self.assertIn('iosAvatarPointerReceiptVersion',original);self.assertTrue(owner.file(1).path.name.startswith('avatar-pointer-'))
        archived=IOSAvatarPointers.archive(owner.previous,store=owner.store,root=self.root,binding=BINDING,run=RUN,role='primary',lock=self.lock)
        self.assertEqual(original,archived.original(ref));self.assertEqual(requests,self.qt.requests)
        with self.assertRaises(NativeUIError):archived.capture()
        with self.assertRaises(NativeUIError):
            from adapters.original_marker_pointers import receipt
            receipt(original,BINDING,RUN,'primary',profile='emote')
        with self.assertRaises(NativeUIError):owner.closed(type('Scope',(),dict(PROFILE='emote'))())

    def test_pointer_query_unknown_return_retains_exact_nonce_without_resending_it(self):
        owner=self.pointer_owner();send=owner.pointer.send
        def lost(query):
            self.assertEqual(query,owner.state['pending']['query']);self.assertIsNotNone(owner.store.read())
            send(query);raise OSError('Lost actual pointer source return')
        with patch.object(owner.pointer,'send',side_effect=lost),self.assertRaises(NativeUIError):owner.capture()
        requests=deepcopy(self.qt.requests);again=self.pointer_owner();again.abandon();self.assertEqual(requests,self.qt.requests)
        ref=again.capture();self.assertNotEqual(requests[-1]['commandId'],again.original(ref)['query']['commandId'])


if __name__=='__main__':unittest.main()
