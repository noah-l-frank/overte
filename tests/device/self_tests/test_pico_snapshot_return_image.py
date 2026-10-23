"""Actual original render protocols/host PNG; native GPU/Android are seams."""
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
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.navigation import NavigationError
from adapters.owned_world_render import WorldRenderOwner
from adapters.pico4.graphics_binding import SerializedWorldCapture
from adapters.pico4.snapshot_return_image import PicoSnapshotReturnImage
from adapters.world_render_evidence import NativeWorldRenderCapture
from adapters.world_render_storage import NativeWorldRenderStorage,receipt_file
from adapters.world_render_receipts import NativeWorldReceiptInventory,NativeWorldReceiptBatchFiles
from self_tests.test_pico_snapshot_background_owner import Boundary
from self_tests.test_stereo_camera_uniforms import CameraBoundary
from self_tests.test_world_render_storage import Boundary as StorageBoundary
from self_tests.test_world_render_receipt_inventory import Boundary as InventoryBoundary


class ReturnBoundary:
    def __init__(self,root):
        self.b=Boundary(root);self.bg=self.b.owner();self.bg.prepare();self.bg.home();self.bg.resume();self.bg.quiet()
        self.images=root/'return-images';self.images.mkdir(mode=0o700);self.native_root=root/'return-native';self.native_root.mkdir(mode=0o700)
        self.gpu=CameraBoundary();self.storage=StorageBoundary();self.storage.raw=self.gpu.raw;self.inventory=InventoryBoundary(self.native_root)
        for path in self.native_root.iterdir():path.unlink()
        self.inventory.issued.clear();self.lose=False;self.actual=None
    def epoch(self):return self.b.epoch()
    def update(self,value):
        def clocks(row):
            if type(row) is dict:
                for key,item in row.items():
                    if key.endswith('EpochMs'):row[key]=self.epoch()
                    else:clocks(item)
            elif type(row) is list:
                for item in row:clocks(item)
        clocks(value);value['processId']=123;value['instance']='a'*32
    def factory(self):
        b=self.b
        def guard():b.lock.assert_held();b.native_guard();return True
        owner=WorldRenderOwner(PrivateFeatureState(b.root/'shared-render-primary.json'),b.binding,guard,role='primary')
        self.storage.mutate=self.update;self.inventory.mutate=self.update
        def send_storage(command):
            self.storage.intents.append(deepcopy(command));self.storage.send(command)
            name=receipt_file(command['commandId']);path=self.native_root/name;path.write_text(self.storage.files[name]);path.chmod(0o600)
            self.inventory.issued[command['commandId']]=(command['requestId'],hashlib.sha256(path.read_bytes()).hexdigest())
            self.inventory.owner=deepcopy(owner.owned());self.inventory.retired=not self.storage.present;self.inventory.present=self.storage.present
            self.inventory.callbacks=self.storage.callbacks;self.inventory.png_bytes=len(self.storage.raw) if self.storage.present else 0
        storage=NativeWorldRenderStorage(send_storage,self.storage.read,self.epoch,guard,123,receipt_intent=owner.receipt_intent,monotonic=lambda:b.host,sleep=b.sleep)
        def send_capture(command):
            assert owner.owned()['capture']==command
            self.gpu.intents.append(deepcopy(command));self.gpu.advance();self.storage.present=True;self.gpu.send(command);self.update(self.gpu.sample)
            if self.lose:raise NativeUIError('Explicit lost synthetic GPU response')
        capture=NativeWorldRenderCapture(send_capture,self.gpu.original,storage,self.epoch,guard,123,intent=owner.intent,
            stereo=True,require_cameras=True,monotonic=lambda:b.host,sleep=b.sleep)
        inventory=NativeWorldReceiptInventory(self.inventory.send,self.inventory.original,self.epoch,guard,123,owner.owned,lambda:storage.instance,monotonic=lambda:b.host,sleep=b.sleep)
        files=NativeWorldReceiptBatchFiles(SimpleNamespace(read=lambda name:(self.native_root/name).read_text()),inventory)
        self.actual=SerializedWorldCapture(capture,storage,owner,files,source_lock=b.lock);return self.actual
    def owner(self):
        return PicoSnapshotReturnImage(self.bg,self.b.root/'snapshot-return-image-primary.json',self.images,self.factory,role='primary',monotonic=lambda:self.b.host)


class SnapshotReturnImageCase(unittest.TestCase):
    def model(self):
        temporary=tempfile.TemporaryDirectory(prefix='snapshot-return-image-');self.addCleanup(temporary.cleanup);root=Path(temporary.name);root.chmod(0o700);return ReturnBoundary(root)


