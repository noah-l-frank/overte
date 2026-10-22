"""Real private scene ownership over independent synthetic native boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.native_graphics_subject import NativeGraphicsSubject
from adapters.native_phone_emote_fixture import NativePhoneEmoteFixture
from adapters.native_phone_web_runtime import NativePhoneWebRuntime
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from overte_phone_emote_scene import PhoneEmoteScene,SceneOriginals
from overte_phone_emote_originals import PhoneEmoteOriginals
from overte_phone_script_history import unpack
from self_tests.test_native_phone_emote_fixture import Boundary as FixtureBoundary,NULL_ID
from self_tests.test_native_phone_web_runtime import Boundary as WebBoundary
from test_emote_view import Model as ViewModel,RUN


class Model(ViewModel):
    def __init__(self):
        super().__init__();self.fixture_source=FixtureBoundary();self.web=WebBoundary();self.created=False
        self.fixture_calls=[];self.scene_receipts=[];self.scene_fault=None;self.world=self.fixture.boundary
        self.fixture.source.clock_ms=lambda:self.native.epoch
        self.world.source['sceneUrl']='hifi://controlled.invalid/0,0,0'
        self.world.source['scan'].update(scannedEntities=1,unowned=[dict(id='99999999-9999-4999-8999-999999999999',sha256='9'*64)])
        self.foreign=deepcopy(self.world.source['scan']['unowned']);self.nodes=[];self.marker_seen=False
        self.web.now=lambda:self.native.epoch
        original=self.web.packet
        def browser():
            value=original()
            if not self.marker_seen:
                for key in ('nativeBefore','nativeAfter'):value['source'][key].update(knownHandles=[],views=[])
                value['source']['java'].update(views=[],creations=[])
            elif self.scene_fault=='retain-browser' and not self.nodes:
                value['source']['nativeAfter']['views'][0]['callbacks']=1
            return value
        self.web.packet=browser
        self.fixture_source.fixture['runId']=RUN
        original_send=self.fixture_source.send
        def fixture_send(request):
            self.fixture_source.epoch=self.native.epoch
            if not self.created:
                self.fixture_source.sample=dict(schemaVersion=1,requestId=request['commandId'],available=False)
            else:original_send(request)
        self.fixture_source.send=fixture_send
        world_send=self.world.send
        def observe_world(request):
            self.sync();self.world.epoch=self.native.epoch
            source=self.world.source;avatar=self.native.avatar
            source.update(subjectVersion=2,avatarPose=deepcopy(avatar['pose']))
            source['view']={key:deepcopy(avatar['view'][key]) for key in ('position','rotation','fieldOfViewDegrees','aspectRatio','perspective')}
            source['view']['mode']=avatar['cameraMode']
            rows=deepcopy(self.foreign)
            if self.scene_fault=='foreign-world' and self.created:rows[0]['sha256']='8'*64
            rows.extend(dict(id=row['id'],sha256=hashlib.sha256(json.dumps(row,sort_keys=True).encode()).hexdigest()) for row in self.nodes)
            source['scan'].update(scannedEntities=len(rows),unowned=rows);world_send(request)
        self.world.send=observe_world;self.fixture.source.send=observe_world

    def _graphics_subject_observer(self,_selector,*,read_only):
        assert read_only
        return NativeGraphicsSubject(self.world.send,self.world.original,lambda:self.native.epoch,lambda:self.candidate_okay,31,
            monotonic=lambda:self.sdk.clock,sleep=self.fixture.sleep)

    def _web_runtime_observer(self,_selector,*,read_only):
        assert read_only
        return NativePhoneWebRuntime(self.web.send,self.web.original,self.web.now,lambda:self.candidate_okay,31,
            monotonic=lambda:self.sdk.clock,sleep=self.fixture.sleep)

    def _emote_fixture_observer(self,_selector,*,read_only):
        assert read_only
        return NativePhoneEmoteFixture(self.fixture_source.send,self.fixture_source.original,lambda:self.native.epoch,
            lambda:self.candidate_okay,31,monotonic=lambda:self.sdk.clock,sleep=self.fixture.sleep)

    def _emote_fixture_input(self,_selector,command,*,lock,intent):
        lock.assert_held();intent(deepcopy(command),deepcopy(self.normal_feature_runtime(_selector,read_only=True)[2]))
        self.fixture_calls.append(deepcopy(command))
        if command['operation']=='prepare':
            if self.scene_fault=='ignore-create':return {'performed':True}
            self.create(command)
        else:
            if self.scene_fault!='ignore-remove':
                self.nodes=[];self.fixture_source.drain()
                if self.scene_fault=='retain-node':self.fixture_source.fixture.update(phase='releasing',retainedObjects=1)
                self.web.revoked=self.scene_fault!='retain-browser'
        if self.scene_fault=='lose-'+command['operation']:raise NativeUIError('Synthetic lost fixture input return')
        return {'performed':True}

    def create(self,command):
        self.created=True;self.sync();avatar=self.native.avatar;view=deepcopy(avatar['view'])
        view.update(feetPosition=deepcopy(avatar['pose']['feetPosition']),modelScale=avatar['pose']['modelScale'],boomLength=self.boom,mode='selfie')
        original=self.fixture_source.fixture
        original.update(runId=RUN,phase='active',originalInput=deepcopy(command),originalView=view,createdEpochMs=self.native.epoch)
        f=1/math.tan(math.radians(view['fieldOfViewDegrees']/2));aspect=view['aspectRatio'];camera=view['position']
        depth=camera[2]-view['feetPosition'][2]+4*view['modelScale'];self.nodes=[]
        x0,y0,x1,y1=command['markerRoi'];w,h=command['imageExtent'];distance=max(.25,view['nearClip']*2)
        # Independent direct FOV reference. Production uses inverse projection.
        for item in original['objects']:
            marker=item['role']=='marker';d=distance if marker else depth
            cx=(x0+x1)/2 if marker else w/2;cy=(y0+y1)/2 if marker else h/2
            width=(x1-x0)/w if marker else 1.1;height=(y1-y0)/h if marker else 1.1
            position=[camera[0]+(2*cx/w-1)*d*aspect/f,camera[1]+(1-2*cy/h)*d/f,camera[2]-d]
            row=dict(id=item['id'],role=item['role'],originalObject=True,name='e2e-'+RUN+'-emote-'+item['role'],
                type='Web' if marker else 'Box',parentId=NULL_ID,hostType='local',position=position,rotation=deepcopy(view['rotation']),
                dimensions=[2*d*aspect/f*width,2*d/f*height,.01],color=[255,255,255] if marker else [128,128,128],visible=True,
                sourceUrl=command['fixtureUrl']+'tickets/'+command['ticket']+'/graphics-marker.v1.html' if marker else '',locked=False,
                collisionless=True,canCastShadow=False,dpi=100 if marker else 0,lastEditedEpochUs=self.native.epoch*1000)
            self.nodes.append(row)
        original.update(entities=deepcopy(self.nodes),absentIds=[],retainedObjects=2)
        if self.scene_fault=='foreign-lease':original['originalInput']['commandId']='0'*32
        self.marker_seen=True;self.web.epoch=self.native.epoch

    def scene_sleep(self,seconds):self.fixture.sleep(seconds);self.native.epoch+=round(seconds*1000)
    def scene(self,view):return PhoneEmoteScene(view,self.root,[1000,750],[20,20,180,60],monotonic=lambda:self.sdk.clock,sleep=self.scene_sleep)
    def retired_scene(self,proof):self.scene_receipts.append(deepcopy(proof))


class EmoteSceneTests(unittest.TestCase):
    def setUp(self):self.model=Model();self.addCleanup(self.model.close)
    def test_original_fixture_world_browser_and_private_records_compose_without_feature_verdicts(self):
        m=self.model
        with m.lock.held():
            view=m.factory();view.prepare();scene=m.scene(view);self.assertEqual({'performed':True},scene.prepare())
            self.assertEqual('active',scene.state['phase']);self.assertEqual(1,len(m.fixture_calls));self.assertGreaterEqual(len(scene.frames),2)
            self.assertTrue(list(m.root.glob('emote-frame-scene-*.json')))
            scene=m.scene(m.factory());m.cleaning();scene.cleanup();self.assertEqual('released',scene.state['phase'])
            scene=m.scene(m.factory());scene.retire(m.retired_scene);self.assertIsNone(scene.store.read());self.assertEqual(1,len(m.scene_receipts))
            self.assertEqual(['prepare','release'],[call['operation'] for call in m.fixture_calls])
            view=m.factory();m.cleanup(view);m.retire(view)

    def test_existing_original_store_does_not_admit_scene_kind_as_source_or_input(self):
        m=self.model
        with self.assertRaises(NativeUIError):PhoneEmoteOriginals(m.root,m.normal_feature_runtime('',read_only=True)[2],RUN,'primary',lambda:True,lambda *_:None,kind='scene')

    def test_ignored_creation_is_not_inferred_from_successful_private_dispatch(self):
        m=self.model;m.scene_fault='ignore-create'
        with m.lock.held():
            view=m.factory();view.prepare();scene=m.scene(view)
            with self.assertRaises(NativeUIError):scene.prepare()
            self.assertEqual(1,len(m.fixture_calls));self.assertIsNotNone(scene.store.read());self.assertIsNotNone(scene.state['pending'])
            with self.assertRaises(NativeUIError):m.scene(m.factory()).prepare()

    def test_lost_create_return_reopens_originals_and_observes_without_replaying_add(self):
        m=self.model;m.scene_fault='lose-prepare'
        with m.lock.held():
            view=m.factory();view.prepare();scene=m.scene(view)
            with self.assertRaises(NativeUIError):scene.prepare()
            self.assertTrue(m.created);m.scene_fault=None;scene=m.scene(m.factory());scene.prepare()
            self.assertEqual(1,len(m.fixture_calls));m.cleaning();scene.cleanup();scene.retire(m.retired_scene)

    def test_ignored_or_incomplete_node_and_browser_retirement_remains_owned(self):
        for fault in ('ignore-remove','retain-node','retain-browser'):
            m=Model()
            try:
                with m.lock.held():
                    view=m.factory();view.prepare();scene=m.scene(view);scene.prepare();m.scene_fault=fault;m.cleaning()
                    with self.subTest(fault=fault),self.assertRaises(NativeUIError):scene.cleanup()
                    self.assertIsNotNone(scene.store.read());self.assertEqual([],m.scene_receipts)
            finally:m.close()

    def test_lost_removal_response_reobserves_original_retirement_without_repeating_delete(self):
        m=self.model
        with m.lock.held():
            view=m.factory();view.prepare();scene=m.scene(view);scene.prepare();m.scene_fault='lose-release';m.cleaning()
            with self.assertRaises(NativeUIError):scene.cleanup()
            m.scene_fault=None;scene=m.scene(m.factory());scene.cleanup();scene.retire(m.retired_scene)
            self.assertEqual(['prepare','release'],[call['operation'] for call in m.fixture_calls])

    def test_foreign_world_mutation_or_native_lease_cannot_become_controlled_scene(self):
        for fault in ('foreign-world','foreign-lease'):
            m=Model()
            try:
                with m.lock.held():
                    view=m.factory();view.prepare();scene=m.scene(view);m.scene_fault=fault
                    with self.subTest(fault=fault),self.assertRaises(NativeUIError):scene.prepare()
                    self.assertIsNotNone(scene.store.read())
            finally:m.close()

    def test_replaced_original_frame_cannot_be_replayed_as_an_owned_scene(self):
        m=self.model
        with m.lock.held():
            view=m.factory();view.prepare();scene=m.scene(view);scene.prepare()
            path=next(m.root.glob('emote-frame-scene-*.json'));path.write_text('{}')
            with self.assertRaises(NativeUIError):m.scene(m.factory())
            self.assertIsNotNone(scene.store.read())

    def test_parent_retention_and_fresh_browser_read_precede_scope_removal(self):
        m=self.model
        with m.lock.held():
            view=m.factory();view.prepare();scene=m.scene(view);scene.prepare();m.cleaning();scene.cleanup();before=len(m.web.commands)
            with self.assertRaises(NativeUIError):scene.retire(lambda _proof:False)
            self.assertGreater(len(m.web.commands),before);self.assertIsNotNone(scene.store.read())
            scene=m.scene(m.factory());scene.retire(m.retired_scene)

    def test_late_browser_reappearance_after_cleanup_is_rejected_before_retirement(self):
        m=self.model
        with m.lock.held():
            view=m.factory();view.prepare();scene=m.scene(view);scene.prepare();m.cleaning();scene.cleanup();m.web.revoked=False
            with self.assertRaises(NativeUIError):scene.retire(m.retired_scene)
            self.assertEqual([],m.scene_receipts);self.assertIsNotNone(scene.store.read())
            self.assertEqual('releasing',scene.state['phase']);m.web.revoked=True
            scene=m.scene(m.factory());scene.cleanup();scene.retire(m.retired_scene)


    def test_cleanup_quiet_window_requires_both_native_and_host_elapsed_time(self):
        for frozen in ('native','host'):
            m=Model()
            try:
                if frozen=='native':m.scene_sleep=lambda seconds:m.fixture.sleep(seconds)
                else:m.scene_sleep=lambda seconds:setattr(m.native,'epoch',m.native.epoch+round(seconds*1000))
                with m.lock.held():
                    view=m.factory();view.prepare();scene=m.scene(view);scene.prepare();m.cleaning()
                    with self.subTest(frozen=frozen),self.assertRaises(NativeUIError):scene.cleanup()
                    self.assertNotEqual('released',scene.state['phase']);self.assertIsNotNone(scene.store.read())
            finally:m.close()

    def test_late_busy_browser_resets_the_contiguous_quiet_suffix(self):
        m=self.model
        with m.lock.held():
            view=m.factory();view.prepare();scene=m.scene(view);scene.prepare();m.cleaning();base=m.web.packet;release_epoch=m.native.epoch
            def late():
                packet=base();elapsed=m.native.epoch-release_epoch
                if not m.nodes and 1000<=elapsed<=1600:packet['source']['nativeAfter']['views'][0]['callbacks']=1
                return packet
            m.web.packet=late;scene.cleanup();start=scene.state['window']['start'];first=scene.frames[start]['frame']
            self.assertGreater(first['epochMs']-release_epoch,1600)
            self.assertGreaterEqual(scene.frames[-1]['frame']['configuration']['requestedEpochMs']-first['epochMs'],3000)
            scene.retire(m.retired_scene)

    def test_current_node_and_browser_retirement_can_be_reobserved_after_view_restoration(self):
        m=self.model
        with m.lock.held():
            view=m.factory();view.prepare();scene=m.scene(view);scene.prepare();m.cleaning();scene.cleanup()
            view=m.factory();m.cleanup(view);scene=m.scene(view);scene.retire(m.retired_scene);m.retire(view)
            self.assertEqual(1.5,m.boom);self.assertFalse(m.preference);self.assertEqual(1,len(m.scene_receipts))

    def test_slow_final_scene_write_is_historical_and_cannot_return_fresh_setup(self):
        m=self.model
        with m.lock.held():
            view=m.factory();view.prepare();scene=m.scene(view);write=scene.store.write;delayed=[False]
            def slow(value,previous):
                write(value,previous)
                if unpack(value['payload'])[0]['phase']=='active':m.sdk.clock+=1.6;delayed[0]=True
            with patch.object(scene.store,'write',side_effect=slow),self.assertRaises(NativeUIError):scene.prepare()
            self.assertTrue(delayed[0]);scene=m.scene(m.factory());scene.prepare();self.assertEqual(1,len(m.fixture_calls))
            m.cleaning();scene.cleanup();scene.retire(m.retired_scene)

    def test_partial_original_file_write_is_not_replayed_or_forgotten(self):
        m=self.model
        with m.lock.held():
            view=m.factory();view.prepare();scene=m.scene(view);intent=scene.originals.intent
            def failed(kind,value):
                intent(kind,value)
                if kind=='original' and value['phase']=='opened':raise OSError('Synthetic lost original file write')
            with patch.object(scene.originals,'intent',side_effect=failed),self.assertRaises(OSError):scene.prepare()
            self.assertEqual([],m.fixture_calls);scene=m.scene(m.factory());self.assertIsNotNone(scene.state['pending'])
            with self.assertRaises(NativeUIError):scene.prepare()
            self.assertIsNotNone(scene.store.read())

    def test_changed_fixture_phase_during_parent_retention_keeps_child_scope(self):
        m=self.model
        with m.lock.held():
            view=m.factory();view.prepare();scene=m.scene(view);scene.prepare();m.cleaning();scene.cleanup()
            def changed(frame):m.scene_receipts.append(deepcopy(frame));m.journal.activate(RUN,'a'*32,verb='cleanup')
            with self.assertRaises(NativeUIError):scene.retire(changed)
            self.assertIsNotNone(scene.store.read());self.assertEqual(1,len(m.scene_receipts))

    def test_changed_candidate_during_retention_keeps_original_scene_journal(self):
        m=self.model
        with m.lock.held():
            view=m.factory();view.prepare();scene=m.scene(view);scene.prepare();m.cleaning();scene.cleanup()
            def changed(frame):m.scene_receipts.append(deepcopy(frame));m.candidate_okay=False
            with self.assertRaises(NativeUIError):scene.retire(changed)
            self.assertIsNotNone(scene.store.read())


    def test_wrong_cleanup_phase_does_not_dispatch_or_break_later_authorized_cleanup(self):
        m=self.model
        with m.lock.held():
            view=m.factory();view.prepare();scene=m.scene(view);scene.prepare();previous=scene.store.read()
            with self.assertRaises(NativeUIError):scene.cleanup()
            self.assertEqual(previous,scene.store.read());self.assertEqual(1,len(m.fixture_calls))
            m.cleaning();scene=m.scene(m.factory());scene.cleanup();scene.retire(m.retired_scene)


    def test_untyped_expected_state_provider_cannot_replace_original_reader_factories(self):
        m=self.model
        with m.lock.held():
            view=m.factory();view.prepare();scene=m.scene(view)
            with patch.object(m,'_web_runtime_observer',return_value=object()),self.assertRaises(NativeUIError):scene.prepare()
            self.assertEqual([],m.fixture_calls);self.assertIsNone(scene.state['pending'])


    def closed_ready(self):
        m=self.model;view=m.factory();view.prepare();scene=m.scene(view);scene.prepare()
        m.cleaning();scene.cleanup();view.cleanup();return scene

    def test_closed_retirement_preserves_active_originals_and_acquires_actual_closed_group(self):
        m=self.model
        with m.lock.held():
            scene=self.closed_ready();header=deepcopy(scene.previous);frames=deepcopy(scene.frames)
            files=set(m.root.glob('emote-frame-scene-*.json'));calls=deepcopy(m.fixture_calls)
            m.journal.close(RUN);proof=scene.retire_closed(m.retired_scene)
            self.assertEqual(header,proof['header']);self.assertEqual(frames,scene.frames)
            self.assertEqual(files,set(m.root.glob('emote-frame-scene-*.json')))
            self.assertFalse(proof['frame']['phaseAfter']['active']);self.assertIsNone(scene.store.read())
            self.assertEqual(calls,m.fixture_calls);self.assertEqual([proof],m.scene_receipts)
            fresh=m.scene(m.factory());self.assertEqual(proof,fresh.retire_closed(lambda _:None,retained=proof))
            view=m.factory();view.retire_closed(lambda _:None)

    def test_closed_retirement_requires_closed_provider_and_rejects_new_browser_work(self):
        m=self.model
        with m.lock.held():
            scene=self.closed_ready()
            with self.assertRaises(NativeUIError):scene.retire_closed(m.retired_scene)
            m.journal.close(RUN);m.scene_fault='retain-browser'
            with self.assertRaises(NativeUIError):scene.retire_closed(m.retired_scene)
            self.assertIsNotNone(scene.store.read());self.assertEqual([],m.scene_receipts)
            self.assertIsNone(scene.state['pending'])

    def test_closed_retirement_rejects_forged_header_provider_lease_or_native_cursor(self):
        m=self.model
        with m.lock.held():
            scene=self.closed_ready();m.journal.close(RUN);proof=scene.retire_closed(m.retired_scene)
            fresh=m.scene(m.factory())
            for fault in ('version','root','provider','lease','cursor','header'):
                bad=deepcopy(proof)
                if fault=='version':bad['emoteSceneRetirementVersion']=True
                elif fault=='root':bad['header']['artifactRoot']=str(m.root/'foreign')
                elif fault=='provider':bad['frame']['phaseAfter']['instance']='9'*32
                elif fault=='lease':bad['frame']['fixture']['source']['originalInput']['commandId']='0'*32
                elif fault=='cursor':bad['frame']['world']=deepcopy(scene.frames[-1]['frame']['world'])
                else:
                    state=unpack(bad['header']['payload'])[0];state['window']['complete']=False
                    from overte_phone_script_history import pack
                    bad['header']['payload']=pack([state])
                with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):
                    fresh.retire_closed(lambda _:None,retained=bad)

    def test_closed_retirement_requires_retention_before_deletion_and_rejects_late_delivery(self):
        m=self.model
        with m.lock.held():
            scene=self.closed_ready();m.journal.close(RUN)
            with self.assertRaises(NativeUIError):scene.retire_closed(lambda _:False)
            self.assertIsNotNone(scene.store.read())
            def late(_):m.sdk.clock+=2
            with self.assertRaises(NativeUIError):scene.retire_closed(late)
            self.assertIsNotNone(scene.store.read());self.assertIsNone(scene.state['pending'])

    def test_closed_retirement_lost_return_requires_original_proof_and_actual_files(self):
        m=self.model
        with m.lock.held():
            scene=self.closed_ready();m.journal.close(RUN);discard=scene.store.discard
            def lost(header):discard(header);raise OSError('Synthetic lost scene removal')
            with patch.object(scene.store,'discard',side_effect=lost),self.assertRaises(OSError):scene.retire_closed(m.retired_scene)
            fresh=m.scene(m.factory())
            with self.assertRaises(NativeUIError):fresh.retire_closed(lambda _:None)
            proof=m.scene_receipts[0];self.assertEqual(proof,fresh.retire_closed(lambda _:None,retained=proof))
            original=next(m.root.glob('emote-frame-scene-*.json'));original.write_bytes(b'{}')
            with self.assertRaises(NativeUIError):fresh.retire_closed(lambda _:None,retained=proof)

    def test_closed_retirement_ignored_removal_and_unreleased_nodes_stay_owned(self):
        m=self.model
        with m.lock.held():
            scene=self.closed_ready();m.journal.close(RUN)
            with patch.object(scene.store,'discard',return_value=None),self.assertRaises(NativeUIError):scene.retire_closed(m.retired_scene)
            self.assertIsNotNone(scene.store.read());proof=m.scene_receipts[0]
            fresh=m.scene(m.factory());self.assertEqual(proof,fresh.retire_closed(lambda _:None,retained=proof))


    def parent_resource_context(self,*,scene_issued=True):
        # Exercise the coordinator's production View/Scene call path. Namespace
        # retirement has its independent original-source tests and is doubled
        # only here; the real View/Scene readers and private files remain intact.
        from types import SimpleNamespace
        from overte_phone_emote_retirement import PhoneEmoteRetirement
        from overte_phone_script_history import pack
        m=self.model
        if scene_issued:
            scene=self.closed_ready();scene_header=deepcopy(scene.previous)
        else:
            view=m.factory();view.prepare();m.cleaning();view.cleanup();scene_header=None
        originals={'phone-emote-scene.json':scene_header,m.factory().store.path.name:m.factory().store.read()}
        store=PrivateFeatureState(m.root/'unit-resource-handoff.json')
        def get(key):
            header=store.read();return None if header is None else unpack(header['payload'])[0].get(key)
        def retain(key,value):
            previous=store.read();records={} if previous is None else unpack(previous['payload'])[0]
            if key in records:self.assertEqual(records[key],value)
            else:records[key]=deepcopy(value);store.write(dict(payload=pack([records])),previous)
        def namespace_retire(callback,*,retained=None):
            callback(retained if retained is not None else dict(unitNamespaceBoundaryVersion=1,header=None))
        owner=object.__new__(PhoneEmoteRetirement)
        owner.run=SimpleNamespace(adapter=m,selector='controlled',phase=m.phase,lock=m.lock,root=m.root,
            extent=[1000,750],marker=[20,20,180,60],monotonic=lambda:m.sdk.clock,sleep=m.scene_sleep)
        owner.owner_state=dict(cleanupTicket='e'*32,setup=dict(view='issued',scene='issued' if scene_issued else 'unissued'))
        owner.state=dict(attempts=1,mode='observed' if scene_issued else 'setup')
        owner.get,owner.retain,owner.original=get,retain,lambda name:deepcopy(originals[name])
        owner.file=lambda name:PrivateFeatureState(m.root/name)
        owner.namespace=lambda:SimpleNamespace(retire_closed=namespace_retire)
        owner.retire_namespace=lambda:namespace_retire(lambda proof:retain('namespace',proof),retained=get('namespace'))
        m.journal.close(RUN);return owner,store

    def test_parent_uses_actual_closed_view_scene_readers_and_retains_fresh_originals_after_child_removal(self):
        m=self.model
        with m.lock.held():
            owner,store=self.parent_resource_context();calls=deepcopy(m.fixture_calls);inputs=deepcopy(m.sdk.inputs)
            owner.retire_resources();records=unpack(store.read()['payload'])[0]
            self.assertEqual({'scene','view','namespace','resources/1'},set(records))
            self.assertIsNone(PrivateFeatureState(m.root/'phone-emote-scene.json').read())
            self.assertIsNone(PrivateFeatureState(m.root/'phone-emote-view.json').read())
            final=records['resources/1'];self.assertFalse(final['view']['phaseAfter']['active'])
            self.assertFalse(final['scene']['phaseAfter']['active']);self.assertEqual('look at',final['scene']['avatar']['source']['cameraMode'])
            self.assertGreater(final['view']['avatar']['sequence'],records['view']['frame']['avatar']['sequence'])
            self.assertGreater(final['scene']['world']['sequence'],records['scene']['frame']['world']['sequence'])
            self.assertEqual(calls,m.fixture_calls);self.assertEqual(inputs,m.sdk.inputs)
            owner.state['attempts']=2;owner.retire_resources();later=unpack(store.read()['payload'])[0]
            self.assertEqual(records['view'],later['view']);self.assertEqual(records['scene'],later['scene'])
            self.assertGreater(later['resources/2']['scene']['world']['sequence'],final['scene']['world']['sequence'])

    def test_parent_rejects_actual_retained_browser_even_when_old_release_window_is_complete(self):
        m=self.model
        with m.lock.held():
            owner,store=self.parent_resource_context();m.scene_fault='retain-browser'
            with self.assertRaises(NativeUIError):owner.retire_resources()
            self.assertIsNotNone(PrivateFeatureState(m.root/'phone-emote-scene.json').read())
            self.assertIsNotNone(PrivateFeatureState(m.root/'phone-emote-view.json').read());self.assertIsNone(store.read())


    def test_parent_partial_view_setup_restores_and_retires_actual_view_without_constructing_scene(self):
        m=self.model
        with m.lock.held():
            owner,store=self.parent_resource_context(scene_issued=False);inputs=deepcopy(m.sdk.inputs)
            with patch.object(m,'_emote_fixture_observer',side_effect=AssertionError('Unissued Scene factory')):
                owner.retire_resources()
            records=unpack(store.read()['payload'])[0]
            self.assertNotIn('scene',records);self.assertIsNone(records['resources/1']['scene'])
            self.assertIsNone(PrivateFeatureState(m.root/'phone-emote-view.json').read())
            self.assertEqual('look at',records['resources/1']['view']['avatar']['source']['cameraMode'])
            self.assertEqual(inputs,m.sdk.inputs)


if __name__=='__main__':unittest.main()
