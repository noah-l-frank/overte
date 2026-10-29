"""Passive round boundaries only; no SDK, product graph or clock flow runs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch
import unittest
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.snapshot_capture_owner import IOSSnapshotCaptureOwner
from ios.adapters.snapshot_photos_archive import SnapshotPhotosArchive
from ios.adapters import snapshot_photos_end_round as source


class SnapshotPhotosEndRoundContractTests(unittest.TestCase):
    def files(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);root=Path(temporary.name)
        path=root/'original.json';path.write_bytes(b'{"original":true}');path.chmod(0o600)
        return root,path
    def test_same_bytes_replacement_inode_is_not_an_original_boundary(self):
        root,path=self.files();lease=source.InventoryLease((root,));replacement=root/'replacement';replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);replacement.replace(path)
        with self.assertRaises(NativeUIError):lease.finish()
    def test_byte_mutation_with_restored_mtime_still_fails_original_stat_and_bytes(self):
        root,path=self.files();lease=source.InventoryLease((root,));before=path.stat();path.write_bytes(b'{"original":fail}')
        os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns))
        with self.assertRaises(NativeUIError):lease.finish()
    def test_missing_or_additional_source_never_becomes_qualified_membership(self):
        root,path=self.files();lease=source.InventoryLease((root,));extra=root/'unowned.json';extra.write_bytes(b'{}')
        with self.assertRaises(NativeUIError):lease.check()
        extra.unlink();path.unlink()
        with self.assertRaises(NativeUIError):lease.check()
    def test_original_capture_decoder_replacement_is_rejected(self):
        with patch.object(IOSSnapshotCaptureOwner,'archive',classmethod(lambda *_a,**_k:None)),self.assertRaises(NativeUIError):source.parser_identity()
    def test_guard_or_historical_capture_method_replacement_is_rejected(self):
        with patch.object(SnapshotPhotosArchive,'guard',lambda *_:True),self.assertRaises(NativeUIError):source.parser_identity()
        with patch.object(SnapshotPhotosArchive,'capture',lambda *_:None),self.assertRaises(NativeUIError):source.parser_identity()
    def test_prohibiting_private_writers_does_not_replace_any_reader_or_guard(self):
        with patch.object(PrivateFeatureState,'write',side_effect=AssertionError('Historical writer forbidden')):
            source.parser_identity()
    def test_private_original_reader_replacement_cannot_be_adopted(self):
        with patch.object(PrivateFeatureState,'read',lambda *_:None),self.assertRaises(NativeUIError):source.parser_identity()
    def test_changed_scope_header_cannot_reuse_a_passive_round(self):
        root,_path=self.files();header={'binding':{'processIdentity':'84'}};graph=SimpleNamespace(previous={'version':1},scope=lambda:deepcopy(header))
        round=object.__new__(source.DecodeRound);round.graph=graph;round.started=time.monotonic();round.header=deepcopy(graph.previous)
        round.scope=deepcopy(header);round.parsers=source.parser_identity();round.lease=source.InventoryLease((root,))
        self.assertTrue(round.check());header['binding']['processIdentity']='85'
        with self.assertRaises(NativeUIError):round.check()
    def test_exception_and_nested_round_boundary_restore_context_without_reuse(self):
        self.assertIsNone(source._ACTIVE.get());outer=object();inner=object()
        with self.assertRaisesRegex(RuntimeError,'declared boundary'):
            with source._entered(outer):
                with source._entered(inner):self.assertIs(inner,source._ACTIVE.get())
                self.assertIs(outer,source._ACTIVE.get());raise RuntimeError('declared boundary')
        self.assertIsNone(source._ACTIVE.get())
        with self.assertRaises(NativeUIError):
            with source.scope(object()):self.fail('Untyped graph admitted')
        self.assertIsNone(source._ACTIVE.get())


if __name__=='__main__':unittest.main()
