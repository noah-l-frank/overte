"""Actual durable image/resource ownership over explicit synthetic native IO."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from PIL import Image
from adapters.native_avatar_render import NativeAvatarRender
from adapters.native_world_model_draws import NativeWorldModelDraws
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.owned_world_render import WorldRenderOwner
from adapters.world_render_evidence import image_name
from feature_journeys.fixtures import marker_bytes
from overte_phone_emote_capture import PhoneEmoteCapture
from overte_phone_script_history import unpack
from test_emote_effects import EffectsModel
from test_emote_pixels import Pair,POLICY
from test_emote_sources import RUN,TICKET
from test_graphics_samples import Originals as WorldOriginals


class Model(EffectsModel):
    def __init__(self,root):
        super().__init__(root);self.pixel=Pair();self.avatar_sequence=0;self.model_sequence=0;self.capture_fault=None;self.extra_models=0
        self.world_root=root/'world-boundary';self.world_root.mkdir(mode=0o700)
        self.world=WorldOriginals(self.world_root);self.world.epoch=lambda:self.epoch
        self.world.storage.mutate=lambda value:value.update(instance='a'*32,capturedEpochMs=self.epoch)
        self.world.inventory.mutate=lambda value:value.update(instance='a'*32,capturedEpochMs=self.epoch)
        with Image.open(io.BytesIO(self.pixel.left)) as image:
            image.load()
            with Image.open(io.BytesIO(marker_bytes(RUN,TICKET))) as card:image.paste(card,(10,10))
            output=io.BytesIO();image.save(output,format='PNG');self.png=output.getvalue()
            self.pixel_sha=hashlib.sha256(image.tobytes()).hexdigest()
        self.world.storage.raw=self.png
        self.world.send=self.world_send
    def world_send(self,key,request):
        assert key=='capture'
        journal=PrivateFeatureState(self.root/('phone-emote-'+self.world.active_role+'-capture-'+str(self.current_index)+'.json')).read()
        assert journal is not None and unpack(journal['payload'])[0]['captureIntent']==request
        self.world.counters['capture']+=1;sequence=self.world.counters['capture'];self.world.calls.append(('capture',deepcopy(request)))
        value=deepcopy(self.pixel.first['capture']);value.update(requestId=request['commandId'],sequence=sequence,
            requestedEpochMs=self.epoch,capturedEpochMs=self.epoch)
        source=value['source'];source.update(acquisitionSequence=sequence,recordedEpochMs=self.epoch,startedEpochMs=self.epoch,capturedEpochMs=self.epoch)
        source['image'].update(name=image_name(request['commandId']),bytes=len(self.png),sha256=hashlib.sha256(self.png).hexdigest(),pixelSha256=self.pixel_sha)
        source['renderTrace'].update(frameId=uuid.uuid4().hex,recordedEpochMs=self.epoch,begunEpochMs=self.epoch,completedEpochMs=self.epoch)
        source['renderTrace']['forwardDrawCommands']=max(8,3*(self.extra_models+1))
        self.world.values['capture']=value;self.world.storage.present=True
        if self.capture_fault=='lost-return':raise RuntimeError('Synthetic lost GPU request return')
    def _world_render_capture(self,selector,*,read_only,role,require_frame_view):
        self.world.active_role=role
        return self.world._world_render_capture(selector,read_only=read_only,role=role,require_frame_view=require_frame_view)
    def _avatar_render_observer(self,_selector,*,read_only):
        assert read_only;box={}
        def send(request):
            self.avatar_sequence+=1
            source=deepcopy(self.pixel.first['avatarBefore']['source']);source['rigId']=2
            value=dict(schemaVersion=1,requestId=request['commandId'],instance='a'*32,sequence=self.avatar_sequence,processId=31,
                requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,source=source)
            if self.capture_fault=='foreign-avatar':value['instance']='f'*32
            box['value']=value
        return NativeAvatarRender(send,lambda:json.dumps(box['value']),lambda:self.epoch,lambda:self.okay,31,**self.options())
    def _world_model_draws_observer(self,_selector,*,read_only):
        assert read_only;box={}
        def send(request):
            self.model_sequence+=1;capture=self.world.values['capture'];original=capture['source']
            trace=deepcopy(self.pixel.first['draws']['source']['modelTrace']);frame=original['renderTrace']
            trace.update(**{key:frame[key] for key in ('frameId','recordedEpochMs','begunEpochMs','completedEpochMs')})
            for index in range(self.extra_models):
                row=deepcopy(trace['models'][0]);row.update(modelInstance=hashlib.sha256(('model-'+str(index)).encode()).hexdigest()[:32],
                    geometryInstance=hashlib.sha256(('geometry-'+str(index)).encode()).hexdigest()[:32],
                    loadedSourceSha256=hashlib.sha256(('source-'+str(index)).encode()).hexdigest())
                trace['models'].append(row)
            trace['drawCommands']=sum(row['drawCommands'] for row in trace['models'])
            if self.capture_fault=='foreign-draw':trace['models'][0]['modelInstance']='f'*32
            box['value']=dict(schemaVersion=1,requestId=request['commandId'],instance=capture['instance'],sequence=self.model_sequence,
                processId=31,requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,
                source=dict(modelCaptureVersion=1,captureRequestId=capture['requestId'],captureSequence=capture['sequence'],
                    acquisitionSequence=original['acquisitionSequence'],captureCapturedEpochMs=original['capturedEpochMs'],
                    imageSha256=original['image']['sha256'],pixelSha256=original['image']['pixelSha256'],modelTrace=trace))
        return NativeWorldModelDraws(send,lambda:json.dumps(box['value']),lambda:self.epoch,lambda:self.okay,31,**self.options())
    def capture(self,*,index=1,role='primary',source=None):
        self.current_index=index
        source=self.source(role) if source is None else source
        if not source.frames:source.read()
        return PhoneEmoteCapture(source,index,POLICY,monotonic=lambda:self.clock)


class EmoteCaptureTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='overte-emote-capture-');self.addCleanup(temporary.cleanup)
        self.model=Model(Path(temporary.name))
    def test_original_capture_png_and_independent_memory_receipt_absence_precede_completion(self):
        m=self.model
        with m.lock.held():
            owner=m.capture();frame=owner.read(TICKET);archived,raw=owner.original()
            self.assertEqual(frame,archived);self.assertEqual(m.png,raw);self.assertEqual('complete',owner.state['phase'])
            self.assertFalse((m.world_root/'world-primary.json').exists());self.assertEqual([],list(m.world.receipt_root.iterdir()))
            self.assertFalse(owner.state['retirement']['memory']['present'])
            self.assertEqual(['remove','inspect'],[value['operation'] for key,value in m.world.calls if key=='inventory'])
            path=m.root/owner.state['image']['name'];self.assertEqual(raw,path.read_bytes())
            proof=owner.cleanup();self.assertTrue(proof['completeImageRecord']);self.assertFalse(owner.store.path.exists());self.assertTrue(path.exists())
    def test_reconstruction_is_historical_and_cannot_replay_a_completed_acquisition(self):
        m=self.model
        with m.lock.held():
            first=m.capture();frame=first.read(TICKET);calls=len(m.world.calls)
            second=m.capture();self.assertEqual((frame,m.png),second.original());self.assertEqual(calls,len(m.world.calls))
            with self.assertRaises(NativeUIError):second.read(TICKET)
            second.cleanup()
    def test_lost_capture_return_retires_only_the_recorded_scope_without_redelivery(self):
        m=self.model;m.capture_fault='lost-return'
        with m.lock.held():
            owner=m.capture()
            with self.assertRaises(NativeUIError):owner.read(TICKET)
            self.assertEqual('reading',owner.state['phase']);self.assertIsNotNone(owner.state['retirement'])
            self.assertEqual(1,m.world.counters['capture']);self.assertFalse((m.world_root/'world-primary.json').exists())
            proof=m.capture().cleanup();self.assertFalse(proof['completeImageRecord']);self.assertEqual(1,m.world.counters['capture'])
    def test_ignored_release_or_late_callback_preserves_ownership_and_reconstructs_cleanup(self):
        for fault in ('release','callback'):
            root=self.model.root/fault;root.mkdir(mode=0o700);m=Model(root)
            if fault=='release':m.world.storage.ignore_release=True
            else:m.world.storage.callbacks=1
            with self.subTest(fault=fault),m.lock.held():
                owner=m.capture()
                with self.assertRaises(NativeUIError):owner.read(TICKET)
                self.assertTrue((m.world_root/'world-primary.json').exists());self.assertTrue(owner.store.path.exists())
                m.world.storage.ignore_release=False;m.world.storage.callbacks=0
                proof=m.capture().cleanup();self.assertFalse(proof['completeImageRecord']);self.assertEqual(1,m.world.counters['capture'])
    def test_ignored_receipt_removal_cannot_be_hidden_by_a_memory_release_ack(self):
        m=self.model;m.world.inventory.ignore_remove=True
        with m.lock.held():
            owner=m.capture()
            with self.assertRaises(NativeUIError):owner.read(TICKET)
            self.assertTrue(owner.store.path.exists());self.assertTrue((m.world_root/'world-primary.json').exists())
            self.assertTrue(list(m.world.receipt_root.iterdir()));m.world.inventory.ignore_remove=False
            self.assertFalse(m.capture().cleanup()['completeImageRecord'])
    def test_foreign_avatar_draw_or_marker_never_creates_current_image_success(self):
        for fault in ('foreign-avatar','foreign-draw','marker'):
            root=self.model.root/fault;root.mkdir(mode=0o700);m=Model(root)
            if fault=='marker':
                m.png=m.pixel.left
                with Image.open(io.BytesIO(m.png)) as image:m.pixel_sha=hashlib.sha256(image.tobytes()).hexdigest()
                m.world.storage.raw=m.png
            else:m.capture_fault=fault
            with self.subTest(fault=fault),m.lock.held():
                owner=m.capture()
                with self.assertRaises(NativeUIError):owner.read(TICKET)
                self.assertNotEqual('complete',owner.state['phase']);self.assertFalse(m.capture().cleanup()['completeImageRecord'])
    def test_failed_opened_write_is_retained_as_private_partial_evidence_and_never_decoded_as_png(self):
        m=self.model
        with m.lock.held():
            owner=m.capture();write=owner.store.write
            def lose(value,previous):
                write(value,previous)
                image=unpack(value['payload'])[0]['image']
                if image is not None and image['phase']=='opened':raise RuntimeError('Synthetic lost opened metadata return')
            with patch.object(owner.store,'write',side_effect=lose),self.assertRaises(NativeUIError):owner.read(TICKET)
            self.assertTrue(owner.failed)
            with self.assertRaises(NativeUIError):owner.cleanup()
            again=m.capture();path=m.root/again.state['image']['name'];self.assertEqual(0,path.stat().st_size)
            proof=again.cleanup();self.assertTrue(proof['retainedPartialImage']);self.assertFalse(proof['completeImageRecord'])
            self.assertTrue(path.exists());self.assertFalse((m.world_root/'world-primary.json').exists())
    def test_lost_final_metadata_write_cannot_make_the_same_live_owner_retry_native_input(self):
        m=self.model
        with m.lock.held():
            owner=m.capture();write=owner.store.write
            def lose(value,previous):
                write(value,previous)
                if unpack(value['payload'])[0]['phase']=='complete':raise RuntimeError('Synthetic lost final write return')
            with patch.object(owner.store,'write',side_effect=lose),self.assertRaises(NativeUIError):owner.read(TICKET)
            with self.assertRaises(NativeUIError):owner.read(TICKET)
            again=m.capture();frame,raw=again.original();self.assertEqual(m.png,raw);self.assertEqual(1,m.world.counters['capture'])
            self.assertTrue(again.cleanup()['completeImageRecord']) # Complete historical record, not a fresh feature pass.
    def test_phase_change_during_acquisition_rejects_publication_but_permits_owned_resource_cleanup(self):
        m=self.model
        with m.lock.held():
            owner=m.capture();original=owner.source.phase.status;calls=[0]
            def status(previous=None):
                calls[0]+=1
                if calls[0]==2:m.journal.activate(RUN,'e'*32,'open',{})
                return original(previous)
            owner.source.phase.status=status
            with self.assertRaises(NativeUIError):owner.read(TICKET)
            self.assertFalse(m.capture().cleanup()['completeImageRecord'])
    def test_missing_or_replaced_original_png_prevents_historical_read_and_scope_retirement(self):
        m=self.model
        with m.lock.held():
            owner=m.capture();owner.read(TICKET);path=m.root/owner.state['image']['name'];path.unlink()
            with self.assertRaises(OSError):owner.original()
            with self.assertRaises(OSError):owner.cleanup()
            self.assertTrue(owner.store.path.exists())
    def test_foreign_existing_capture_is_not_adopted_or_released(self):
        m=self.model
        with m.lock.held():
            owner=m.capture();owned=m._world_render_capture('x',read_only=True,role='primary',require_frame_view=True)
            owned.owner.intent(dict(schemaVersion=1,commandId='f'*32,action='feature-world-render-observe'));before=owned.owner.owned()
            with self.assertRaises(NativeUIError):owner.read(TICKET)
            self.assertEqual(before,owned.owner.owned());self.assertEqual(0,m.world.counters['capture']);self.assertFalse(owner.store.path.exists())
    def test_source_memory_or_journal_substitution_cannot_establish_original_native_birth(self):
        m=self.model
        with m.lock.held():
            source=m.source();source.read();source.frames[-1]['group']['native']['instance']='f'*32
            with self.assertRaises(NativeUIError):m.capture(source=source)
    def test_missing_measurement_owner_after_a_delivered_request_cannot_be_called_clean(self):
        m=self.model;m.world.storage.ignore_release=True
        with m.lock.held():
            owner=m.capture()
            with self.assertRaises(NativeUIError):owner.read(TICKET)
            store=PrivateFeatureState(m.world_root/'world-primary.json');store.discard(store.read())
            with self.assertRaises(NativeUIError):m.capture().cleanup()
            self.assertTrue(owner.store.path.exists())
    def test_late_final_decode_cannot_publish_stale_originals_under_a_frozen_device_clock(self):
        import overte_phone_emote_capture as captures
        m=self.model
        with m.lock.held():
            owner=m.capture();decode=captures.original_pixels;calls=[0]
            def delayed(*args):
                result=decode(*args);calls[0]+=1
                if calls[0]==2:m.clock+=1.6
                return result
            with patch.object(captures,'original_pixels',side_effect=delayed),self.assertRaises(NativeUIError):owner.read(TICKET)
            self.assertEqual('complete',owner.state['phase']);self.assertEqual(1,m.world.counters['capture'])
            # It remains a complete historical record; no fresh result was returned.
            self.assertTrue(m.capture().cleanup()['completeImageRecord'])
    def test_roles_and_acquisition_indices_keep_separate_original_files_and_metadata(self):
        m=self.model
        with m.lock.held():
            names=[]
            for role,index in (('primary',1),('primary',2),('actor',1)):
                owner=m.capture(role=role,index=index);owner.read(TICKET);names.append(owner.state['image']['name']);owner.cleanup()
            self.assertEqual(3,len(set(names)));self.assertEqual(3,m.world.counters['capture'])

    def test_preexisting_png_created_after_planned_intent_is_neither_adopted_nor_removed(self):
        m=self.model
        with m.lock.held():
            owner=m.capture();intent=owner._image_intent
            def foreign(value):
                intent(value)
                if value['phase']=='planned':
                    path=m.root/value['name'];path.write_bytes(b'foreign original');path.chmod(0o600)
            owner._image_intent=foreign
            with self.assertRaises(NativeUIError):owner.read(TICKET)
            again=m.capture();path=m.root/again.state['image']['name']
            with self.assertRaises(NativeUIError):again.cleanup()
            self.assertEqual(b'foreign original',path.read_bytes());self.assertTrue(again.store.path.exists())

    def test_late_output_copy_cannot_hide_behind_frozen_native_and_fixture_clocks(self):
        import overte_phone_emote_capture as captures
        m=self.model
        def slow(value):
            result=deepcopy(value)
            if type(value) is dict and set(value)=={'ticket','avatarBefore','avatarAfter','capture','draws'}:m.clock+=1.6
            return result
        with m.lock.held():
            owner=m.capture()
            with patch.object(captures,'deepcopy',side_effect=slow),self.assertRaises(NativeUIError):owner.read(TICKET)
            self.assertEqual(1,m.world.counters['capture']);self.assertFalse((m.world_root/'world-primary.json').exists())
            self.assertTrue(m.capture().cleanup()['completeImageRecord'])

    def test_maximum_native_model_table_stays_within_existing_private_metadata_limit(self):
        m=self.model;m.extra_models=127
        with m.lock.held():
            owner=m.capture();frame=owner.read(TICKET)
            self.assertEqual(128,len(frame['draws']['source']['modelTrace']['models']))
            self.assertLessEqual(owner.store.path.stat().st_size,65536);owner.cleanup()

    def test_interrupted_parent_source_observation_allows_only_retirement_of_an_existing_child(self):
        m=self.model
        with m.lock.held():
            owner=m.capture();owner.read(TICKET);source=owner.source
            source.state.update(phase='reading',pending=dict(startedEpochMs=m.epoch,role='primary',
                revision=source.state['revision'],original=None,manifest=None));source.save()
            recovered=m.capture(source=source)
            with self.assertRaises(NativeUIError):recovered.read(TICKET)
            self.assertTrue(recovered.cleanup()['completeImageRecord']);self.assertEqual(1,m.world.counters['capture'])
            self.assertTrue(source.store.path.exists());self.assertEqual('reading',source.state['phase'])
            with self.assertRaises(NativeUIError):m.capture(index=2,source=source)


if __name__=='__main__':unittest.main()
