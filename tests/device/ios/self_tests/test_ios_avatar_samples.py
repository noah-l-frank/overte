"""Real private PNG/chunk owners with synthetic native/Qt/phase producers.

Marker admission is an explicitly modeled seam here; its independent whole
normal-Script/Node/code/UUID/quiet owner is exercised by marker_scope tests.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from PIL import Image
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.native_vulkan_world_frame import NativeVulkanWorldFrame
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters.avatar_samples import IOSAvatarSamples,AvatarImagePending,AvatarImagePhaseChanged
from ios.adapters.avatar_marker_scope import IOSAvatarMarkerScope
from ios.adapters.avatar_marker_measurements import image_body_preserved
from ios.adapters.avatar_world import owned_marker
from ios.adapters.script_runtime import IOSScriptRuntime
from ios.self_tests.test_ios_avatar_images import bundle,NONCE,MARKER_URL
from ios.self_tests.test_ios_avatar_renderers import PEER
from ios.self_tests.test_ios_graphics_measurements import NATIVE,HOST,RUN,TICKET,URL,BINDING
from self_tests.test_native_feature_observation import Boundary
from self_tests.test_native_vulkan_world_frame import World


class AvatarSamplesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.root.chmod(0o700);self.addCleanup(self.temp.cleanup)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');held=self.lock.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        self.template,self.raw,self.policy=bundle();self.gpu=World();self.gpu.source_extent=[320,200];self.gpu.target_extent=[640,400]
        self.gpu.png=self.raw;self.gpu.raw_pixels=Image.open(BytesIO(self.raw)).convert('RGBA').tobytes()
        self.gpu.epoch=lambda:NATIVE+round(self.gpu.clock*1000)
        self.draw=0;self.reuse_draw=False;send_gpu=self.gpu.send
        def gpu_send(query):
            if query['operation']=='read':self.draw+=1;self.gpu.retired=False
            send_gpu(query)
            if query['operation']=='inspect' and (self.gpu.request is None or self.gpu.request['requestId']!=query['requestId']):
                self.gpu.value['source'].update(retired=False,present=False,callbacks=0,gpuPending=False,metadataBytes=0,pngBytes=0,gpuBufferBytes=0)
        self.gpu.send=gpu_send
        def fault(p):
            source=p.get('source',{});source.get('image',{}).update(width=640,height=400)
            if 'renderTrace' in source:source['renderTrace']['frameId']=format(1 if self.reuse_draw else self.draw,'032x')
        self.gpu.fault=fault
        self.native_boundary=Boundary();self.sequences=dict(world=0,renderers=0,phase=0);self.fail_world_after=False
        self.scope=object.__new__(IOSAvatarMarkerScope);self.scope.run,self.scope.role,self.scope.binding=RUN,'primary',deepcopy(BINDING)
        self.scope.fixture_url=URL;self.scope.guard=lambda:True;self.scope.bound=lambda:self.lock.assert_held()
        self.scope.state=dict(phase='ready',admission=dict(marker=dict(sourceUrl=MARKER_URL)),fileOwnership=dict(nonce=NONCE))
        self.scope.snapshot=lambda:dict(syntheticMarkerAdmission=True,runId=RUN,binding=deepcopy(BINDING))
        marker_baseline=deepcopy(self.template['worldBefore'])
        def bind_world(value):
            image_body_preserved(marker_baseline,value);marker=owned_marker(value,NONCE,MARKER_URL)
            return dict(nonce=NONCE,url=marker['sourceUrl'])
        self.scope.bind_image_world=bind_world
        seam=patch.object(IOSAvatarMarkerScope,'archive',return_value=self.scope);seam.start();self.addCleanup(seam.stop)
        self.phase=object.__new__(PhaseFixtureReader);self.phase.area,self.phase.run,self.phase.fixture_url='avatar-people',RUN,URL
        self.phase.status=self.phase_status;self.ticket=TICKET
        self.activations=[dict(sequence=1,ticket=TICKET,activatedEpochMs=HOST-100,stimulus=dict(verb='baseline',inputs={}))]
        self.phase.read=lambda:dict(ticket=self.ticket,afterEpochMs=self.activations[-1]['activatedEpochMs'],status=self.phase_status())
        self.runtime=object.__new__(IOSScriptRuntime);self.runtime.state_path=lambda _:self.root/'session.json';self.runtime._sources=self.sources
    def owner(self):
        return IOSAvatarSamples(self.runtime,'owned',self.scope,self.root,self.policy,self.phase,self.lock,
            monotonic=lambda:self.gpu.clock,epoch_ms=lambda:HOST+self.gpu.clock*1000,sleep=self.gpu.sleep)
    def phase_status(self,*_args):
        self.sequences['phase']+=1;s=self.sequences['phase']
        return dict(fixturePhaseVersion=1,instance='a'*32,sequence=s,requestId=format(s+10000,'032x'),runId=RUN,area='avatar-people',
            capturedEpochMs=HOST+self.gpu.clock*1000,active=True,createdEpochMs=HOST-1000,retiredEpochMs=None,
            activations=deepcopy(self.activations))
    def sources(self,_selector):
        return dict(binding=deepcopy(BINDING),check=lambda:True,clock_source=None,observer=SimpleNamespace(
            bound_native_observer=self.native,avatar_world=lambda _:SimpleNamespace(last=None,read=self.world),
            avatar_renderers=lambda _:SimpleNamespace(last=None,read=self.renderers),vulkan_world_frame=self.vulkan))
    def native(self,_clock):
        def retime(value,epoch):
            if type(value) is dict:return {key:epoch if key.endswith('EpochMs') else retime(v,epoch) for key,v in value.items()}
            if type(value) is list:return [retime(v,epoch) for v in value]
            return value
        def send(query):
            self.gpu.clock+=.01;self.native_boundary.send(query)
            self.native_boundary.sample=retime(self.native_boundary.sample,self.gpu.epoch());self.native_boundary.sample['processId']=42
        return NativeFeatureObservation(send,lambda:json.dumps(self.native_boundary.sample),self.gpu.epoch,lambda:True,42,
            ios=True,native_clock_bound=True,monotonic=lambda:self.gpu.clock,sleep=self.gpu.sleep)
    def world(self,run):
        self.assertEqual(RUN,run);self.sequences['world']+=1;s=self.sequences['world'];self.gpu.clock+=.01
        if self.fail_world_after and s%2==0:raise OSError('Synthetic lost actual post-image World')
        p=deepcopy(self.template['worldBefore']);p.update(requestId='ios-'+format(6000+s,'032x'),sequence=s)
        for key in ('clockBefore','clockAfter'):p[key]=dict(epochMs=self.gpu.epoch(),monotonicMs=round(self.gpu.clock*1000))
        p['source']['scriptOriginal'].update(requestedEpochMs=self.gpu.epoch(),capturedEpochMs=self.gpu.epoch())
        p['source']['bodies'].update(sequence=s,capturedEpochMs=self.gpu.epoch());return p
    def renderers(self,run):
        self.assertEqual(RUN,run);self.sequences['renderers']+=1;s=self.sequences['renderers'];self.gpu.clock+=.01
        p=deepcopy(self.template['renderersBefore']);p.update(requestId='ios-'+format(8000+s,'032x'),sequence=s)
        for key in ('clockBefore','clockAfter'):p[key]=dict(epochMs=self.gpu.epoch(),monotonicMs=round(self.gpu.clock*1000))
        for row in p['source']['avatars']:
            for key in ('rigPose','externalPose'):
                if row[key]:row[key].update(capturedEpochMs=self.gpu.epoch(),evaluationSequence=100+s)
        return p
    def vulkan(self,intent,receipt):
        return NativeVulkanWorldFrame(self.gpu.send,self.gpu.original,self.gpu.epoch,lambda:True,42,intent,receipt=receipt,
            monotonic=lambda:self.gpu.clock,sleep=self.gpu.sleep)
    def test_genuine_png_gpu_chunks_and_mesh_brackets_remain_immutable_after_reconstruction(self):
        owner=self.owner();row=owner.capture(TICKET);commands=len(self.gpu.commands)
        again=self.owner();frame,raw,measurement=again.archive(row)
        self.assertEqual(self.raw,raw);self.assertTrue(measurement['modelLoaded']);self.assertEqual('observed',row['status'])
        self.assertEqual(commands,len(self.gpu.commands));self.assertEqual(1,sum(q['operation']=='read' for q in self.gpu.commands))
        self.assertGreater(frame['retirement']['sequence'],frame['capture']['sequence'])
        actual=self.root/again.read_record(row)['owner']['name'];identity=actual.stat().st_ino
        self.scope.guard=lambda:(_ for _ in ()).throw(AssertionError('historical live guard'))
        self.assertEqual(raw,again.archive(row)[1]);self.assertEqual(identity,actual.stat().st_ino)
    def test_bad_challenge_keeps_original_png_and_true_gpu_retirement_as_pending(self):
        image=Image.open(BytesIO(self.raw)).convert('RGBA');image.paste((128,128,128,255),(187,70,443,134))
        stream=BytesIO();image.save(stream,format='PNG');self.gpu.png=stream.getvalue();self.gpu.raw_pixels=image.tobytes()
        with self.assertRaises(AvatarImagePending):self.owner().capture(TICKET)
        owner=self.owner();row=owner.state['rows'][-1];frame,raw,result=owner.archive(row)
        self.assertEqual('marker-pending',row['status']);self.assertIsNone(result);self.assertEqual(self.gpu.png,raw)
        self.assertFalse(frame['retirement']['source']['present']);self.assertEqual(1,sum(q['operation']=='release' for q in self.gpu.commands))
    def test_lost_capture_is_never_reissued_and_abandoned_originals_recover_actual_gpu_owner(self):
        send=self.gpu.send
        def lost(query):
            send(query)
            if query['operation']=='read':raise OSError('Synthetic lost native read return')
        self.gpu.send=lost
        with self.assertRaises(NativeUIError):self.owner().capture(TICKET)
        owner=self.owner();before=len(self.gpu.commands)
        with self.assertRaises(NativeUIError):owner.capture(TICKET)
        self.assertEqual(before,len(self.gpu.commands));self.gpu.send=send
        row=owner.recover();self.assertEqual('abandoned',row['status']);record=owner.read_record(row)
        self.assertIn('worldBefore',record['partial']);self.assertNotIn('capture',record['partial'])
        self.assertEqual('released',record['owner']['phase']);self.assertEqual(1,sum(q['operation']=='read' for q in self.gpu.commands))
        with self.assertRaises(NativeUIError):owner.archive(row)
        self.assertTrue(self.owner().drain());self.assertEqual(1,sum(q['operation']=='release' for q in self.gpu.commands))
    def test_partial_post_image_source_read_keeps_genuine_png_without_promoting_it_to_sample(self):
        self.fail_world_after=True
        with self.assertRaises(OSError):self.owner().capture(TICKET)
        owner=self.owner();row=owner.recover();record=owner.read_record(row)
        self.assertEqual('abandoned',row['status']);self.assertIn('capture',record['partial']);self.assertNotIn('worldAfter',record['partial'])
        self.assertEqual(self.raw,(self.root/record['owner']['name']).read_bytes());self.assertEqual(1,sum(q['operation']=='read' for q in self.gpu.commands))
    def test_lost_release_is_only_inspected_and_keeps_actual_empty_or_partial_artifact(self):
        send=self.gpu.send
        def lost(query):
            send(query)
            if query['operation']=='release':raise OSError('Synthetic lost actual retirement return')
        self.gpu.send=lost
        with self.assertRaises(NativeUIError):self.owner().capture(TICKET)
        self.gpu.send=send;owner=self.owner();row=owner.recover();self.assertEqual('abandoned',row['status'])
        self.assertEqual(1,sum(q['operation']=='release' for q in self.gpu.commands));self.assertTrue(owner.drain())
        self.assertEqual(1,sum(q['operation']=='release' for q in self.gpu.commands))
    def test_lost_original_writer_keeps_its_opened_inode_and_no_native_capture_is_repeated(self):
        owner=self.owner();intent=owner.originals.intent
        def lost(kind,value):
            intent(kind,value)
            if value['phase']=='opened':raise OSError('Synthetic lost original writer after actual inode admission')
        owner.originals.intent=lost
        with self.assertRaises(OSError):owner.capture(TICKET)
        failed=deepcopy(owner.state['pending']['original']);path=owner.originals.path(failed);inode=path.stat().st_ino
        self.assertEqual(0,path.stat().st_size);owner=self.owner();row=owner.recover();record=owner.read_record(row)
        self.assertEqual('abandoned',row['status']);self.assertEqual(inode,record['abandonment']['partialFile']['identity']['inode'])
        self.assertEqual(inode,path.stat().st_ino);self.assertEqual(1,sum(q['operation']=='read' for q in self.gpu.commands))
        (self.root/'foreign-source-link').hardlink_to(path)
        with self.assertRaises(NativeUIError):owner.read_record(row)
    def test_lost_saved_original_return_adopts_that_original_without_native_requests(self):
        owner=self.owner();write=owner.store.write
        def lost(value,previous):
            if owner.state['pending'] is None and owner.state['rows']:raise OSError('Synthetic missing final owner CAS')
            return write(value,previous)
        owner.store.write=lost
        with self.assertRaises(OSError):owner.capture(TICKET)
        before=len(self.gpu.commands);rebuilt=self.owner();self.assertEqual('saved',rebuilt.state['pending']['original']['phase'])
        row=rebuilt.recover();self.assertEqual('observed',row['status']);self.assertEqual(before,len(self.gpu.commands))
        self.assertEqual(self.raw,rebuilt.archive(row)[1])
    def test_partial_sources_are_extended_by_new_capture_and_reused_actual_draw_is_refused(self):
        self.fail_world_after=True
        with self.assertRaises(OSError):self.owner().capture(TICKET)
        owner=self.owner();abandoned=owner.recover();self.fail_world_after=False
        row=owner.capture(TICKET);frame,_raw,_result=owner.archive(row)
        old=owner.read_record(abandoned)['partial'];self.assertGreater(frame['worldBefore']['sequence'],old['worldBefore']['sequence'])
        self.assertGreater(frame['renderersBefore']['sequence'],old['renderersAfter']['sequence'])
        self.reuse_draw=True
        with self.assertRaises(NativeUIError):self.owner().capture(TICKET)
        self.assertIsNotNone(self.owner().state['pending'])
    def test_second_failure_during_abandoned_record_write_retains_both_original_inodes(self):
        self.fail_world_after=True
        with self.assertRaises(OSError):self.owner().capture(TICKET)
        owner=self.owner();intent=owner.originals.intent
        def lost(kind,value):
            intent(kind,value)
            if value['phase']=='opened':raise OSError('Synthetic interrupted abandonment archive')
        owner.originals.intent=lost
        with self.assertRaises(OSError):owner.recover()
        original=deepcopy(owner.state['pending']['original']);inode=owner.originals.path(original).stat().st_ino
        rebuilt=self.owner();row=rebuilt.recover();record=rebuilt.read_record(row)
        self.assertEqual(inode,record['abandonment']['partialFile']['identity']['inode'])
        self.assertEqual(inode,rebuilt.originals.path(original).stat().st_ino)
        self.assertEqual(1,sum(q['operation']=='read' for q in self.gpu.commands));self.assertEqual(1,sum(q['operation']=='release' for q in self.gpu.commands))
    def test_actual_phase_change_retains_original_pixels_and_is_not_a_current_observation(self):
        status=self.phase.status
        def crossed(previous):
            p=status(previous);p['activations'].append(dict(sequence=2,ticket='f'*32,activatedEpochMs=p['capturedEpochMs'],stimulus=dict(verb='baseline',inputs={})))
            return p
        self.phase.status=crossed
        with self.assertRaises(AvatarImagePhaseChanged):self.owner().capture(TICKET)
        owner=self.owner();row=owner.state['rows'][-1]
        self.assertEqual('phase-changed',row['status']);self.assertEqual(self.raw,owner.archive(row)[1])

    def test_unavailable_geometry_uses_only_previously_archived_real_volume_and_new_original_challenge(self):
        owner=self.owner();basis=owner.capture(TICKET)
        self.ticket='f'*32;self.activations.append(dict(sequence=2,ticket=self.ticket,activatedEpochMs=HOST+self.gpu.clock*1000,
            stimulus=dict(verb='baseline',inputs={})))
        self.template,self.raw,_policy=bundle(start=1000,ticket=self.ticket,unavailable=True,uniform=True)
        self.gpu.png=self.raw;self.gpu.raw_pixels=Image.open(BytesIO(self.raw)).convert('RGBA').tobytes()
        row=owner.capture(self.ticket,absence_basis=basis['index']);frame,raw,result=owner.archive(row)
        self.assertFalse(result['modelLoaded']);self.assertEqual('previously-rendered-avatar',result['subjectBoundsSource'])
        self.assertEqual(owner.archive(basis)[2]['frameId'],result['basisFrameId']);self.assertEqual(self.raw,raw)
    def test_historical_whole_ledger_uses_only_original_files_and_retains_all_source_and_png_inodes(self):
        owner=self.owner();row=owner.capture(TICKET);value=owner.store.read();calls=len(self.gpu.commands)
        self.scope.guard=lambda:(_ for _ in ()).throw(AssertionError('live guard'))
        historical=IOSAvatarSamples.history(value,store=owner.store,root=self.root,binding=BINDING,run=RUN,
            role='primary',policy=self.policy,lock=self.lock)
        self.assertEqual(self.raw,historical.archive(row)[1]);self.assertEqual(calls,len(self.gpu.commands))
        path=historical.originals.path(historical.originals.expand(row['original']))
        path.rename(self.root/'old-source.json');path.write_bytes((self.root/'old-source.json').read_bytes());path.chmod(0o600)
        with self.assertRaises(NativeUIError):historical.archive(row)

    def test_split_native_begin_or_late_phase_original_cannot_be_admitted_under_an_old_image_clock(self):
        owner=self.owner();row=owner.capture(TICKET);record=owner.read_record(row)
        for fault in ('native','phase','status'):
            wrong=deepcopy(record)
            if fault=='native':wrong['partial']['nativeStart']['hostBeforeEpochMs']+=1
            elif fault=='phase':wrong['partial']['phaseAfter']['capturedEpochMs']+=1000
            else:wrong['status']='phase-changed'
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):owner.validate_record(wrong)

    def test_independent_remote_subject_uses_its_actual_mesh_and_excludes_observer_self(self):
        self.template,self.raw,self.policy=bundle(remote=True);self.gpu.png=self.raw
        self.gpu.raw_pixels=Image.open(BytesIO(self.raw)).convert('RGBA').tobytes();baseline=deepcopy(self.template['worldBefore'])
        def bind(value):
            image_body_preserved(baseline,value);marker=owned_marker(value,NONCE,MARKER_URL);return dict(nonce=NONCE,url=marker['sourceUrl'])
        self.scope.bind_image_world=bind
        owner=self.owner();row=owner.capture(TICKET,avatar_id=PEER);frame,raw,result=owner.archive(row)
        self.assertEqual(PEER,result['sessionId']);self.assertTrue(result['remote']);self.assertTrue(result['modelLoaded'])
        self.assertEqual(self.raw,raw);self.assertEqual(PEER,row['avatarId'])

    def test_replaced_or_hardlinked_original_png_refuses_reconstruction_archive(self):
        owner=self.owner();row=owner.capture(TICKET);record=owner.read_record(row);path=self.root/record['owner']['name']
        (self.root/'foreign.png').hardlink_to(path)
        with self.assertRaises(NativeUIError):owner.archive(row)
        with self.assertRaises(NativeUIError):owner.drain()


if __name__=='__main__':unittest.main()
