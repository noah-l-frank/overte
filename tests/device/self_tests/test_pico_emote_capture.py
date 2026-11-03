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
        self.world_binding=deepcopy(BINDING);self.world_role='primary'
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

    def owner_store(self):return PrivateFeatureState(self.root/('world-'+self.world_role+'.json'))

    def world(self):
        m=self.source_case
        def guard():self.lock.assert_held();return m.guard()
        owner=WorldRenderOwner(self.owner_store(),self.world_binding,guard,role=self.world_role)
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
            self.assertEqual((frame,m.raw),m.capture().original())
            owner.store.discard(header)
            self.assertEqual((frame,m.raw),PicoEmoteCapture.archive(header,m.source,1,POLICY))
            self.assertEqual(calls,(len(m.gpu.commands),len(m.avatar.commands),len(m.models.commands)))

    def test_lost_acquisition_cleanup_uses_original_prefix_after_parent_advance_or_interruption(self):
        for interrupted in (False,True):
            with self.subTest(interrupted=interrupted):
                m=CaptureModel(self);m.lost=True;m.release_lost=True
                with m.lock.held():
                    owner=m.capture()
                    with self.assertRaises(NativeUIError):owner.read('c'*32)
                    header=deepcopy(owner.source_header);m.release_lost=False
                    m.source.read()
                    if interrupted:
                        m.source_case.fault='roots'
                        with self.assertRaises(NativeUIError):m.source.read()
                    restored=m.capture();proof=restored.recover()
                    self.assertEqual(header,restored.source_header)
                    self.assertNotEqual(header,restored.current_source_header)
                    self.assertFalse(proof['memory']['present']);self.assertIsNone(m.owner_store().read())
                    self.assertEqual(1,len(m.gpu.commands));self.assertEqual([],list(m.native_root.iterdir()))

    def test_parent_change_during_live_owner_and_historical_source_cannot_authorize_acquisition(self):
        m=self.model
        with m.lock.held():
            owner=m.capture();m.source.read()
            with self.assertRaises(NativeUIError):owner.read('c'*32)
            self.assertEqual([],m.gpu.commands)
            m.source.historical=True
            with self.assertRaises(NativeUIError):m.capture()
            self.assertEqual([],m.gpu.commands)

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


