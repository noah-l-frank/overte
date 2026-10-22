"""Original Snapshot evidence namespaces and recoverable real file prefixes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/self_tests'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.normal_ui import NativeUIError
from overte_phone_snapshots_evidence import SnapshotsOriginals,SnapshotsImages,SnapshotsBinary
from test_graphics_images import BINDING
from test_graphics_measurements import Sources,RUN,TICKET
from self_tests.test_snapshot_upload_service import png

class SnapshotsEvidenceTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='snapshots-evidence-');self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.receipts=[];self.failure=None;self.raw=png()
        self.acquisition=dict(source='snapshot-capture-original',bytes=len(self.raw),sha256=hashlib.sha256(self.raw).hexdigest(),capturedEpochMs=20000)
    def intent(self,value):
        self.receipts.append(deepcopy(value))
        if value['phase']==self.failure:raise NativeUIError('Synthetic lost storage return')
    def binary(self,role='primary',stage=1):return SnapshotsBinary(self.root,BINDING,RUN,role,stage,lambda:True,self.intent)
    def test_raw_frames_and_world_png_keep_separate_snapshot_namespaces(self):
        owner=SnapshotsOriginals(self.root,BINDING,RUN,'primary',lambda:True,lambda *_:True,kind='snapshots')
        frame=dict(actualSourceEpochMs=20000);ref=owner.write(1,frame);refs=owner.append([],ref)
        self.assertEqual([frame],owner.restore(refs,1));self.assertIn('snapshots',owner.path(owner.expand(ref)).name)
        source=Sources();images=SnapshotsImages(self.root,BINDING,RUN,'primary',1,lambda:True,self.intent)
        value=images.write(TICKET,source.capture,source.pixels)
        self.assertTrue(value['name'].startswith('snapshots-'));self.assertEqual(source.pixels,images.archive(self.root,value))
    def test_each_binary_sink_retains_actual_bytes_and_original_acquisition_epoch(self):
        for stage,source in enumerate(sorted(SnapshotsBinary.SOURCES),1):
            acquisition=self.acquisition|dict(source=source);owner=self.binary(stage=stage);value=owner.write(TICKET,acquisition,self.raw)
            self.assertEqual(self.raw,owner.archive(self.root,value));self.assertEqual(20000,value['acquisition']['capturedEpochMs'])
            self.assertEqual(['planned','opened','saved'],[row['phase'] for row in self.receipts[-3:]])
            self.assertEqual(0o600,(self.root/value['name']).stat().st_mode&0o777)
    def test_uncertain_opened_file_resumes_only_its_original_matching_prefix_inode(self):
        owner=self.binary();self.failure='opened'
        with self.assertRaises(NativeUIError):owner.write(TICKET,self.acquisition,self.raw)
        value=deepcopy(self.receipts[-1]);path=self.root/value['name'];inode=path.stat().st_ino
        path.write_bytes(self.raw[:20]);self.failure=None;result=owner.resume(value,self.raw)
        self.assertEqual(inode,path.stat().st_ino);self.assertEqual(self.raw,owner.read(result))
        path.write_bytes(b'foreign')
        with self.assertRaises(NativeUIError):owner.resume(value,self.raw)
        self.assertEqual(b'foreign',path.read_bytes())
    def test_foreign_hash_actor_link_mode_replacement_or_non_png_cannot_supply_transcript(self):
        owner=self.binary();value=owner.write(TICKET,self.acquisition,self.raw);path=self.root/value['name']
        with self.assertRaises(NativeUIError):self.binary('actor').read(value)
        bad=deepcopy(value);bad['acquisition']['sha256']='f'*64
        with self.assertRaises(NativeUIError):owner.read(bad)
        link=self.root/'alias';os.link(path,link)
        with self.assertRaises(NativeUIError):owner.read(value)
        link.unlink();path.chmod(0o644)
        with self.assertRaises(NativeUIError):owner.read(value)
        path.chmod(0o600);replacement=self.root/'replacement';replacement.write_bytes(self.raw);replacement.chmod(0o600);os.replace(replacement,path)
        with self.assertRaises(NativeUIError):owner.read(value)
        raw=b'acknowledged but not a PNG';acquisition=self.acquisition|dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        with self.assertRaises((ValueError,NativeUIError)):self.binary(stage=2).write(TICKET,acquisition,raw)

if __name__=='__main__':unittest.main()