class SnapshotReturnImageTests(SnapshotReturnImageCase):
    def test_original_two_eye_return_png_current_snapshot_bookends_and_real_file_retirement(self):
        m=self.model();owner=m.owner();parent=m.bg.store.read();result=owner.acquire()
        self.assertTrue(result['originalStereoReturnPng']);self.assertTrue(result['captureMemoryAndReceiptsRetired']);self.assertFalse(result['sceneChallengeVerified'])
        self.assertFalse(result['fullSnapshotRecipe']);self.assertEqual(m.gpu.raw,owner.image_bytes());self.assertEqual([],list(m.native_root.iterdir()))
        self.assertIsNone(m.actual.owner.store.read());self.assertEqual(parent,m.bg.store.read());self.assertEqual(1,len(m.gpu.commands))
        queries=m.b.queries;self.assertTrue(m.owner().state['phase']=='complete');self.assertEqual(queries,m.b.queries)
        self.assertEqual(['lifecycle.background','app.launch'],m.b.calls)
        with m.b.lock.held():
            state=deepcopy(owner.state);state['frame']['capture']['source']['stereo']['eyes'][1]['viewOffset']=deepcopy(state['frame']['capture']['source']['stereo']['eyes'][0]['viewOffset'])
            with self.assertRaises(NativeUIError):owner.validate(state)
            state=deepcopy(owner.state);state['frames'][1]['base']['ui']['generation']='f'*32
            with self.assertRaises((NativeUIError,NavigationError)):owner.validate(state)
            state=deepcopy(owner.state);state['proof']['memory']['requestId']='f'*32
            with self.assertRaises(NativeUIError):owner.validate(state)
        original_header=owner.store.read();native=m.b.parent.native;guard=native.guard
        def changed():
            result=guard();owner.store.write(dict(original_header,role='actor'),owner.store.read());return result
        with m.b.lock.held():
            with patch.object(native,'guard',side_effect=changed),self.assertRaises(NativeUIError):owner.fence(m.b.parent)
            owner.store.write(original_header,owner.store.read())
        path=m.images/owner.state['image']['name'];raw=path.read_bytes()
        def changed_png():
            result=guard();path.write_bytes(raw[:-1]+b'x');return result
        with m.b.lock.held(),patch.object(native,'guard',side_effect=changed_png),self.assertRaises(NativeUIError):owner.fence(m.b.parent)
        path.write_bytes(raw)
        path.rename(path.with_suffix('.held'));path.write_bytes(raw);path.chmod(0o600)
        with self.assertRaises(NativeUIError):m.owner()
        self.assertEqual(1,len(m.gpu.commands));self.assertTrue(m.bg.store.path.exists())


class SnapshotReturnImageFenceTests(SnapshotReturnImageCase):
    def test_lost_capture_never_reacquires_after_cold_reopen_and_keeps_both_owners(self):
        m=self.model();owner=m.owner();m.lose=True
        with self.assertRaises(NativeUIError):owner.acquire()
        self.assertEqual('acquiring',m.owner().state['phase']);m.lose=False
        with self.assertRaises(NativeUIError):m.owner().acquire()
        self.assertEqual(1,len(m.gpu.commands));self.assertIsNotNone(m.actual.owner.store.read());self.assertTrue(owner.store.path.exists())
    def test_ignored_native_release_keeps_original_png_receipts_and_cold_does_not_resend_release(self):
        m=self.model();owner=m.owner();m.storage.ignore_release=True
        with self.assertRaises(NativeUIError):owner.acquire()
        releases=sum(row['operation']=='release' for row in m.storage.commands)
        with self.assertRaises(NativeUIError):m.owner().acquire()
        self.assertEqual(releases,sum(row['operation']=='release' for row in m.storage.commands));self.assertTrue(list(m.native_root.iterdir()))
        self.assertTrue(m.storage.present);self.assertIsNotNone(m.actual.owner.store.read())

    def test_phase_change_after_capture_parent_intent_prevents_the_actual_native_query(self):
        import uuid
        m=self.model();owner=m.owner();save=owner.save
        def changed(state):
            save(state)
            if state['phase']=='acquiring':
                phase=m.b.phase;phase['activations'].append(dict(sequence=len(phase['activations'])+1,ticket=uuid.uuid4().hex,activatedEpochMs=m.b.epoch(),stimulus=dict(verb='close',inputs={})))
        with patch.object(owner,'save',side_effect=changed),self.assertRaises(NativeUIError):owner.acquire()
        self.assertEqual([],m.gpu.commands);self.assertIsNone(m.actual.owner.store.read());self.assertEqual('acquiring',m.owner().state['phase'])
        with self.assertRaises(NativeUIError):m.owner().acquire()
        self.assertEqual([],m.gpu.commands)


if __name__=='__main__':unittest.main()
