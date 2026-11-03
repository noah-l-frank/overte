"""Lossless Close2 storage; original Close1 admission remains unchanged."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.snapshot_close_originals import SnapshotCloseOriginals
from adapters.pico4.snapshot_upload_originals import SnapshotUploadOriginals, SnapshotBackgroundOriginals, KINDS
from adapters.script_journey.history import canonical, pack, MAX_RAW
from self_tests.test_pico_lifecycle_back import BINDING
from self_tests.test_pico_lifecycle_source import RUN


class LegacyClose(SnapshotUploadOriginals):
    VERSION_KEY='snapshotCloseOriginalsVersion'
    VERBS=('close',)


class SnapshotCloseOriginalsTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='snapshot-close-storage-');self.addCleanup(temporary.cleanup)
        self.directory=Path(temporary.name);self.directory.chmod(0o700);self.path=self.directory/'snapshot-close-originals.json'
        self.owner=self.make()
    def make(self):return SnapshotCloseOriginals(self.path,RUN,BINDING,'close')
    def row(self,index=0):return dict({kind:dict(raw='unchanged literal\\\"\nλ',clock=index,source=kind) for kind in KINDS},hostMonotonic=1.+index)
    def state(self,rows=None):return dict(frames=[self.row()] if rows is None else rows,received=None)
    def physical(self):return {p.name:(p.read_bytes(),p.stat().st_ino,p.stat().st_mtime_ns,p.stat().st_ctime_ns) for p in self.directory.iterdir()}

    def test_complete_original_frame_roundtrip_one_part_and_host_only_never_repacks_or_writes(self):
        state=self.state([self.row(index) for index in range(34)]);encoded=self.owner.encode(state)
        self.assertEqual(34,len(self.owner.values));self.assertTrue(all(set(row)=={'fullFrame'} for row in encoded['frames']))
        self.assertEqual(state,self.make().decode(encoded));before=self.physical()
        with patch.object(self.owner,'fits',side_effect=AssertionError('Previously admitted frames may not repack')),patch.object(PrivateFeatureState,'write',side_effect=AssertionError('host-only source write')):
            self.assertEqual(encoded,self.owner.encode(state,host_only=True))
        self.assertEqual(before,self.physical());self.assertLess(self.owner.history.raw_bytes,MAX_RAW)
        self.assertEqual(2,self.owner.disk['snapshotCloseOriginalsVersion'])

    def test_real_incompressible_capacity_falls_back_to_tagged_role_references(self):
        rng=random.Random(20261103);row=dict({kind:dict(literal=base64.b64encode(rng.randbytes(14000)).decode()) for kind in KINDS},hostMonotonic=1.)
        self.assertFalse(self.owner.fits(row));state=self.state([row]);encoded=self.owner.encode(state)
        self.assertEqual({'roleFrames','hostMonotonic'},set(encoded['frames'][0]));self.assertEqual(4,len(self.owner.values))
        self.assertEqual(state,self.make().decode(encoded));before=self.physical()
        with patch.object(self.owner,'fits',side_effect=AssertionError('Do not re-evaluate original layout')):self.assertEqual(encoded,self.owner.encode(state,host_only=True))
        self.assertEqual(before,self.physical())

    def test_cold_legacy_continues_v1_without_migration_and_default_containers_stay_v1(self):
        legacy=LegacyClose(self.path,RUN,BINDING,'close');state=self.state();encoded=legacy.encode(state);before=self.physical()
        cold=self.make();self.assertEqual(1,cold.version);self.assertEqual(state,cold.decode(encoded));self.assertEqual(before,self.physical())
        self.assertEqual(encoded,cold.encode(state,host_only=True));self.assertEqual(before,self.physical())
        state['frames'].append(self.row(1));new=cold.encode(state);self.assertEqual(1,cold.disk['snapshotCloseOriginalsVersion']);self.assertEqual(state,self.make().decode(new))
        self.assertEqual(8,len(cold.values));self.assertTrue(all(set(row)==set(KINDS)|{'hostMonotonic'} for row in new['frames']))
        for cls,verb,key in ((SnapshotUploadOriginals,'upload','snapshotUploadOriginalsVersion'),(SnapshotBackgroundOriginals,'background','snapshotBackgroundOriginalsVersion')):
            owner=cls(self.directory/(verb+'.json'),RUN,BINDING,verb);owner.encode(self.state());self.assertEqual(1,owner.disk[key]);self.assertEqual(4,len(owner.values))

    def test_invalid_dto_anywhere_rejects_before_first_write_including_legacy(self):
        class DictSubclass(dict):pass
        class ListSubclass(list):pass
        malformed=[(1,),DictSubclass(a=1),ListSubclass([1]),{1:'key'},float('nan'),float('inf')]
        for version in (1,2):
            self.setUp()
            if version==1:
                legacy=LegacyClose(self.path,RUN,BINDING,'close');legacy.encode(self.state());self.owner=self.make()
            before=self.physical()
            for value in malformed:
                with self.subTest(version=version,value=repr(value)):
                    state=self.state();state['frames'][0]['base']['bad']=value
                    with patch.object(PrivateFeatureState,'write',side_effect=AssertionError('invalid DTO reached disk')),self.assertRaises((NativeUIError,ValueError)):self.owner.encode(state)
            self.assertEqual(before,self.physical())

    def test_unknown_host_only_frame_fails_before_capacity_and_all_writes(self):
        with patch.object(self.owner,'fits',side_effect=AssertionError('Unknown host-only frame')),patch.object(PrivateFeatureState,'write',side_effect=AssertionError('Unexpected write')),self.assertRaises(NativeUIError):self.owner.encode(self.state(),host_only=True)
        self.assertEqual({},self.physical())

    def test_missing_changed_identical_replacement_foreign_and_orphan_parts_refuse(self):
        for fault in ('missing','changed','same-bytes','foreign','orphan'):
            with self.subTest(fault=fault):
                self.setUp();self.owner.encode(self.state());child=self.owner.history.store(0);old=child.read()
                if fault=='missing':child.path.unlink()
                elif fault=='orphan':self.owner.history.store(1).write(old,None)
                else:
                    changed=deepcopy(old)
                    if fault=='changed':changed['transcript']=pack([dict(kind='fullFrame',original=self.row(3))])
                    if fault=='foreign':changed['scopeSha256']='f'*64
                    child.write(changed,old)
                with self.assertRaises(NativeUIError):self.owner.verify()
                if fault!='same-bytes':
                    with self.assertRaises(NativeUIError):self.make()
                # Cold historical reading cannot know a former inode. It makes
                # no freshness/ownership claim; warm readers retain that stamp.

    def test_unknown_child_or_manifest_cas_never_tries_role_fallback_or_adopts_orphans(self):
        for boundary in ('root-before','root-after','child','manifest-before','manifest-after'):
            with self.subTest(boundary=boundary):
                self.setUp();write=PrivateFeatureState.write;calls=[]
                def lost(store,value,previous):
                    calls.append(store.path.name)
                    at_child=store.path.name.endswith('.frame-000.json');at_manifest=store.path==self.path and previous is not None
                    if boundary.startswith('root') and store.path==self.path and previous is None:
                        if boundary=='root-after':write(store,value,previous)
                        raise OSError('Unknown initial root result')
                    if boundary=='child' and at_child:
                        write(store,value,previous);raise OSError('Unknown original child result')
                    if boundary.startswith('manifest') and at_manifest:
                        if boundary=='manifest-after':write(store,value,previous)
                        raise OSError('Unknown original manifest result')
                    return write(store,value,previous)
                with patch.object(PrivateFeatureState,'write',new=lost),self.assertRaises(OSError):self.owner.encode(self.state())
                self.assertFalse(self.owner.history.store(1).path.exists());self.assertNotIn('base',[value['kind'] for value in self.owner.values])
                if boundary!='root-before':
                    with self.assertRaises(NativeUIError):self.owner.verify()
                if boundary.startswith('root'):
                    self.assertFalse(self.owner.history.store(0).path.exists())
                    continue
                self.assertTrue(self.owner.history.store(0).path.exists())
                if boundary!='manifest-after':
                    with self.assertRaises(NativeUIError):self.make()
                else:
                    cold=self.make();self.assertEqual(1,len(cold.values));self.assertEqual(self.row(),cold.get('fullFrame',dict(snapshotOriginal=0,kind='fullFrame',sha256=cold.digest(cold.values[0]))))

    def test_aggregate_decoded_capacity_and_reference_guards_are_not_relaxed(self):
        state=self.state();encoded=self.owner.encode(state)
        for kind,value in (('kind','base'),('sha256','f'*64),('snapshotOriginal',True)):
            changed=deepcopy(encoded);changed['frames'][0]['fullFrame'][kind]=value
            with self.subTest(kind=kind),self.assertRaises(NativeUIError):self.owner.decode(changed)
        rows=[dict(self.row(index),base=dict(originalLiteral='x'*(2*1024*1024),index=index)) for index in range(8)]
        self.owner.encode(self.state(rows[:7]));before=self.physical()
        self.assertGreater(self.owner.history.raw_bytes,14*1024*1024)
        with self.assertRaises(NativeUIError):self.owner.encode(self.state(rows))
        self.assertEqual(before,self.physical());self.assertEqual(8,len(self.owner.values))
        self.assertFalse(self.owner.history.store(8).path.exists())


if __name__=='__main__':unittest.main()
