"""Independent literal Emote v1 writers and extracted owner regressions."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.native_clock_join import NativeClockAcquisition,digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_marker_file_receipts import OriginalMarkerFileReceipts
from adapters.original_marker_pointers import OriginalMarkerPointers
from adapters.script_feature.history import pack
from ios.adapters.emote_file_receipts import IOSEmoteFileReceipts
from ios.adapters.emote_pointers import IOSEmotePointers
from ios.self_tests import test_ios_emote_file_receipts as file_tests,test_ios_emote_pointers as pointer_tests,emote_pointer_fixture
from ios.self_tests.test_ios_emote_sources import BINDING,RUN


class LegacyFiles(OriginalMarkerFileReceipts):PROFILE='emote'
class LegacyPointers(OriginalMarkerPointers):PROFILE='emote'


class ExtractedFileRegressions(file_tests.FileReceiptsTests):
    def reader(self):
        old=super().reader()
        return LegacyFiles(old.store,old.root,old.binding,old.run,old.role,old.lock,old.guard,native=old.native,files=old.files,
            epoch_ms=old.epoch_ms,monotonic=old.monotonic)


class ExtractedPointerRegressions(pointer_tests.PointerOwnerTests):
    def setUp(self):
        replacement=patch.object(emote_pointer_fixture,'IOSEmotePointers',LegacyPointers);replacement.start();self.addCleanup(replacement.stop)
        super().setUp()


class FrozenEmoteV1WriterTests(unittest.TestCase):
    def test_literal_v1_file_writer_remains_readable_without_rewriting_or_transport(self):
        fixture=file_tests.FileReceiptsTests();fixture.setUp();self.addCleanup(fixture.tearDown);producer=fixture.reader()
        window=NativeClockAcquisition(producer.native,epoch_ms=producer.epoch_ms,monotonic=producer.monotonic);window.begin(producer.epoch_ms())
        producer.files.request('observe',RUN,fixture.ownership['ownerToken']);packet=deepcopy(producer.files.last_packet)
        join=window.finish(dict(files=packet),[('files','capturedEpochMs')])
        # Explicit frozen original writer/schema/filename. No extracted owner
        # creates this original or constructs its private metadata.
        value=dict(iosEmoteNativeFileReceiptVersion=1,runId=RUN,role='primary',binding=BINDING,kind='bytes',ownership=fixture.ownership,
            query=deepcopy(fixture.boundary.commands[-1]),packet=packet,clockJoin=join)
        path=PrivateFeatureState(fixture.root/('emote-native-files-'+RUN+'-primary-1.json'));path.write(value,None)
        reference=dict(index=1,sha256=digest(value));raw=dict(iosEmoteFileReceiptsVersion=1,runId=RUN,role='primary',binding=BINDING,
            artifactRoot=str(fixture.root),payload=pack([dict(records=[reference],pending=None,abandoned=[])]))
        fixture.store.write(raw,None);before=path.path.read_bytes();queries=deepcopy(fixture.boundary.commands)
        for owner_type in (LegacyFiles,IOSEmoteFileReceipts):
            owner=owner_type.archive(raw,store=fixture.store,root=fixture.root,binding=BINDING,run=RUN,role='primary',lock=fixture.lock)
            self.assertEqual(value,owner.original(reference))
        self.assertEqual(queries,fixture.boundary.commands);self.assertEqual(before,path.path.read_bytes());self.assertEqual(0o600,path.path.stat().st_mode&0o777)

    def test_literal_v1_pointer_writer_remains_readable_without_rewriting_or_transport(self):
        fixture=pointer_tests.PointerOwnerTests();fixture.setUp();self.addCleanup(fixture.doCleanups);owner=fixture.qt.owner()
        # A distinct directory avoids using the completed original created by
        # this test fixture's normal startup baseline.
        root=fixture.scope.root/'literal-pointer';root.mkdir(mode=0o700)
        window=NativeClockAcquisition(owner.native,epoch_ms=owner.epoch_ms,monotonic=owner.monotonic);window.begin(owner.epoch_ms())
        pointer=owner.pointer;packet=pointer.read(RUN)
        join=window.finish(dict(pointer=packet,pointerClock=dict(capturedEpochMs=packet['clockAfter']['epochMs'])),[('pointerClock','capturedEpochMs')])
        receipt=dict(iosEmotePointerReceiptVersion=1,runId=RUN,role='primary',binding=BINDING,query=deepcopy(fixture.qt.boundary.requests[-1]),packet=packet,clockJoin=join)
        value=dict(iosEmotePointerOriginalVersion=1,payload=pack([receipt]));path=PrivateFeatureState(root/('emote-pointer-'+RUN+'-primary-1.json'));path.write(value,None)
        reference=dict(index=1,sha256=digest(value));raw=dict(iosEmotePointersVersion=1,runId=RUN,role='primary',binding=BINDING,artifactRoot=str(root),
            payload=pack([dict(records=[reference],abandoned=[],pending=None)]));store=PrivateFeatureState(root/'owner.json');store.write(raw,None)
        before=path.path.read_bytes();queries=deepcopy(fixture.qt.boundary.requests)
        for owner_type in (LegacyPointers,IOSEmotePointers):
            archive=owner_type.archive(raw,store=store,root=root,binding=BINDING,run=RUN,role='primary',lock=fixture.scope.lock)
            self.assertEqual(receipt,archive.original(reference))
        self.assertEqual(queries,fixture.qt.boundary.requests);self.assertEqual(before,path.path.read_bytes());self.assertEqual(0o600,path.path.stat().st_mode&0o777)


if __name__=='__main__':unittest.main()
