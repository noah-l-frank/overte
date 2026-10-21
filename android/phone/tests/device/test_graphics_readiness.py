"""Fresh independently sampled synthetic frames and real rejected-image ownership."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
sys.path.insert(0,str(ROOT/'tests/device/adapters/android-phone'))
from PIL import Image
from adapters.normal_ui import NativeUIError
from feature_journeys.fixtures import challenge
from overte_phone_graphics_readiness import PhoneGraphicsReadiness
from overte_phone_graphics_samples import PhoneGraphicsSamples,GraphicsMarkerPending
from overte_phone_script_history import unpack,pack
import test_graphics_samples as original_fixture

RUN,TICKET,POLICY,BINDING=original_fixture.RUN,original_fixture.TICKET,original_fixture.POLICY,original_fixture.BINDING
FOREIGN='f'*32


class Originals(original_fixture.Originals):
    """Each new source acquisition has its own simulated actual clock/pixels."""
    def __init__(self,root):
        super().__init__(root);self.schedule=[FOREIGN,TICKET]
        self.storage.mutate=lambda packet:packet.update(instance='a'*32,capturedEpochMs=self.epoch())
        self.inventory.mutate=lambda packet:packet.update(instance='a'*32,capturedEpochMs=self.epoch())
    def epoch(self):return 20000+round(self.clock*1000)
    def image(self,marker):
        self.scene.image(ticket=marker if marker!='ambiguous' else FOREIGN)
        if marker=='ambiguous':
            image=Image.open(io.BytesIO(self.scene.pixels)).convert('RGBA');image.paste((128,128,128,255),tuple(POLICY['marker']))
            output=io.BytesIO();image.save(output,format='PNG');self.scene.pixels=output.getvalue()
            self.scene.capture['source']['image'].update(bytes=len(self.scene.pixels),sha256=hashlib.sha256(self.scene.pixels).hexdigest(),
                pixelSha256=hashlib.sha256(image.tobytes()).hexdigest())
        self.storage.raw=self.scene.pixels
    def send(self,key,request):
        if key=='capture':self.image(self.schedule[min(self.counters['capture'],len(self.schedule)-1)])
        super().send(key,request)
        # Stamp this newly sampled synthetic packet, never a saved original.
        def stamp(value):
            if type(value) is dict:
                for field,item in value.items():
                    if field.endswith('EpochMs') and type(item) is int:value[field]=self.epoch()
                    else:stamp(item)
            elif type(value) is list:
                for item in value:stamp(item)
        stamp(self.values[key])
    def provider(self):
        value=super().provider();value['capturedEpochMs']=self.epoch();self.client.graphics_previous=deepcopy(value);return value
    def sleep(self,seconds):self.clock+=seconds
    def wrapper(self,samples):return PhoneGraphicsReadiness(samples,monotonic=lambda:self.clock,sleep=self.sleep)


class GraphicsReadinessTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='overte-graphics-readiness-');self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.boundary=Originals(self.root)
    def test_rejected_marker_is_original_history_and_only_an_entirely_new_current_frame_can_return(self):
        b=self.boundary
        with b.lock.held():
            samples=b.factory();actual=b.wrapper(samples).read(TICKET,20000)
            self.assertEqual(2,b.counters['capture']);self.assertEqual(2,actual['sequence']);self.assertEqual(21000,actual['capturedEpochMs'])
            self.assertEqual(1,len(samples.state['readiness']));rejected=samples.state['readiness'][0]
            self.assertEqual(challenge(RUN,FOREIGN).hex(),rejected['marker']['observed'])
            self.assertNotEqual(rejected['frame']['capture']['requestId'],samples.state['frame']['capture']['requestId'])
            self.assertNotEqual(rejected['frame']['capture']['source']['renderTrace']['frameId'],samples.state['frame']['capture']['source']['renderTrace']['frameId'])
            self.assertNotEqual(rejected['frame']['image']['name'],Path(actual['imagePath']).name)
            self.assertTrue((self.root/rejected['frame']['image']['name']).exists());self.assertEqual([],list(b.receipt_root.iterdir()))
            self.assertFalse((self.root/'world-primary.json').exists());self.assertEqual('ready',samples.state['phase'])

    def test_ambiguous_first_marker_never_becomes_facts_and_a_new_independent_frame_can_become_ready(self):
        b=self.boundary;b.schedule=['ambiguous',TICKET]
        with b.lock.held():
            samples=b.factory();actual=b.wrapper(samples).read(TICKET,20000)
            self.assertEqual(2,actual['sequence']);marker=samples.state['readiness'][0]['marker']
            self.assertEqual('ambiguous',marker['reason']);self.assertEqual([128,128,128],marker['rgb']);self.assertIsNone(marker['observed'])

    def test_persistently_foreign_frames_exhaust_the_bound_and_cannot_return_an_old_or_empty_sample(self):
        b=self.boundary;b.schedule=[FOREIGN]
        with b.lock.held():
            samples=b.factory()
            with self.assertRaises(NativeUIError):b.wrapper(samples).read(TICKET,20000)
            self.assertEqual(16,b.counters['capture']);self.assertEqual(16,len(samples.state['readiness']))
            self.assertIsNone(samples.state['frame']);self.assertEqual('ready',samples.state['phase'])
            self.assertFalse((self.root/'world-primary.json').exists());self.assertEqual([],list(b.receipt_root.iterdir()))

    def test_later_readiness_failure_cannot_fall_back_to_a_previously_accepted_frame(self):
        b=self.boundary;b.schedule=[TICKET]
        with b.lock.held():
            samples=b.factory();before=b.wrapper(samples).read(TICKET,20000);original=deepcopy(samples.state['frame'])
            b.schedule=[FOREIGN]
            with self.assertRaises(NativeUIError):b.wrapper(samples).read(TICKET,20000)
            self.assertEqual(original,samples.state['frame']);self.assertEqual(17,b.counters['capture'])
            self.assertEqual(before['imagePath'],str(self.root/samples.state['frame']['image']['name']))

    def test_later_success_keeps_the_entire_rejected_source_cursor_snapshot_immutable(self):
        b=self.boundary
        with b.lock.held():
            samples=b.factory()
            with self.assertRaises(GraphicsMarkerPending):samples.read(TICKET,20000)
            first=samples.retire_marker_not_ready();b.sleep(1);samples.read(TICKET,20000)
            self.assertEqual(first,samples.state['readiness'][0])
            self.assertGreater(samples.state['cursors']['native']['sequence'],first['cursors']['native']['sequence'])

    def test_recreation_cannot_adopt_even_a_fully_retired_pending_marker_frame(self):
        b=self.boundary
        with b.lock.held():
            samples=b.factory()
            with self.assertRaises(GraphicsMarkerPending):samples.read(TICKET,20000)
            with self.assertRaises(NativeUIError):b.factory()
            samples.retire_marker_not_ready();self.assertNotIn('state',samples.state['readiness'][0])
            result=b.factory().read(TICKET,20000);self.assertEqual(2,result['sequence']);self.assertEqual(2,b.counters['capture'])

    def test_ignored_memory_retirement_is_fatal_and_never_enters_the_readiness_retry_loop(self):
        b=self.boundary;b.storage.ignore_release=True
        with b.lock.held():
            samples=b.factory()
            with self.assertRaises(NativeUIError):b.wrapper(samples).read(TICKET,20000)
            self.assertEqual(1,b.counters['capture']);self.assertEqual([],samples.state['readiness'])
            self.assertTrue((self.root/'world-primary.json').exists());self.assertEqual('reading',samples.state['phase'])

    def test_ignored_receipt_retirement_stays_owned_without_another_capture(self):
        b=self.boundary;b.inventory.ignore_remove=True
        with b.lock.held():
            samples=b.factory()
            with self.assertRaises(NativeUIError):b.wrapper(samples).read(TICKET,20000)
            self.assertEqual(1,b.counters['capture']);self.assertEqual([],samples.state['readiness'])
            self.assertTrue((self.root/'world-primary.json').exists());self.assertTrue(list(b.receipt_root.iterdir()))

    def test_other_source_failures_cannot_be_reclassified_as_marker_readiness(self):
        b=self.boundary;b.scene.subject_before['source']['view']['position'][0]=1
        b.scene.subject_after['source']['view']['position'][0]=1
        with b.lock.held():
            samples=b.factory()
            with self.assertRaises(NativeUIError):b.wrapper(samples).read(TICKET,20000)
            self.assertEqual(1,b.counters['capture']);self.assertEqual([],samples.state['readiness'])
            with self.assertRaises(NativeUIError):samples.retire_marker_not_ready()

    def test_ignored_marker_retirement_write_cannot_forget_original_cursors_and_retry(self):
        b=self.boundary
        with b.lock.held():
            samples=b.factory();original=samples.store.write
            def ignored(value,previous):
                if unpack(value['payload'])[0]['readiness']:return None
                return original(value,previous)
            with patch.object(samples.store,'write',side_effect=ignored),self.assertRaises(NativeUIError):b.wrapper(samples).read(TICKET,20000)
            self.assertEqual(1,b.counters['capture'])
            with self.assertRaises(NativeUIError):b.factory()

    def test_missing_rejected_original_png_prevents_scope_retirement(self):
        b=self.boundary
        with b.lock.held():
            samples=b.factory()
            with self.assertRaises(GraphicsMarkerPending):samples.read(TICKET,20000)
            (self.root/samples.state['pending']['markerFrame']['image']['name']).unlink()
            with self.assertRaises(FileNotFoundError):samples.retire_marker_not_ready()
            self.assertEqual('reading',samples.state['phase']);self.assertEqual(1,b.counters['capture'])

    def test_marker_history_cannot_be_relabelled_as_a_different_observation_or_capture(self):
        b=self.boundary
        with b.lock.held():
            samples=b.factory();b.wrapper(samples).read(TICKET,20000);original=samples.store.read()
            for fault in ('marker','capture','role','sequence'):
                changed=deepcopy(original);state=unpack(changed['payload'])[0];item=state['readiness'][0]
                if fault=='marker':item['marker']['observed']='0'*32
                elif fault=='capture':item['frame']['capture']['requestId']='0'*32
                elif fault=='role':item['frame']['image']['role']='actor'
                else:item['sequence']=state['sequence']
                changed['payload']=pack([state]);samples.store.write(changed,samples.store.read())
                with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):b.factory()
                samples.store.write(original,changed)

    def test_changed_ticket_uses_existing_scope_retirement_and_never_relabels_failed_marker_facts(self):
        b=self.boundary
        with b.lock.held():
            samples=b.factory()
            with self.assertRaises(GraphicsMarkerPending):samples.read(TICKET,20000)
            b.change_phase()
            with self.assertRaises(NativeUIError):samples.retire_marker_not_ready()
            event=samples.retire_changed_ticket();self.assertIsNotNone(event['markerFrame']);self.assertNotIn('state',event)
            b.schedule=['7'*32];actual=b.factory().read('7'*32,20000)
            self.assertEqual(2,actual['sequence']);self.assertEqual(2,b.counters['capture'])

    def test_completed_rejected_frame_archives_are_pure_and_still_require_original_bytes(self):
        b=self.boundary
        with b.lock.held():
            samples=b.factory();b.wrapper(samples).read(TICKET,20000);value=samples.store.read()
        b.fail_runtime=True
        options=dict(client=b.client,run=RUN,provider_instance=b.scene.instance,role='primary',stage=0,
            binding=BINDING,artifact_root=self.root,image_policy=POLICY)
        state=PhoneGraphicsSamples.archive(value,**options);self.assertEqual(1,len(state['readiness']))
        (self.root/state['readiness'][0]['frame']['image']['name']).write_bytes(b'foreign replacement')
        with self.assertRaises(NativeUIError):PhoneGraphicsSamples.archive(value,**options)

    def test_readiness_deadline_includes_accepted_retirement_and_never_returns_cached_success(self):
        b=self.boundary
        with b.lock.held():
            samples=b.factory();original=samples.retire_marker_not_ready
            def late():value=original();b.clock+=21;return value
            with patch.object(samples,'retire_marker_not_ready',side_effect=late),self.assertRaises(NativeUIError):b.wrapper(samples).read(TICKET,20000)
            self.assertEqual(1,b.counters['capture']);self.assertIsNone(samples.state['frame'])

    def test_frozen_native_clock_cannot_hide_a_slow_rejected_image_before_retry(self):
        b=self.boundary;b.epoch=lambda:20000
        with b.lock.held():
            samples=b.factory();original=samples.images.write
            def slow(*args):value=original(*args);b.clock+=2;return value
            with patch.object(samples.images,'write',side_effect=slow),self.assertRaises(NativeUIError):b.wrapper(samples).read(TICKET,20000)
            self.assertEqual(1,b.counters['capture']);self.assertEqual([],samples.state['readiness'])
            with self.assertRaises(NativeUIError):samples.retire_marker_not_ready()