class RemoteCaptureModel:
    """Real host owners/files; explicit separate client/GPU/Qt/clock models."""
    def __init__(self,case,*,viewer_bridge=None):
        from self_tests.test_pico_emote_native_cycle import CycleBoundary
        from self_tests.test_pico_avatar_remote import RemoteBoundary,SELF,SUBJECT
        from adapters.pico4.avatar_remote_source import PicoRemoteAvatarSource
        self.cycle=CycleBoundary();case.addCleanup(self.cycle.close)
        self.remote=RemoteBoundary(area='emotes');case.addCleanup(self.remote.close)
        self.gpu=CaptureModel(case);self.hosts=[];case.addCleanup(self.close)
        self.primary=self.viewer=None
        self.canonical_adapter=self.canonical_target=None
        self.primary_calls=[];self.viewer_calls=[];self.primary_raw=self.viewer_raw=None;self.edit=None
        s=self.cycle.s;r=self.remote
        r.binding['targetFingerprint']='e'*64
        if viewer_bridge is not None:r.binding['sessionId']=viewer_bridge
        with s.lock.held():
            self.parent=self.cycle.owner();self.parent.baseline()
            self.parent.act(self.cycle.input.call('open'));self.parent.act(self.cycle.input.call('play',{'name':'Waving'}))
        def send(role,request):
            r.sequence+=1;packet=r.packet(request,primary=role=='primary',epoch=s.epoch)
            binding=self.parent.source.binding if role=='primary' else r.binding
            packet['processId']=int(binding['processIdentity'].split(':')[0])
            (self.primary_calls if role=='primary' else self.viewer_calls).append(deepcopy(request))
            if self.edit:self.edit(role,packet)
            if role=='primary':self.primary_raw=json.dumps(packet)
            else:self.viewer_raw=json.dumps(packet)
        self.send_source=send
        with s.lock.held():
            self.primary=PicoRemoteAvatarSource(PrivateFeatureState(s.root/'primary-remote.json'),self.parent.source.binding,
                s.phase,s.lock,SELF,lambda query:send('primary',query),lambda:self.primary_raw,
                lambda:s.epoch,s.guard,monotonic=lambda:s.clock,sleep=s.sleep)
            self.primary.read()
        with r.lock.held():
            self.viewer=PicoRemoteAvatarSource(PrivateFeatureState(r.root/'viewer-remote.json'),r.binding,
                s.phase,r.lock,SUBJECT,lambda query:send('viewer',query),lambda:self.viewer_raw,
                lambda:s.epoch,s.guard,primary=self.primary.packets[0],monotonic=lambda:s.clock,sleep=s.sleep)
        self.gpu.source_case=s;self.gpu.lock=r.lock;self.gpu.world_binding=deepcopy(r.binding);self.gpu.world_role='actor'
        produce=self.gpu.gpu.mutate
        def timestamps(value,delta):
            if type(value) is dict:
                for key,item in value.items():
                    if key.endswith('EpochMs'):value[key]=item+delta
                    else:timestamps(item,delta)
            elif type(value) is list:
                for item in value:timestamps(item,delta)
        def render(packet):
            produce(packet);timestamps(packet,s.epoch-20000);packet['processId']=self.viewer.pid;frame=packet['source']['renderTrace']
            for key in ('frameId','frameIndex','executionSequence','recordedEpochMs','begunEpochMs','completedEpochMs','renderer','view'):
                self.gpu.models.trace[key]=deepcopy(frame[key])
            self.gpu.models.epoch=s.epoch
        self.gpu.gpu.mutate=render
        self.gpu.storage.mutate=lambda value:value.update(instance='a'*32,processId=self.viewer.pid,capturedEpochMs=s.epoch)
        self.gpu.inventory.mutate=lambda value:value.update(instance='a'*32,processId=self.viewer.pid,capturedEpochMs=s.epoch)

    def canonical(self,case):
        """Use the actual Pico binding/factory; only SDK/native/GPU edges model."""
        import sys
        from adapters.pico4.avatar_remote_source import PicoRemoteAvatarSource
        from adapters.pico4.avatar_remote_state import source_store
        from adapters.script_journey.lock import ScriptSourceLock
        from adapters.world_render_receipts import INVENTORY_FILE
        from adapters.pico4.emote_model_draws import FILE as DRAW_FILE
        from adapters.world_render_evidence import FILE as WORLD_FILE
        sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'android/vr/pico/tests/device'))
        import test_normal_emote as bound
        fixture=bound.PicoEmoteTests();fixture.setUp();case.addCleanup(fixture.doCleanups)
        adapter,target=fixture.instance,fixture.native.target
        _ui,_observe,binding=adapter._script_runtime(target);candidate=adapter._native_feature_observer(target)
        s=self.cycle.s;r=self.remote
        assert not self.viewer.packets and not self.hosts
        assert self.viewer.close_host()  # Unissued setup only; no history is renewed.
        r.binding=deepcopy(binding);r.lock=ScriptSourceLock(adapter._script_journey().state_path(target).with_name('script-sources.lock'))
        with r.lock.held():
            self.viewer=PicoRemoteAvatarSource(source_store(adapter,target,RUN,area='emotes'),binding,s.phase,r.lock,
                self.primary.packets[0]['source']['selfSessionId'],lambda query:self.send_source('viewer',query),lambda:self.viewer_raw,
                lambda:s.epoch,candidate.guard,primary=self.primary.packets[0],monotonic=lambda:s.clock,sleep=s.sleep)
        self.gpu.lock=r.lock;self.gpu.world_binding=deepcopy(binding)
        self.gpu.owner_store=lambda:adapter._emote_world_render_store(target,'actor')
        actual_read=adapter.adb.read_debug_app_file
        self.native_commands=[]
        def send(command):
            self.native_commands.append(deepcopy(command))
            if command['action']=='feature-world-render-observe':
                assert self.gpu.owner_store().read()['capture']==command
                self.gpu.gpu.intents.append(deepcopy(command));self.gpu.gpu.send(command);self.gpu.storage.present=True
                if self.gpu.lost:raise NativeUIError('Explicit lost actual-bound acquire result')
            elif command['action']=='feature-world-render-storage':
                self.gpu.storage.intents.append(deepcopy(command));self.gpu.storage.send(command)
                name=receipt_file(command['commandId']);path=self.gpu.native_root/name
                path.write_text(self.gpu.storage.files[name]);path.chmod(0o600)
                self.gpu.inventory.issued[command['commandId']]=(command['requestId'],hashlib.sha256(path.read_bytes()).hexdigest())
                self.gpu.inventory.owner=deepcopy(self.gpu.owner_store().read())
                self.gpu.inventory.retired=not self.gpu.storage.present;self.gpu.inventory.present=self.gpu.storage.present
                self.gpu.inventory.callbacks=self.gpu.storage.callbacks
                self.gpu.inventory.png_bytes=len(self.gpu.raw) if self.gpu.storage.present else 0
                if self.gpu.release_lost and command['operation']=='release':raise NativeUIError('Explicit lost actual-bound release result')
            elif 'receiptIds' in command:self.gpu.inventory.send(command)
            elif command['action']=='feature-pico-world-model-draws-observe':
                self.gpu.models.capture=deepcopy(self.gpu.gpu.sample)
                if self.gpu.query_lost:raise NativeUIError('Explicit lost actual-bound model result')
                self.gpu.models.send(command)
            else:raise AssertionError('Unknown actual Native operation')
        native=SimpleNamespace(pid=self.viewer.pid,send=send,guard=candidate.guard,clock_ms=lambda:s.epoch,
            monotonic=lambda:s.clock,sleep=s.sleep)
        def read(selected,package,path,**options):
            assert selected==target and package=='org.overte.pico'
            if path.endswith('/'+WORLD_FILE):return self.gpu.gpu.original()
            if path.endswith('/'+DRAW_FILE):return self.gpu.models.original()
            if path.endswith('/'+INVENTORY_FILE):return self.gpu.inventory.original()
            name=path.rsplit('/',1)[-1]
            if name.startswith('world-render-storage-'):return (self.gpu.native_root/name).read_text()
            return actual_read(selected,package,path,**options)
        for boundary in (patch.object(adapter,'_native_feature_observer',return_value=native),
                         patch.object(adapter.adb,'read_debug_app_file',side_effect=read)):
            boundary.start();case.addCleanup(boundary.stop)
        self.canonical_adapter,self.canonical_target=adapter,target
        return adapter,target

    def close(self):
        for owner in self.hosts:
            if not owner.close_host():raise AssertionError('Original Capture2 descriptor remains uncertain')
        for source in (self.primary,self.viewer):
            if source is not None and not source.close_host():raise AssertionError('Original remote source descriptor remains uncertain')

    def held(self):
        from adapters.pico4.emote_remote_capture import held
        return held(self.parent,self.primary,self.viewer)

    def owner(self,index=1):
        from adapters.pico4.emote_remote_capture import create
        if self.canonical_adapter is not None:
            value=create(self.canonical_adapter,self.canonical_target,self.parent,self.primary,self.viewer,index)
            self.hosts.append(value);return value
        reader=self.gpu.models.reader();send=reader.send
        def query(command):
            self.gpu.models.capture=deepcopy(self.gpu.gpu.sample)
            if self.gpu.query_lost:raise NativeUIError('Explicit lost remote model result')
            send(command)
        reader.send=query
        def world(target,source):
            assert target=='explicit-viewer' and source is self.viewer
            return self.gpu.world()
        adapter=SimpleNamespace(_script_runtime=lambda target:(None,None,self.viewer.binding),
            _script_journey=lambda:SimpleNamespace(state_path=lambda target:self.remote.root/'state.json'),
            _emote_world_render_capture=world,_emote_model_draws_observer=lambda target:reader)
        value=create(adapter,'explicit-viewer',self.parent,self.primary,self.viewer,index)
        self.hosts.append(value);return value

    def ticket(self):return self.parent.state['steps'][1]['call']['ticket']

    def finish(self):
        with self.cycle.s.lock.held():
            self.parent.act(self.cycle.input.call('cancel'));self.parent.act(self.cycle.input.call('close'))
            self.cycle.s.journal.activate(RUN,'f'*32,'cleanup')
            return self.parent.cleanup(sleep=self.cycle.sleep)


