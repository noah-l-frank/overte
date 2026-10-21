"""Real scoped sampler/owners/native protocols at synthetic rendering boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
import uuid
from unittest.mock import patch
from adapters.graphics_journey.samples import GraphicsSamples,GraphicsMarkerPending
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.native_graphics_subject import NativeGraphicsSubject
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.owned_world_render import WorldRenderOwner
from adapters.pico4.graphics_binding import SerializedWorldCapture
from adapters.script_journey.files import ScriptFileIO
from adapters.script_journey.lock import ScriptSourceLock
from adapters.world_render_evidence import NativeWorldRenderCapture
from adapters.world_render_storage import NativeWorldRenderStorage,receipt_file
from adapters.world_render_receipts import NativeWorldReceiptInventory,NativeWorldReceiptBatchFiles
from feature_journeys.witness import Client
from feature_journeys.stereo_graphics_evidence import PROFILE,observation
from self_tests.test_stereo_graphics_evidence import Source,JourneyPixels,RUN,TICKET,ROOT
from self_tests.test_native_feature_observation import Boundary as FeatureBoundary
from self_tests.test_native_graphics_subject import Boundary as SubjectBoundary
from self_tests.test_pico_graphics_source import Boundary as UiBoundary
from self_tests.test_world_render_storage import Boundary as StorageBoundary
from self_tests.test_world_render_receipt_inventory import Boundary as InventoryBoundary


class Model:
    def __init__(self):
        self.temporary=tempfile.TemporaryDirectory();self.root=Path(self.temporary.name);self.artifacts=self.root/'artifacts';self.artifacts.mkdir(mode=0o700)
        self.native_root=self.root/'native';self.native_root.mkdir(mode=0o700)
        self.fixture=Source();self.raw,self.body,_=self.fixture.acquire();self.binding=deepcopy(self.body['binding'])
        self.clock=0.;self.okay=True;self.active=TICKET;self.stale=False;self.capture_error=False;self.lose_candidate=False
        self.features=FeatureBoundary();self.features.mutate=lambda v:v.update(processId=31,graphics=deepcopy(self.body['nativeBefore']['graphics']))
        self.subject=SubjectBoundary();self.subject.source=deepcopy(self.body['subjectBefore']['source'])
        self.ui=UiBoundary();self.ui.shown=False;self.ui.roots=[];self.ui.controls=[]
        self.gpu=JourneyPixels();self.storage=StorageBoundary();self.storage.mutate=lambda v:v.update(instance='a'*32)
        self.inventory=InventoryBoundary(self.native_root)
        for path in self.native_root.iterdir():path.unlink()
        self.inventory.issued.clear();self.inventory.mutate=lambda v:v.update(instance='a'*32)
        self.tablet_sequence=0;self.tablet=None;self.commands=[]
        self.lock=ScriptSourceLock(self.root/'script-sources.lock')
        self.client=object.__new__(Client);self.client.url=ROOT.rsplit('/runs/',1)[0];self.client.run=RUN;self.client.area='graphics'
        self.client.graphics_instance=self.fixture.provider.instance;self.client.graphics_previous=None
        self.client.graphics_status=self.status;self.client.request=self.request
    def close(self):self.temporary.cleanup()
    def guard(self):
        if not self.okay:raise NativeUIError('Synthetic candidate lost')
        return True
    def sleep(self,seconds):self.clock+=seconds
    def status(self):
        value=self.fixture.provider.snapshot(RUN,uuid.uuid4().hex);self.client.graphics_previous=deepcopy(value);return value
    def request(self,path):
        assert path=='/runs/'+RUN+'/active'
        return dict(schemaVersion=1,runId=RUN,area='graphics',ticket=self.active,stimulus=dict(verb='baseline',inputs={}))
    def activate(self,ticket):self.fixture.provider.activate(RUN,ticket);self.active=ticket
    def state_path(self,_target):return self.root/'state.json'
    def normal_feature_runtime(self,_target,*,read_only):
        assert read_only;self.guard();return None,None,deepcopy(self.binding),self.guard,None
    def _native_feature_observer(self,_target,*,read_only):
        assert read_only
        return NativeFeatureObservation(self.features.send,self.features.original,lambda:20000,self.guard,31,monotonic=lambda:self.clock,sleep=self.sleep)
    def _graphics_subject_observer(self,_target,*,read_only):
        assert read_only
        return NativeGraphicsSubject(self.subject.send,self.subject.original,lambda:20000,self.guard,31,require_framework=True,
            monotonic=lambda:self.clock,sleep=self.sleep)
    def _graphics_ui_observer(self,_target,*,read_only):assert read_only;return self.ui.source()
    def _script_file_io(self,_target,*,read_only):
        assert read_only
        def send(envelope):
            request=envelope['request'];assert request['action']=='observe';self.commands.append(deepcopy(envelope));self.tablet_sequence+=1
            self.tablet=dict(schemaVersion=1,commandId=request['commandId'],action='observe',instance='e'*32,generation='f'*32,
                sourceSequence=self.tablet_sequence,lastCommandSequence=0,elapsedMs=0,capturedEpochMs=20000,processId=31,
                fileControlsVersion=1,ready=True,controls=[],scriptInventory=dict(inventoryVersion=1,complete=True,
                    managers=[],pickers=[],tabletPresent=True,tabletShown=False))
        return ScriptFileIO(send,lambda:json.dumps(self.tablet),lambda:20000,self.guard,31,monotonic=lambda:self.clock,sleep=self.sleep)
    def owner_store(self,role):return PrivateFeatureState(self.root/('capture-'+role+'.json'))
    def _world_render_capture(self,_target,*,read_only,role,require_frame_view,source_lock):
        assert read_only and require_frame_view and source_lock is self.lock;source_lock.assert_held()
        def guard():
            self.lock.assert_held();self.guard()
            assert self.owner_store('actor' if role=='primary' else 'primary').read() is None
            return True
        owner=WorldRenderOwner(self.owner_store(role),self.binding,guard,role=role)
        def send_storage(command):
            self.storage.intents.append(deepcopy(command));self.storage.send(command)
            name=receipt_file(command['commandId']);path=self.native_root/name;path.write_text(self.storage.files[name]);path.chmod(0o600)
            self.inventory.issued[command['commandId']]=(command['requestId'],hashlib.sha256(path.read_bytes()).hexdigest())
            self.inventory.owner=deepcopy(owner.owned());self.inventory.retired=not self.storage.present
            self.inventory.present=self.storage.present;self.inventory.callbacks=self.storage.callbacks
            self.inventory.png_bytes=len(self.storage.raw) if self.storage.present else 0
        storage=NativeWorldRenderStorage(send_storage,self.storage.read,lambda:20000,guard,31,receipt_intent=owner.receipt_intent,
            monotonic=lambda:self.clock,sleep=self.sleep)
        def send_capture(command):
            assert owner.owned()['capture']==command
            self.gpu.intents.append(deepcopy(command));self.gpu.advance()
            pixels=JourneyPixels(card_ticket=TICKET if self.stale else self.active)
            self.gpu.raw,self.gpu.pixels=pixels.raw,pixels.pixels;self.storage.raw=pixels.raw;self.storage.present=True
            self.gpu.send(command)
            if self.lose_candidate:self.okay=False
            if self.capture_error:raise NativeUIError('Synthetic lost capture result')
        capture=NativeWorldRenderCapture(send_capture,self.gpu.original,storage,lambda:20000,guard,31,intent=owner.intent,
            stereo=True,require_cameras=True,monotonic=lambda:self.clock,sleep=self.sleep)
        inventory=NativeWorldReceiptInventory(self.inventory.send,self.inventory.original,lambda:20000,guard,31,owner.owned,
            lambda:storage.instance,monotonic=lambda:self.clock,sleep=self.sleep)
        receipts=NativeWorldReceiptBatchFiles(SimpleNamespace(read=lambda name:(self.native_root/name).read_text()),inventory)
        return SerializedWorldCapture(capture,storage,owner,receipts,source_lock=self.lock)
    def samples(self,role='primary'):
        return GraphicsSamples(self,'owned',self.client,RUN,self.fixture.provider.instance,role,0,self.lock,self.artifacts,PROFILE,
            epoch_ms=lambda:20000,monotonic=lambda:self.clock)


class PicoGraphicsSampleTests(unittest.TestCase):
    def setUp(self):self.model=Model();self.addCleanup(self.model.close)
    def test_original_native_stereo_frame_and_both_artifacts_are_joined_and_capture_is_fully_retired(self):
        m=self.model
        with m.lock.held():
            owner=m.samples();value=owner.read(TICKET,20000);self.assertEqual('ready',owner.state['phase'])
            self.assertEqual([],value['resources']);self.assertEqual(2,len(owner.state['images']))
            self.assertTrue(Path(value['imagePath']).is_file());self.assertTrue(Path(value['metadataPath']).is_file())
            self.assertIsNone(m.owner_store('primary').read());self.assertEqual([],list(m.native_root.iterdir()))
            archived=GraphicsSamples.archive(owner.previous,client=m.client,run=RUN,provider_instance=m.fixture.provider.instance,
                role='primary',stage=0,binding=m.binding,artifact_root=m.artifacts,image_policy=PROFILE)
            self.assertEqual(1,archived['sequence']);self.assertEqual(value['state'],owner._historical(owner.state['frame'])['state'])
        self.assertEqual(1,len(m.gpu.commands));self.assertTrue(all(c['action']=='feature-native-observe' for c in m.features.commands))


    def test_successive_recreated_samples_keep_original_source_cursors_and_reject_a_stale_competing_owner(self):
        m=self.model
        with m.lock.held():
            old=m.samples();old.read(TICKET,20000);new=m.samples();new.read(TICKET,20000)
            self.assertEqual(2,new.state['sequence']);self.assertEqual(4,len(new.state['images']))
            self.assertGreater(new.state['frame']['capture']['source']['stereo']['executionSequence'],old.state['frame']['capture']['source']['stereo']['executionSequence'])
            before=len(m.gpu.commands)
            with self.assertRaises(NativeUIError):old.read(TICKET,20000)
            self.assertEqual(before,len(m.gpu.commands));self.assertEqual('ready',m.samples().state['phase'])

    def test_original_producer_pair_passes_the_external_independent_stereo_verifier(self):
        m=self.model
        with m.lock.held():
            owner=m.samples();actual=owner.read(TICKET,20000);frame=owner.state['frame']
            sample=dict(schemaVersion=1,contractVersion=16,runId=RUN,sequence=actual['sequence'],capturedEpochMs=actual['capturedEpochMs'],
                state=actual['state'],resources=actual['resources'],lifecycle=actual['lifecycle'],artifacts=[
                    dict(kind='image',name=frame['image']['name'],sequence=actual['sequence'],capturedEpochMs=frame['capture']['capturedEpochMs'],
                        ticket=TICKET,source='world-render-target'),
                    dict(kind='file',name=frame['metadata']['name'],sequence=actual['sequence'],capturedEpochMs=frame['capture']['capturedEpochMs'],ticket=TICKET)])
            evidence,_=observation(Path(actual['imagePath']).read_bytes(),Path(actual['metadataPath']).read_bytes(),RUN,TICKET,ROOT,PROFILE,sample)
            self.assertEqual(actual['image']['sha256'],evidence['sha256']);self.assertEqual({'left','right'},set(evidence['eyes']))

    def test_primary_and_actor_keep_separate_native_queries_files_and_owners(self):
        m=self.model
        with m.lock.held():
            primary=m.samples();primary.read(TICKET,20000);previous=deepcopy(primary.previous)
            actor=m.samples('actor');actor.read(TICKET,20000)
            self.assertEqual(previous,primary.store.read());self.assertNotEqual(primary.store.path,actor.store.path)
            self.assertTrue(all(value['role']=='actor' for value in actor.state['images']))
            self.assertTrue({value['name'] for value in primary.state['images']}.isdisjoint({value['name'] for value in actor.state['images']}))
            with self.assertRaises(NativeUIError):GraphicsSamples.archive(actor.previous,client=m.client,run=RUN,
                provider_instance=m.fixture.provider.instance,role='primary',stage=0,binding=m.binding,artifact_root=m.artifacts,image_policy=PROFILE)
            m.samples().read(TICKET,20000);self.assertEqual(3,len(m.gpu.commands));self.assertEqual([],list(m.native_root.iterdir()))

    def test_stale_marker_is_retired_as_rejected_history_before_a_new_actual_frame(self):
        m=self.model;m.activate('e'*32);m.stale=True
        with m.lock.held():
            owner=m.samples()
            with self.assertRaises(GraphicsMarkerPending):owner.read(m.active,20000)
            self.assertEqual('reading',owner.state['phase']);self.assertEqual(2,len(owner.state['images']))
            self.assertIsNone(m.owner_store('primary').read())
            with self.assertRaises(NativeUIError):m.samples()
            owner.retire_marker_not_ready();self.assertEqual('ready',owner.state['phase']);self.assertEqual(1,len(owner.state['readiness']))
            m.stale=False;owner=m.samples();value=owner.read(m.active,20000)
            self.assertEqual(2,value['sequence']);self.assertEqual(2,len(m.gpu.commands));self.assertEqual(4,len(owner.state['images']))

    def test_missing_or_changed_metadata_prevents_owner_recreation_without_native_recapture(self):
        m=self.model
        with m.lock.held():
            owner=m.samples();value=owner.read(TICKET,20000);previous=deepcopy(owner.previous);path=Path(value['metadataPath']);original=path.read_bytes()
            path.write_bytes(original[:-1]);before=len(m.gpu.commands)
            with self.assertRaises((NativeUIError,OSError,ValueError)):m.samples()
            self.assertEqual(previous,owner.store.read());self.assertEqual(before,len(m.gpu.commands))
            path.write_bytes(original);m.samples();path.unlink()
            with self.assertRaises((NativeUIError,OSError,ValueError)):m.samples()
            self.assertEqual(previous,owner.store.read());self.assertEqual(before,len(m.gpu.commands))

    def test_partial_lost_metadata_commit_recovers_only_to_retired_history_after_ticket_change(self):
        m=self.model
        with m.lock.held():
            owner=m.samples();intent=owner.images.intent
            def lost(value):
                if value['kind']=='file' and value['phase']=='saved':raise OSError('Synthetic lost metadata saved journal')
                return intent(value)
            with patch.object(owner.images,'intent',side_effect=lost),self.assertRaises(OSError):owner.read(TICKET,20000)
            self.assertEqual(['saved','opened'],[row['phase'] for row in owner.state['images']]);self.assertIsNone(m.owner_store('primary').read())
            with self.assertRaises(NativeUIError):m.samples()
            m.activate('e'*32);proof=owner.retire_changed_ticket();self.assertEqual(TICKET,proof['ticket'])
            self.assertEqual('ready',owner.state['phase']);self.assertTrue(all(row['phase']=='saved' for row in owner.state['images']))
            self.assertEqual(1,len(m.gpu.commands));self.assertIsNone(owner.state['frame']);m.samples()

    def test_ignored_native_receipt_removal_keeps_capture_owner_until_original_absence(self):
        m=self.model;m.inventory.ignore_remove=True
        with m.lock.held():
            owner=m.samples()
            with self.assertRaises(NativeUIError):owner.read(TICKET,20000)
            self.assertIsNotNone(m.owner_store('primary').read());self.assertTrue(list(m.native_root.iterdir()))
            self.assertFalse(m.storage.present);m.inventory.ignore_remove=False;m.activate('e'*32)
            owner.retire_changed_ticket();self.assertIsNone(m.owner_store('primary').read())
            self.assertEqual([],list(m.native_root.iterdir()));self.assertEqual(1,len(m.gpu.commands));m.samples()

    def test_candidate_loss_after_dispatch_keeps_uncertain_capture_and_blocks_new_samples(self):
        m=self.model;m.lose_candidate=True
        with m.lock.held():
            owner=m.samples()
            with self.assertRaises(NativeUIError):owner.read(TICKET,20000)
            previous=deepcopy(owner.store.read());capture=deepcopy(m.owner_store('primary').read())
            self.assertIsNotNone(capture);self.assertEqual(1,len(m.gpu.commands));self.assertEqual([],m.storage.commands)
            with self.assertRaises(NativeUIError):m.samples()
            self.assertEqual(previous,owner.store.read());self.assertEqual(capture,m.owner_store('primary').read())

    def test_retained_hidden_graphics_root_is_measured_as_an_actual_resource(self):
        m=self.model;m.ui.roots=[dict(id='d'*32,profile='graphics-generic-v1',visible=False,inCurrentTree=False,
            callbackRunning=False,callbackItemPresent=False)]
        with m.lock.held():
            value=m.samples().read(TICKET,20000)
            self.assertFalse(value['state']['dialog']);self.assertEqual(['panel:graphics'],value['resources'])

    def test_camera_cursor_replay_cannot_publish_even_with_a_new_control_nonce_and_frame(self):
        m=self.model
        with m.lock.held():
            owner=m.samples();owner.read(TICKET,20000);m.gpu.uniform_sequence-=3
            owner=m.samples()
            with self.assertRaises(NativeUIError):owner.read(TICKET,20000)
            self.assertEqual('reading',owner.state['phase']);self.assertIsNone(m.owner_store('primary').read())
            self.assertEqual(2,len(m.gpu.commands));self.assertEqual([],list(m.native_root.iterdir()))


if __name__=='__main__':unittest.main()
