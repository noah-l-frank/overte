"""Actual owners and native readers at synthetic source/GPU/clock boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.owned_world_render import WorldRenderOwner
from adapters.pico4.emote_capture import PicoEmoteCapture
from adapters.pico4.graphics_binding import SerializedWorldCapture
from adapters.world_render_evidence import NativeWorldRenderCapture
from adapters.world_render_storage import NativeWorldRenderStorage,receipt_file
from adapters.world_render_receipts import NativeWorldReceiptInventory,NativeWorldReceiptBatchFiles
from self_tests import test_pico_emote_sources as source_fixture
RUN,BINDING=source_fixture.RUN,source_fixture.BINDING
from self_tests.test_pico_emote_pixels import fixture,POLICY
from self_tests.test_native_avatar_render import Boundary as AvatarBoundary
from self_tests.test_world_render_storage import Boundary as StorageBoundary
from self_tests.test_world_render_receipt_inventory import Boundary as InventoryBoundary


class CaptureModel:
    def __init__(self,case):
        self.source_case=source_fixture.SourcesTests();self.source_case.setUp();case.addCleanup(self.source_case.doCleanups)
        self.root=self.source_case.root;self.lock=self.source_case.lock;self.source=None
        frame,self.raw,self.models,self.gpu=fixture('c'*32,run=RUN,producers=True)
        self.gpu.commands.clear();self.gpu.intents.clear();self.models.commands.clear()
        self.avatar=AvatarBoundary();self.avatar.epoch=20000;self.avatar.avatar=deepcopy(frame['avatarBefore']['source'])
        self.avatar.avatar['rigId']=self.source_case.native['animation']['rigId']
        self.avatar.edit=lambda value:value.update(instance=self.source_case.native['instance'])
        self.native_root=self.root/'native';self.native_root.mkdir(mode=0o700)
        self.storage=StorageBoundary();self.storage.raw=self.raw;self.storage.present=False
        self.storage.mutate=lambda value:value.update(instance='a'*32)
        self.inventory=InventoryBoundary(self.native_root)
        for path in self.native_root.iterdir():path.unlink()
        self.inventory.issued.clear();self.inventory.mutate=lambda value:value.update(instance='a'*32)
        self.lost=False;self.release_lost=False;self.query_lost=False
        produce=self.gpu.mutate;model_row=deepcopy(self.models.trace['models'][0])
        def render(packet):
            produce(packet);frame=packet['source']['renderTrace'];batch=frame['cameraBatches'][0]
            row=deepcopy(model_row)
            row['cameraUses']=[dict(batchSequence=batch['sequence'],slot=c['slot'],eye=c['eye'],
                drawViewport=deepcopy(c['drawViewport']),drawCommands=1) for c in batch['cameras']]
            self.models.trace={key:deepcopy(frame[key]) for key in ('frameId','frameIndex','executionSequence',
                'recordedEpochMs','begunEpochMs','completedEpochMs','renderer','view')}
            self.models.trace.update(picoModelTraceVersion=1,drawCommands=1,models=[row])
        self.gpu.mutate=render

    def owner_store(self):return PrivateFeatureState(self.root/'world-primary.json')

    def world(self):
        m=self.source_case
        def guard():self.lock.assert_held();return m.guard()
        owner=WorldRenderOwner(self.owner_store(),BINDING,guard,role='primary')
        def send_storage(command):
            self.storage.intents.append(deepcopy(command));self.storage.send(command)
            name=receipt_file(command['commandId']);path=self.native_root/name
            path.write_text(self.storage.files[name]);path.chmod(0o600)
            self.inventory.issued[command['commandId']]=(command['requestId'],hashlib.sha256(path.read_bytes()).hexdigest())
            self.inventory.owner=deepcopy(owner.owned());self.inventory.retired=not self.storage.present
            self.inventory.present=self.storage.present;self.inventory.callbacks=self.storage.callbacks
            self.inventory.png_bytes=len(self.raw) if self.storage.present else 0
            if self.release_lost and command['operation']=='release':
                raise NativeUIError('Synthetic lost release reply')
        options=dict(monotonic=lambda:m.clock,sleep=m.sleep)
        storage=NativeWorldRenderStorage(send_storage,self.storage.read,lambda:m.epoch,guard,31,
            receipt_intent=owner.receipt_intent,**options)
        def acquire(command):
            assert owner.owned()['capture']==command
            self.gpu.intents.append(deepcopy(command));self.gpu.send(command);self.storage.present=True
            if self.lost:raise NativeUIError('Synthetic lost acquire reply')
        capture=NativeWorldRenderCapture(acquire,self.gpu.original,storage,lambda:m.epoch,guard,31,
            intent=owner.intent,stereo=True,require_cameras=True,**options)
        inventory=NativeWorldReceiptInventory(self.inventory.send,self.inventory.original,lambda:m.epoch,guard,31,
            owner.owned,lambda:storage.instance,**options)
        receipts=NativeWorldReceiptBatchFiles(SimpleNamespace(read=lambda name:(self.native_root/name).read_text()),inventory)
        return SerializedWorldCapture(capture,storage,owner,receipts,source_lock=self.lock)

    def capture(self,index=1):
        if self.source is None:self.source=self.source_case.owner();self.source.read()
        # Defer model producer binding until its native query, after acquisition.
        reader=self.models.reader();send=reader.send
        def query(command):
            self.models.capture=deepcopy(self.gpu.sample)
            if self.query_lost:raise NativeUIError('Synthetic lost model reply')
            send(command)
        reader.send=query
        return PicoEmoteCapture(self.source,index,POLICY,self.world,self.avatar.reader,lambda:reader,
            monotonic=lambda:self.source_case.clock)


class PicoEmoteCaptureTests(unittest.TestCase):
    def setUp(self):self.model=CaptureModel(self)

    def test_original_png_model_cameras_avatar_and_actual_memory_file_retirement(self):
        m=self.model
        with m.lock.held():
            owner=m.capture();frame=owner.read('c'*32)
            self.assertEqual('complete',owner.state['phase']);self.assertIsNone(m.owner_store().read())
            self.assertFalse(m.storage.present);self.assertEqual([],list(m.native_root.iterdir()))
            self.assertEqual((frame,m.raw),owner.original())
            self.assertEqual((frame,m.raw),m.capture().original())
            self.assertEqual(1,len(m.gpu.commands));self.assertEqual(1,len(m.models.commands))
            self.assertEqual(2,len(m.avatar.commands))
            for path in m.root.rglob('*'):
                if path.is_file() and path.suffix in ('.json','.png'):self.assertEqual(0o600,path.stat().st_mode&0o777)
            with self.assertRaises(NativeUIError):m.capture().read('c'*32)
            self.assertEqual(1,len(m.gpu.commands))

    def test_lost_acquire_or_model_result_never_reacquires_and_cleanup_retains_original_intent(self):
        for fault in ('lost','query_lost'):
            with self.subTest(fault=fault):
                m=CaptureModel(self);setattr(m,fault,True);m.release_lost=True
                with m.lock.held():
                    owner=m.capture()
                    with self.assertRaises(NativeUIError):owner.read('c'*32)
                    self.assertEqual('reading',owner.state['phase']);self.assertIsNotNone(m.owner_store().read())
                    m.release_lost=False;restored=m.capture()
                    with self.assertRaises(NativeUIError):restored.read('c'*32)
                    proof=restored.recover();self.assertFalse(proof['memory']['present'])
                    self.assertEqual([],list(m.native_root.iterdir()));self.assertIsNone(m.owner_store().read())
                    self.assertEqual(1,len(m.gpu.commands))
                    if fault=='lost':self.assertIsNone(restored.state['capture'])
                    with self.assertRaises(NativeUIError):restored.original()

    def test_historical_original_survives_parent_advance_without_any_query_or_retiming(self):
        m=self.model
        with m.lock.held():
            owner=m.capture();frame=owner.read('c'*32);header=deepcopy(owner.previous)
            m.source.read();calls=(len(m.gpu.commands),len(m.avatar.commands),len(m.models.commands))
            self.assertEqual((frame,m.raw),owner.original())
            owner.store.discard(header)
            self.assertEqual((frame,m.raw),PicoEmoteCapture.archive(header,m.source,1,POLICY))
            self.assertEqual(calls,(len(m.gpu.commands),len(m.avatar.commands),len(m.models.commands)))

    def test_ignored_release_or_changed_avatar_rig_cannot_deliver_a_frame(self):
        for fault in ('ignore_release','rig'):
            with self.subTest(fault=fault):
                m=CaptureModel(self)
                if fault=='ignore_release':m.storage.ignore_release=True
                else:m.avatar.avatar['rigId']+=1
                with m.lock.held():
                    owner=m.capture()
                    with self.assertRaises(NativeUIError):owner.read('c'*32)
                    self.assertEqual('reading',owner.state['phase'])
                    with self.assertRaises(NativeUIError):owner.original()
                    self.assertEqual(int(fault=='ignore_release'),len(m.gpu.commands))

    def test_bad_current_challenge_is_retired_and_recovery_never_reacquires(self):
        m=self.model;m.source_case.journal.activate(RUN,'f'*32,'play',{'name':'Waving'})
        with m.lock.held():
            owner=m.capture()
            with self.assertRaises(NativeUIError):owner.read('f'*32)
            self.assertIsNone(m.owner_store().read());self.assertIsNotNone(owner.state['retirement'])
            commands=deepcopy(m.storage.commands);proof=m.capture().recover()
            self.assertFalse(proof['memory']['present']);self.assertEqual(commands,m.storage.commands)
            self.assertEqual(1,len(m.gpu.commands))

    def test_partial_image_write_keeps_inode_and_cannot_be_promoted_to_an_original(self):
        m=self.model
        from adapters.graphics_journey import originals
        with m.lock.held():
            owner=m.capture()
            with patch.object(originals.GraphicsOriginals,'read',side_effect=NativeUIError('Synthetic write interruption')):
                with self.assertRaises(NativeUIError):owner.read('c'*32)
            self.assertIn(owner.state['image']['phase'],('planned','opened'))
            restored=m.capture();self.assertEqual(owner.state['image'],restored.state['image'])
            restored.recover();self.assertEqual(1,len(m.gpu.commands))
            with self.assertRaises(NativeUIError):restored.original()

    def test_changed_png_inode_bytes_or_link_never_becomes_historical_evidence(self):
        for fault in ('bytes','inode','hardlink','symlink'):
            with self.subTest(fault=fault):
                m=CaptureModel(self)
                with m.lock.held():
                    owner=m.capture();owner.read('c'*32)
                    path=owner.images().root/owner.state['image']['name']
                    if fault=='bytes':path.write_bytes(m.raw+b'foreign')
                    elif fault=='inode':
                        other=path.with_suffix('.replacement');other.write_bytes(m.raw);other.chmod(0o600);os.replace(other,path)
                    elif fault=='hardlink':os.link(path,path.with_suffix('.link'))
                    else:
                        original=path.with_suffix('.original');path.rename(original);path.symlink_to(original)
                    with self.assertRaises((NativeUIError,OSError)):owner.original()
                    self.assertEqual(1,len(m.gpu.commands))

    def test_lost_parent_reservation_blocks_warm_and_cold_dispatch_before_acquisition(self):
        m=self.model
        with m.lock.held():
            owner=m.capture();write=owner.store.write
            def lost(value,previous):
                write(value,previous)
                if __import__('adapters.script_journey.history',fromlist=['unpack']).unpack(value['payload'])[0]['captureIntent'] is not None:
                    raise NativeUIError('Synthetic lost journal reply')
            with patch.object(owner.store,'write',side_effect=lost),self.assertRaises(NativeUIError):owner.read('c'*32)
            self.assertEqual([],m.gpu.commands);self.assertIsNone(m.owner_store().read())
            with self.assertRaises(NativeUIError):owner.read('c'*32)
            with self.assertRaises(NativeUIError):m.capture().read('c'*32)
            self.assertEqual([],m.gpu.commands)

    def test_final_native_clock_jump_and_frozen_clock_decode_cost_cannot_deliver_stale_original(self):
        from adapters.pico4 import emote_capture
        for fault in ('native','host'):
            with self.subTest(fault=fault):
                m=CaptureModel(self);original=emote_capture.pixel_original;calls=[0]
                def consume(*args,**kwargs):
                    result=original(*args,**kwargs);calls[0]+=1
                    if calls[0]==2:
                        if fault=='native':m.avatar.epoch+=2000
                        else:m.source_case.clock+=2
                    return result
                with m.lock.held():
                    owner=m.capture()
                    with patch.object(emote_capture,'pixel_original',side_effect=consume),self.assertRaises(NativeUIError):owner.read('c'*32)
                    self.assertEqual(1,len(m.gpu.commands));self.assertIsNone(m.owner_store().read())

    def test_rewritten_original_parent_rig_or_phase_cannot_reconstruct_completed_packet(self):
        from adapters.script_journey.history import pack,unpack
        m=self.model
        with m.lock.held():
            owner=m.capture();owner.read('c'*32);previous=deepcopy(owner.previous)
            for key in ('rig','phase'):
                altered=deepcopy(previous);state=unpack(altered['payload'])[0]
                if key=='rig':
                    state['avatarBefore']['source']['rigId']+=1;state['avatarAfter']['source']['rigId']+=1
                else:
                    state['providerBefore']['instance']='f'*32;state['providerAfter']['instance']='f'*32
                altered['payload']=pack([state]);owner.store.write(altered,previous)
                with self.assertRaises((NativeUIError,ValueError)):m.capture()
                owner.store.write(previous,altered)
            self.assertEqual(1,len(m.gpu.commands))


if __name__=='__main__':unittest.main()