class PicoEmoteRemoteCaptureTests(unittest.TestCase):
    def setUp(self):self.model=RemoteCaptureModel(self)

    def test_complete_normal_input_remote_two_eye_png_cancel_close_and_original_quiet_cycle(self):
        m=self.model
        with m.held():
            owner=m.owner();frame=owner.read(m.ticket())
            self.assertEqual(1,len(m.gpu.gpu.commands));self.assertEqual(2,len(m.viewer_calls));self.assertEqual(2,len(m.primary_calls))
            self.assertEqual((frame,m.gpu.raw),owner.original());self.assertIsNone(m.gpu.owner_store().read())
            self.assertFalse(m.gpu.storage.present);self.assertEqual([],list(m.gpu.native_root.iterdir()))
            self.assertNotIn('animation',frame);self.assertEqual(2,owner.previous['picoEmoteCaptureVersion'])
        m.finish()
        with m.held():
            final=owner.finish_cycle();self.assertTrue(final['normalCycleClosed']);self.assertTrue(final['remoteDrawPngRetired'])
            self.assertFalse(final['pixelsQualified']);self.assertFalse(final['independentActorQualified']);self.assertFalse(final['wholeFeatureComplete'])
            self.assertEqual('cycle-complete',m.owner().state['phase'])
            self.assertGreaterEqual(m.parent.state['cleanup']['window']['elapsedMs'],3000)

    def test_unrelated_ui_bridge_does_not_supply_or_override_native_avatar_session(self):
        bridge='44444444-4444-4444-8444-444444444444';m=RemoteCaptureModel(self,viewer_bridge=bridge)
        with m.held():
            owner=m.owner();frame=owner.read(m.ticket())
            self.assertEqual(bridge,owner.binding['sessionId'])
            self.assertEqual('22222222-2222-4222-8222-222222222222',frame['avatarBefore']['source']['selfSessionId'])
            self.assertEqual('11111111-1111-4111-8111-111111111111',frame['avatarBefore']['source']['subjectSessionId'])

    def test_malformed_foreign_subject_or_same_pid_foreign_renderer_is_retained_before_refusal(self):
        for fault in ('malformed','unavailable','foreign','renderer'):
            with self.subTest(fault=fault):
                m=RemoteCaptureModel(self)
                def edit(role,packet):
                    if role!='viewer':return
                    if fault=='malformed':packet['source'].pop('subject')
                    elif fault=='unavailable':packet['source']['subject']['remoteJointPose']['available']=False
                    elif fault=='foreign':packet['source']['subject']['sessionId']='22222222-2222-4222-8222-222222222222'
                    else:packet['source']['worldRenderInstance']='9'*32
                m.edit=edit
                with m.held():
                    owner=m.owner()
                    with self.assertRaises(NativeUIError):owner.read(m.ticket())
                    self.assertEqual('failed',owner.state['phase']);self.assertEqual(31,m.viewer.pid)
                    self.assertEqual(int(fault=='renderer'),len(m.gpu.gpu.commands))
                    if m.viewer.state['pending'] is not None:self.assertTrue(m.viewer.state['pending']['raw'])
                    with self.assertRaises(NativeUIError):owner.original()

    def test_missing_executed_eye_or_ignored_capture_cannot_become_remote_stereo(self):
        for fault in ('eye','ignored'):
            with self.subTest(fault=fault):
                m=RemoteCaptureModel(self)
                if fault=='ignored':m.gpu.gpu.ignore=True
                else:m.gpu.models.edit=lambda packet:packet['source']['modelTrace']['models'][0]['cameraUses'].pop()
                with m.held():
                    owner=m.owner()
                    with self.assertRaises(NativeUIError):owner.read(m.ticket())
                    self.assertEqual('failed',owner.state['phase'])
                    self.assertEqual(1,len(m.gpu.gpu.commands))

    def test_lost_acquire_or_model_reply_keeps_issue_and_recovers_only_original_resources(self):
        for fault in ('lost','query_lost'):
            with self.subTest(fault=fault):
                m=RemoteCaptureModel(self);setattr(m.gpu,fault,True);m.gpu.release_lost=True
                with m.held():
                    owner=m.owner()
                    with self.assertRaises(NativeUIError):owner.read(m.ticket())
                    self.assertIsNotNone(m.gpu.owner_store().read());m.gpu.release_lost=False
                    if fault=='query_lost':
                        self.assertIsNotNone(owner.state['modelRequest'])
                        self.assertEqual(owner.state['capture']['requestId'],owner.state['modelRequest']['captureRequestId'])
                        self.assertEqual('saved',owner.state['image']['phase'])
                        self.assertEqual(m.gpu.raw,owner.images().read(owner.state['image']))
                    restored=m.owner()
                    with self.assertRaises(NativeUIError):restored.read(m.ticket())
                    proof=restored.recover();self.assertFalse(proof['memory']['present'])
                    self.assertEqual(1,len(m.gpu.gpu.commands));self.assertIsNone(m.gpu.owner_store().read())
                    with self.assertRaises(NativeUIError):restored.finish_cycle()

    def test_real_png_change_inode_link_or_root_replacement_never_becomes_original(self):
        for fault in ('bytes','inode','link','journal'):
            with self.subTest(fault=fault):
                m=RemoteCaptureModel(self)
                with m.held():
                    owner=m.owner();owner.read(m.ticket());path=owner.images().root/owner.state['image']['name']
                    if fault=='bytes':path.write_bytes(m.gpu.raw+b'foreign')
                    elif fault=='inode':
                        other=path.with_suffix('.other');other.write_bytes(m.gpu.raw);other.chmod(0o600);os.replace(other,path)
                    elif fault=='link':os.link(path,path.with_suffix('.alias'))
                    else:
                        path=owner.store.path;other=path.with_suffix('.other');other.write_bytes(path.read_bytes());other.chmod(0o600);os.replace(other,path)
                    with self.assertRaises((NativeUIError,OSError)):owner.original()
                    self.assertEqual(1,len(m.gpu.gpu.commands))

    def test_original_parent_deadline_inside_native_send_prevents_capture_without_renewal(self):
        m=self.model
        with m.held():
            owner=m.owner();candidate=owner.candidate;delayed=[]
            def expire():
                candidate()
                if owner.state['captureIntent'] is not None and not delayed:
                    delayed.append(True);m.cycle.tick(120001)
                return candidate()
            owner.candidate=expire
            with self.assertRaises(NativeUIError):owner.read(m.ticket())
            self.assertEqual('failed',owner.state['phase'])
            self.assertEqual([True],delayed);self.assertEqual([],m.gpu.gpu.commands)
            before=len(m.gpu.gpu.commands)
            with self.assertRaises(NativeUIError):m.owner()
            self.assertEqual(before,len(m.gpu.gpu.commands))

    def test_delayed_final_validation_is_durable_failed_never_cold_completed_or_reacquired(self):
        m=self.model
        with m.held():
            owner=m.owner();validate=owner.validate_frame;calls=[]
            def delayed(*args):
                value=validate(*args);calls.append(True)
                if len(calls)==2:m.cycle.s.clock+=2
                return value
            owner.validate_frame=delayed
            with self.assertRaises(NativeUIError):owner.read(m.ticket())
            self.assertEqual('failed',owner.state['phase']);self.assertIsNone(m.gpu.owner_store().read())
            restored=m.owner()
            with self.assertRaises(NativeUIError):restored.read(m.ticket())
            with self.assertRaises(NativeUIError):restored.original()
            self.assertEqual(1,len(m.gpu.gpu.commands))

    def test_original_model_guard_expiry_keeps_saved_png_and_sends_zero_late_model_queries(self):
        m=self.model
        with m.held():
            owner=m.owner();factory=owner.models;delayed=[]
            def models():
                reader=factory();guard=reader.guard
                def expire():
                    value=guard()
                    if owner.state['image'] is not None and not delayed:
                        delayed.append(True);m.cycle.tick(120001)
                    return value
                reader.guard=expire;return reader
            owner.models=models
            with self.assertRaises(NativeUIError):owner.read(m.ticket())
            self.assertEqual([True],delayed);self.assertEqual([],m.gpu.models.commands)
            self.assertEqual('saved',owner.state['image']['phase']);self.assertIsNone(owner.state['modelRequest'])
            self.assertTrue((owner.image_root()/owner.state['image']['name']).exists())
            self.assertEqual('failed',owner.state['phase']);self.assertIsNotNone(m.gpu.owner_store().read())

    def test_lost_original_journal_return_cannot_dispatch_or_be_cold_adopted(self):
        from adapters.script_journey.history import unpack
        m=self.model
        with m.held():
            owner=m.owner();write=owner.file.write
            def lost(value,previous):
                write(value,previous)
                if unpack(value['payload'])[0]['captureIntent'] is not None:raise NativeUIError('Actual saved intent with lost return')
            with patch.object(owner.file,'write',side_effect=lost),self.assertRaises(NativeUIError):owner.read(m.ticket())
            self.assertEqual([],m.gpu.gpu.commands);self.assertIsNone(m.gpu.owner_store().read())
            with self.assertRaises(NativeUIError):m.owner()
            self.assertTrue(owner.store.path.exists())

    def test_original_pending_child_is_not_adopted_or_removed_on_capture_constructor_refusal(self):
        m=self.model
        with m.held():
            owner=m.owner();orphan=owner.store.path.with_name(owner.store.path.name+'.pending-original')
            orphan.write_bytes(b'actual prepared ownership\n');orphan.chmod(0o600)
            before=(len(m.primary_calls),len(m.viewer_calls))
            with self.assertRaises(NativeUIError):m.owner()
            self.assertEqual(b'actual prepared ownership\n',orphan.read_bytes())
            self.assertEqual(before,(len(m.primary_calls),len(m.viewer_calls)));self.assertEqual([],m.gpu.gpu.commands)

    def test_actual_recycled_capture_directory_ofd_is_retained_until_real_child_exit(self):
        import subprocess,sys
        script='''import os,unittest
from pathlib import Path
from self_tests.test_pico_emote_capture import RemoteCaptureModel
from adapters.normal_ui import NativeUIError
from adapters.pico4.emote_remote_capture import UNRESOLVED_HOST_FILES
case=unittest.TestCase();m=RemoteCaptureModel(case)
with m.held():
 owner=m.owner();path=m.cycle.s.root/'foreign-ofd';path.write_bytes(b'foreign retained bytes')
 foreign=os.open(path,os.O_RDONLY);recycled=owner.file.parent.fd;os.close(recycled);os.dup2(foreign,recycled)
 try:owner.read(m.ticket())
 except NativeUIError:pass
 else:raise AssertionError('Recycled original was accepted')
 assert not owner.close_host() and owner.file in UNRESOLVED_HOST_FILES
 assert os.fstat(recycled).st_ino==path.stat().st_ino and os.pread(recycled,100,0)==b'foreign retained bytes'
 assert not m.gpu.gpu.commands
print('original OFD refused; foreign handles retained through actual host exit')
'''
        env=dict(os.environ,PYTHONPATH=str(Path(__file__).resolve().parents[1]),PYTHONDONTWRITEBYTECODE='1')
        result=subprocess.run([sys.executable,'-c',script],capture_output=True,text=True,env=env,timeout=25)
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)

    def test_callback_or_live_parent_timer_cannot_finish_a_retired_component(self):
        m=self.model;m.gpu.storage.callbacks=1
        with m.held():
            owner=m.owner()
            with self.assertRaises(NativeUIError):owner.read(m.ticket())
            self.assertIsNotNone(m.gpu.owner_store().read());self.assertIsNone(owner.state['retirement'])
            m.gpu.storage.callbacks=0;owner.recover()
        other=RemoteCaptureModel(self)
        with other.held():owner=other.owner();owner.read(other.ticket())
        other.cycle.busy='timer'
        with other.cycle.s.lock.held():
            other.parent.act(other.cycle.input.call('cancel'));other.parent.act(other.cycle.input.call('close'))
            other.cycle.s.journal.activate(RUN,'f'*32,'cleanup')
            with self.assertRaises(NativeUIError):other.parent.cleanup(sleep=other.cycle.sleep)
        with other.held(),self.assertRaises(NativeUIError):owner.finish_cycle()

    def test_actual_remaining_source_slots_are_not_reset_for_a_new_capture_index(self):
        m=self.model
        with m.held():
            for _ in range(31):m.viewer.read()
            owner=m.owner(index=2);before=(len(m.primary_calls),len(m.viewer_calls))
            with self.assertRaises(NativeUIError):owner.read(m.ticket())
            self.assertEqual(before,(len(m.primary_calls),len(m.viewer_calls)));self.assertEqual([],m.gpu.gpu.commands)
            self.assertEqual(31,len(m.viewer.previous['records']));self.assertIsNone(owner.previous)


