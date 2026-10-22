"""Real durable scene owner/readers; explicit synthetic entity/HMD boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest
import uuid
from unittest.mock import patch
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parent)]

from adapters.native_avatar_render import NativeAvatarRender
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.emote_scene_source import NativePicoEmoteScene,command,validate,ready,retired,INPUT,OBSERVE,continuity
from adapters.pico4.emote_scene_owner import PicoEmoteScene
from adapters.script_journey.history import unpack,pack
from self_tests.test_native_avatar_render import Boundary as AvatarBoundary
from self_tests import test_pico_emote_sources as source_fixture
from feature_journeys.fixtures import pinned_resource
RUN,BINDING=source_fixture.RUN,source_fixture.BINDING


class SceneBoundary:
    def __init__(self,case):
        self.s=source_fixture.SourcesTests();self.s.setUp();case.addCleanup(self.s.doCleanups)
        self.store=PrivateFeatureState(self.s.root/'scene.json');self.avatar=AvatarBoundary();self.avatar.avatar['cameraMode']='look at'
        self.avatar.avatar.update(cameraStateVersion=1,cameraState=dict(hmd=True,boomLength=1.5,zoomMin=.5,zoomDefault=1.5))
        def resource(url,path,name):
            data=pinned_resource(name)
            return dict(present=True,urlSha256=hashlib.sha256(url.encode()).hexdigest(),bundledResource=dict(resourcePath=path,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
        configured=resource('qrc:/meshes/defaultAvatar_full.fst','meshes/defaultAvatar_full.fst','avatar-a.fst')
        loaded=resource('qrc:/meshes/mannequin/mannequin.fbx','meshes/mannequin/mannequin.fbx','mannequin/mannequin.fbx')
        self.avatar.avatar.update(avatarResourcesVersion=1,avatarResources=dict(configured=configured,loaded=loaded))
        self.avatar.avatar['geometry']['sourceSha256']=loaded['urlSha256']
        self.inputs=[];self.sequence=0;self.sample=None;self.scene=None;self.lost=None;self.ignore=False;self.retain=False;self.foreign=False
        self.freeze_native=False;self.clock_jump=False;self.phase_change=False;self.reader_send_count=0
    def sleep(self,seconds):
        self.s.clock+=seconds
        if not self.freeze_native:self.s.epoch+=round(seconds*1000)
    def native(self):
        return NativePicoEmoteScene(self.send,lambda:'' if self.sample is None else json.dumps(self.sample),lambda:self.s.epoch,self.s.guard,31,
            monotonic=lambda:self.s.clock,sleep=self.sleep)
    def avatar_reader(self):
        def send(request):self.avatar.epoch=self.s.epoch;self.avatar.send(request)
        return NativeAvatarRender(send,self.avatar.original,lambda:self.s.epoch,self.s.guard,31,monotonic=lambda:self.s.clock,sleep=self.sleep)
    def make(self):
        return PicoEmoteScene(self.store,BINDING,self.s.phase,self.s.lock,self.native,self.avatar_reader,self.s.guard,
            monotonic=lambda:self.s.clock,sleep=self.sleep)
    def cleanup_phase(self):self.s.journal.activate(RUN,uuid.uuid4().hex,'cleanup',{})
    def send(self,request):
        self.reader_send_count+=1
        if request['action']==INPUT:
            state=unpack(self.store.read()['payload'])[0];row=state[request['operation']]
            unittest.TestCase().assertEqual(request,row['request']);unittest.TestCase().assertTrue(row['attempted'])
            self.inputs.append(deepcopy(request))
            if request['operation']=='prepare':
                view=deepcopy(self.avatar.avatar['view']);view.update(feetPosition=[0,0,-2],modelScale=1,boomLength=1.5,mode='look at',hmd=True)
                objects=[dict(role='backdrop',id='11111111-1111-4111-8111-111111111111'),dict(role='marker',id='22222222-2222-4222-8222-222222222222')]
                entities=[]
                # Independently authored exact fixture coordinates. These are
                # explicit actor values, never actual rendered measurements.
                for obj,position,size in zip(objects,([0,1.6,-6],[-.15625,1.7875,-.25]),([13.2,13.2,.01],[.0625,.025,.01])):
                    marker=obj['role']=='marker'
                    entities.append(dict(**obj,originalObject=True,name='e2e-'+RUN+'-emote-'+obj['role'],type='Web' if marker else 'Box',
                        parentId='00000000-0000-0000-0000-000000000000',hostType='local',position=position,rotation=[0,0,0,1],dimensions=size,
                        color=[255,255,255] if marker else [128,128,128],visible=True,sourceUrl=request['fixtureUrl']+'tickets/'+request['ticket']+'/graphics-marker.v1.html' if marker else '',
                        locked=False,collisionless=True,canCastShadow=False,dpi=100 if marker else 0,lastEditedEpochUs=self.s.epoch*1000))
                self.scene=dict(picoEmoteSceneVersion=1,fixtureInstance='a'*32,runId=RUN,phase='active',createdEpochMs=self.s.epoch,
                    originalInput=deepcopy(request),originalView=view,objects=objects,entities=[] if self.ignore else entities,
                    absentIds=[r['id'] for r in objects] if self.ignore else [],retainedObjects=2)
            else:self.scene.update(phase='releasing',entities=[],absentIds=[r['id'] for r in self.scene['objects']])
            source=dict(picoEmoteSceneInputVersion=1,commandId=request['commandId'],runId=RUN,fixtureInstance='a'*32,operation=request['operation'],recorded=True)
            if self.lost==request['operation']:raise OSError('Explicit lost input reply after native actor effect')
        else:
            if self.scene is None:raise OSError('No original scene')
            if self.scene['phase']=='releasing' and not self.retain:self.scene.update(phase='drained',retainedObjects=0)
            source=deepcopy(self.scene)
            if self.foreign and source['entities']:source['entities'][0]['originalObject']=False
        self.sequence+=1
        self.sample=dict(schemaVersion=1,requestId=request['commandId'],instance='f'*32,sequence=self.sequence,processId=31,
            requestedEpochMs=self.s.epoch,capturedEpochMs=self.s.epoch,source=source)


class PicoEmoteSceneTests(unittest.TestCase):
    def setUp(self):
        self.b=SceneBoundary(self);held=self.b.s.lock.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None);self.owner=self.b.make()
    def prepare(self):return self.owner.prepare([1600,1000],[200,100,400,150])
    def test_original_effect_and_three_second_actual_retirement_keep_journal(self):
        value=self.prepare();self.assertEqual(2,len(value['scene']['source']['entities']));self.assertEqual(1,len(self.b.inputs))
        self.b.cleanup_phase();proof=self.owner.cleanup();self.assertEqual(2,len(self.b.inputs));self.assertGreaterEqual(self.b.s.clock,3)
        self.assertEqual(proof,self.b.store.read());self.assertEqual('retired',self.b.make().state['phase']);self.assertNotIn('passed',proof)
    def test_lost_prepare_ack_reconciles_readonly_after_cold_restore(self):
        self.b.lost='prepare'
        with self.assertRaises(NativeUIError):self.prepare()
        self.assertTrue(self.owner.state['prepare']['attempted']);self.b.lost=None;self.owner=self.b.make();self.owner.reconcile()
        self.assertEqual(1,len(self.b.inputs));self.assertEqual('ready',self.owner.state['phase'])
    def test_receipt_without_original_entities_cannot_become_ready(self):
        self.b.ignore=True
        with self.assertRaises(NativeUIError):self.prepare()
        self.assertEqual('preparing',self.b.make().state['phase']);self.assertEqual(1,len(self.b.inputs))
    def test_lost_release_ack_cold_cleanup_never_resends(self):
        self.prepare();self.b.cleanup_phase();self.b.lost='release'
        with self.assertRaises(NativeUIError):self.owner.cleanup()
        self.b.lost=None;self.owner=self.b.make();proof=self.owner.cleanup()
        self.assertEqual(2,len(self.b.inputs));self.assertIsNotNone(proof)
    def test_absent_entities_with_live_original_objects_do_not_retire(self):
        self.prepare();self.b.cleanup_phase();self.b.retain=True
        with self.assertRaises(NativeUIError):self.owner.cleanup()
        self.assertEqual('releasing',self.b.make().state['phase']);self.assertEqual(2,len(self.b.inputs))
    def test_foreign_replacement_blocks_release_before_input(self):
        self.prepare();self.b.cleanup_phase();self.b.foreign=True
        with self.assertRaises(NativeUIError):self.owner.cleanup()
        self.assertEqual(1,len(self.b.inputs));self.assertIsNone(self.owner.state['release'])
    def test_phase_change_during_original_scene_read_blocks_ready(self):
        send=self.b.send
        def changed(request):
            send(request)
            if request['action']==OBSERVE:self.b.s.journal.activate(RUN,uuid.uuid4().hex,'play',{'name':'Waving'})
        self.b.send=changed
        with self.assertRaises((NativeUIError,ValueError)):self.prepare()
        self.assertEqual('preparing',self.b.make().state['phase']);self.assertEqual(1,len(self.b.inputs))
    def test_missing_resources_refuse_before_first_input(self):
        self.b.avatar.avatar.pop('avatarResourcesVersion');self.b.avatar.avatar.pop('avatarResources')
        with self.assertRaises(NativeUIError):self.prepare()
        self.assertFalse(self.b.inputs);self.assertIsNone(self.b.store.read())
    def test_slow_intent_cas_with_frozen_native_clock_blocks_transport(self):
        write=self.b.store.write;self.b.freeze_native=True
        def slow(value,previous):
            write(value,previous)
            if unpack(value['payload'])[0]['prepare']['attempted']:self.b.sleep(2)
        with patch.object(self.b.store,'write',side_effect=slow),self.assertRaises(NativeUIError):self.prepare()
        self.assertFalse(self.b.inputs);self.assertTrue(self.b.make().state['prepare']['attempted'])
    def test_lost_intent_write_ack_preserves_unresolved_no_replay(self):
        write=self.b.store.write
        def lost(value,previous):
            write(value,previous)
            if unpack(value['payload'])[0]['prepare']['attempted']:raise OSError('Explicit committed CAS with lost ACK')
        with patch.object(self.b.store,'write',side_effect=lost),self.assertRaises(OSError):self.prepare()
        self.assertFalse(self.b.inputs);owner=self.b.make()
        with self.assertRaises(NativeUIError):owner.prepare([1600,1000],[200,100,400,150])
        self.assertFalse(self.b.inputs)
    def test_phase_advance_during_durable_intent_blocks_transport(self):
        write=self.b.store.write
        def advanced(value,previous):
            write(value,previous)
            if unpack(value['payload'])[0]['prepare']['attempted']:
                self.b.s.journal.activate(RUN,uuid.uuid4().hex,'play',{'name':'Waving'})
        with patch.object(self.b.store,'write',side_effect=advanced),self.assertRaises(NativeUIError):self.prepare()
        self.assertFalse(self.b.inputs);self.assertTrue(self.b.make().state['prepare']['attempted'])
    def test_frozen_native_clock_cannot_qualify_retirement_with_host_time_alone(self):
        self.prepare();self.b.cleanup_phase();self.b.freeze_native=True
        with self.assertRaises(NativeUIError):self.owner.cleanup()
        self.assertGreaterEqual(self.b.s.clock,3);self.assertEqual('releasing',self.b.make().state['phase'])
    def test_native_clock_jump_cannot_replace_actual_host_quiet_window(self):
        self.prepare();self.b.cleanup_phase();sleep=self.b.sleep
        def accelerated(seconds):sleep(seconds);self.b.s.epoch+=3000
        self.owner.sleep=accelerated
        with self.assertRaises(NativeUIError):self.owner.cleanup()
        self.assertGreaterEqual(self.b.s.clock,3);self.assertNotEqual('retired',self.b.make().state['phase'])
    def test_corrupt_retained_input_and_reused_original_queries_are_refused(self):
        self.prepare();good=deepcopy(self.b.store.read());state=unpack(good['payload'])[0]
        for edit in (lambda s:s['prepare']['request'].update(commandId='9'*32),lambda s:s['originals'].append(deepcopy(s['originals'][-1])),
                     lambda s:s['frames'].append(deepcopy(s['frames'][-1]))):
            bad=deepcopy(state);edit(bad);header=deepcopy(good);header['payload']=pack([bad]);self.b.store.write(header,self.b.store.read())
            with self.subTest(edit=edit),self.assertRaises((NativeUIError,ValueError)):self.b.make()
        self.b.store.write(good,self.b.store.read())
    def test_closed_scene_input_rejects_per_eye_claims_foreign_fixture_and_coerced_version(self):
        self.prepare();request=deepcopy(self.b.inputs[0])
        for change in (dict(schemaVersion=True),dict(eyes=['left','right']),dict(fixtureUrl='http://user@controlled.test/feature-fixture/v1/runs/'+RUN+'/'),dict(imageExtent=[True,1000])):
            with self.subTest(change=change),self.assertRaises((NativeUIError,ValueError)):command(request|change)
    def test_original_scene_identity_and_liveness_cannot_revive(self):
        self.prepare();previous=deepcopy(self.owner.state['frames'][-1]['scene'])
        value=deepcopy(previous);value.update(requestId='9'*32,sequence=previous['sequence']+1);value['source']['fixtureInstance']='9'*32
        with self.assertRaises(NativeUIError):continuity(previous,value)
        value=deepcopy(previous);value.update(requestId='9'*32,sequence=previous['sequence']+1);previous['source']['retainedObjects']=0
        with self.assertRaises(NativeUIError):continuity(previous,value)


if __name__=='__main__':unittest.main()
