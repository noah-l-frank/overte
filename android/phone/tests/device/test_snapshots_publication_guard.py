"""Actual host publication cannot replace fresh target or owner authority.

Native producers are explicit seams; real original bytes, private files,
journals, source reducers and publication/recovery code execute unchanged.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import tempfile
import unittest
from unittest.mock import patch

import test_snapshots_role as source
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError


class SnapshotPublicationGuardTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='snapshot-publication-guard-');self.addCleanup(temporary.cleanup)
        self.b=source.SnapshotRolesBoundary(temporary.name)
        self.current=True;self.guards=[]
        def guard():self.guards.append(self.current);need(self.current);return True
        self.b.feature.bound=guard

    def test_target_changes_after_real_binary_publication_cannot_commit_a_complete_frame(self):
        original=source.SnapshotsBinary.write
        def changed(engine,*args,**kwargs):
            result=original(engine,*args,**kwargs);self.current=False;return result
        with self.b.role() as role:
            with patch.object(source.SnapshotsBinary,'write',changed),self.assertRaises(NativeUIError):role.read(0)
            self.assertEqual(0,role.state['sequence']);self.assertEqual('reading',role.state['phase'])
            self.assertEqual([],role.state['manifests']);self.assertFalse(self.guards[-1])
            binary=role.state['pending']['binaries'][0]
            self.assertEqual('saved',binary['phase'])
            self.assertEqual(self.b.raw,source.SnapshotsBinary.archive(self.b.root,binary))

    def test_target_changes_after_original_frame_write_prevent_manifest_publication(self):
        with self.b.role() as role:
            write=role.originals.write
            def changed(*args,**kwargs):
                result=write(*args,**kwargs);self.current=False;return result
            with patch.object(role.originals,'write',changed),self.assertRaises(NativeUIError):role.read(0)
            self.assertEqual(0,role.state['sequence']);self.assertEqual([],role.state['manifests'])
            self.assertEqual('saved',role.state['pending']['original']['phase']);self.assertFalse(self.guards[-1])

    def test_foreign_actual_role_header_is_preserved_during_host_publication(self):
        original=source.SnapshotsBinary.write;foreign={}
        with self.b.role() as role:
            def changed(engine,*args,**kwargs):
                result=original(engine,*args,**kwargs)
                header=deepcopy(role.previous);header['runId']='e'*32
                role.store.write(header,role.previous);foreign.update(header);return result
            with patch.object(source.SnapshotsBinary,'write',changed),self.assertRaises(NativeUIError):role.read(0)
            self.assertEqual(foreign,role.store.read());self.assertEqual(0,role.state['sequence'])

    def test_failed_acquisition_cannot_leave_a_host_only_guard_for_later_calls(self):
        original=source.SnapshotsBinary.write
        def interrupted(engine,*args,**kwargs):
            original(engine,*args,**kwargs);raise NativeUIError('Explicit interruption after actual host publication')
        with self.b.role() as role:
            with patch.object(source.SnapshotsBinary,'write',interrupted),self.assertRaises(NativeUIError):role.read(0)
            header=deepcopy(role.store.read());self.current=False
            with self.assertRaises(NativeUIError):role.save()
            self.assertEqual(header,role.store.read());self.assertFalse(self.guards[-1])


if __name__=='__main__':unittest.main()