class PicoEmoteRemoteBindingTests(unittest.TestCase):
    """Actual current Pico binding; explicit Native/GPU/Qt/ADB IO models."""
    def setUp(self):
        self.model=RemoteCaptureModel(self)
        self.adapter,self.target=self.model.canonical(self)

    def test_actual_typed_script_route_completes_normal_capture_and_quiet_cycle(self):
        from adapters.pico4.graphics_binding import PicoGraphicsBinding
        m=self.model
        with m.held():
            # This exact script lock was previously rejected by the generic
            # Graphics factory; the actual additive Emote route accepts it.
            with self.assertRaises(NativeUIError):PicoGraphicsBinding(self.adapter)._lock(self.target,m.viewer.lock)
            owner=m.owner();frame=owner.read(m.ticket())
            self.assertEqual(m.viewer.binding,owner.state['image']['binding']);self.assertEqual(1,len(m.gpu.gpu.commands))
            self.assertEqual(m.viewer.pid,frame['capture']['processId']);self.assertEqual((frame,m.gpu.raw),owner.original())
            self.assertIsNone(m.gpu.owner_store().read());self.assertEqual([],list(m.gpu.native_root.iterdir()))
        m.finish()
        with m.held():
            result=owner.finish_cycle();self.assertTrue(result['remoteDrawPngRetired']);self.assertFalse(result['wholeFeatureComplete'])

    def test_failed_source_cannot_acquire_but_same_existing_intent_retires_with_original_files(self):
        m=self.model
        with m.held():
            owned=self.adapter._emote_world_render_capture(self.target,m.viewer)
            self.assertIs(owned.source_lock,m.viewer.lock);self.assertEqual('actor',owned.owner.role)
            command=dict(schemaVersion=1,commandId='a'*32,action='feature-world-render-observe')
            owned.capture.intent(command);owned.capture.send(command)
            self.assertTrue(m.gpu.storage.present);self.assertEqual(1,len(m.gpu.gpu.commands))
            m.edit=lambda role,packet:packet['source']['subject']['remoteJointPose'].update(available=False) if role=='viewer' else None
            with self.assertRaises(NativeUIError):m.viewer.read()
            self.assertTrue(m.viewer.failed);self.assertEqual('failed',m.viewer.previous['phase'])
            before=len(m.native_commands)
            with self.assertRaises(NativeUIError):owned.capture.send(command)
            self.assertEqual(before,len(m.native_commands));self.assertIsNotNone(owned.owner.store.read())
            proof=owned.release();self.assertFalse(proof['present']);self.assertEqual(0,proof['callbacks'])
            self.assertEqual([],list(m.gpu.native_root.iterdir()));self.assertIsNone(owned.owner.store.read())
            second=dict(command,commandId='b'*32);before=len(m.native_commands)
            with self.assertRaises(NativeUIError):owned.capture.intent(second)
            with self.assertRaises(NativeUIError):owned.capture.send(second)
            self.assertEqual(before,len(m.native_commands));self.assertIsNone(owned.owner.store.read())

    def test_actual_binding_refuses_foreign_type_scope_path_lock_and_competing_owners(self):
        from copy import copy
        from adapters.pico4.avatar_remote_source import PicoRemoteAvatarSource
        from adapters.pico4.graphics_binding import PicoGraphicsBinding
        from adapters.script_journey.lock import ScriptSourceLock
        m=self.model
        with m.held():
            for fault in ('type','area','version','role','path','lock'):
                with self.subTest(fault=fault):
                    bad=copy(m.viewer)
                    if fault=='type':
                        class Foreign(PicoRemoteAvatarSource):pass
                        bad=object.__new__(Foreign);bad.__dict__.update(m.viewer.__dict__)
                    elif fault=='area':bad.phase=SimpleNamespace(area='avatar-people',run=RUN)
                    elif fault=='version':bad.identity=dict(bad.identity,picoRemoteAvatarSourceVersion=2)
                    elif fault=='role':bad.primary=None
                    elif fault=='path':bad.store=PrivateFeatureState(bad.store.path.with_name('foreign-source.json'))
                    else:bad.lock=ScriptSourceLock(PicoGraphicsBinding(self.adapter).state_path(self.target).with_name('script-sources.lock'))
                    before=len(m.native_commands)
                    with self.assertRaises((NativeUIError,RuntimeError,ValueError)):
                        self.adapter._emote_world_render_capture(self.target,bad)
                    self.assertEqual(before,len(m.native_commands))
            owned=self.adapter._emote_world_render_capture(self.target,m.viewer)
            facade=PicoGraphicsBinding(self.adapter)
            stores=[self.adapter._emote_world_render_store(self.target,'primary'),self.adapter._world_render_store(self.target)]
            stores.extend(facade.world_render_store(self.target,role=role) for role in ('primary','actor'))
            for store in stores:
                store.write({'unresolvedForeignCapture':True},None)
                with self.assertRaises((NativeUIError,RuntimeError,ValueError)):owned.owner.guard()
                store.discard(store.read())  # Only this counter's own fixture file.
            owned.owner.guard();self.assertEqual([],m.gpu.gpu.commands)


if __name__=='__main__':unittest.main()
