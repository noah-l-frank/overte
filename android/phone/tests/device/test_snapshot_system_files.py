"""Actual private namespace with explicit passive-native and OS transport seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone'),str(Path(__file__).parent)]
from adapters.normal_ui import NativeUIError
from test_snapshot_handoff import Boundary as Native
from test_snapshot_capture_files import Producer,LocalTransport,CONTEXT,RUN,PREFIX
from overte_phone_snapshot_capture_files import PhoneSnapshotCaptureFiles
from overte_phone_snapshot_handoff import PhoneSnapshotHandoff
from overte_phone_snapshot_system_files import SnapshotSystemFileSource


class Passive(Native):
    def __init__(self,producer):
        super().__init__();self.producer=producer;self.epoch=producer.epoch
        self.owner.update(processId=77,startedEpochMs=self.epoch,deadlineEpochMs=self.epoch+60000)
        self.fault=''
    def raw(self):
        value=self.frame();source=value['source'];source.update(processId=77,startedEpochMs=self.owner['startedEpochMs'],deadlineEpochMs=self.owner['deadlineEpochMs'])
        value['processId']=77;batch=source['source']
        for packet in batch['group'].values():
            packet.update(processId=77,requestedEpochMs=self.epoch,capturedEpochMs=self.epoch)
        batch['group']['snapshot']['source']['androidExport']['capturedEpochMs']=self.epoch
        batch['context']['account']['observation']['capturedEpochMs']=self.epoch
        for key in ('readbacks','upload'):batch[key]['processId']=77
        self.producer.outer='a'*32
        original=self.producer.reader(True).request(RUN)
        batch['captureFiles']=original
        if self.fault=='stale':batch['captureFiles']['capturedEpochMs']-=2000
        elif self.fault=='foreign':batch['captureFiles']['runId']='f'*32
        elif self.fault=='rollback':batch['captureFiles']['source']['plans']=[]
        return json.dumps(value)


class SnapshotSystemFilesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.producer=Producer(self.root);self.producer.outer='a'*32
        primary=self.root/'primary';primary.mkdir(mode=0o700)
        self.owner=PhoneSnapshotCaptureFiles(LocalTransport(self.root,primary),self.producer.reader(),CONTEXT,self.root/'owner.json')
        self.owner.plan(RUN,PREFIX);self.row,self.path=self.producer.capture();self.binding=self.owner.binding()
        self.native=Passive(self.producer);self.handoff=PhoneSnapshotHandoff(self.native.raw,lambda:self.native.epoch,lambda:True,self.native.owner)
        self.source=SnapshotSystemFileSource(self.handoff)
    def peer(self):
        artifacts=self.root/'observer';artifacts.mkdir(mode=0o700,exist_ok=True)
        return PhoneSnapshotCaptureFiles(LocalTransport(self.root,artifacts),self.source,CONTEXT,self.root/'observer-owner.json',read_only=True)
    def test_independent_readonly_owner_uses_new_passive_source_and_actual_namespace(self):
        peer=self.peer();peer.attach(self.binding);before=len(self.producer.sent)
        inventory=peer.inventory();self.assertEqual(self.path.stat().st_ino,inventory['files'][0]['inode'])
        original=peer.acquire(self.row['path'],self.row['captureId'])
        self.assertEqual(self.path.read_bytes(),(peer.transport.artifacts/original['artifact']).read_bytes())
        self.assertTrue(all(request['action'].endswith('observe') for request in self.producer.sent[before:]))
        # The native producer writes a new passive sample; no handoff command
        # or file plan/delete/seal is delivered by this wrapper.
        self.assertFalse(self.native.commands);self.assertTrue(self.path.exists())
    def test_mutations_and_foreign_run_are_refused_before_passive_acquisition(self):
        for operation,kwargs in (('plan',dict(prefix=PREFIX,operation_id='1'*32)),('retire',dict(file_id='2'*32,operation_id='1'*32)),('seal',dict(file_id='2'*32,operation_id='1'*32))):
            with self.subTest(operation=operation),self.assertRaises(NativeUIError):self.source.request(RUN,operation,**kwargs)
        with self.assertRaises(NativeUIError):self.source.request('f'*32)
        self.assertIsNone(self.handoff.last)
    def test_old_foreign_rollback_sources_and_actual_replacement_never_become_inventory(self):
        for fault in ('stale','foreign','rollback','replacement'):
            with self.subTest(fault=fault):
                if fault!='stale':self.setUp()
                peer=self.peer();peer.attach(self.binding)
                if fault=='replacement':
                    raw=self.path.read_bytes();self.path.rename(self.path.with_suffix('.old'));self.path.write_bytes(raw)
                else:self.native.fault=fault
                with self.assertRaises(NativeUIError):peer.inventory()


if __name__=='__main__':unittest.main()
