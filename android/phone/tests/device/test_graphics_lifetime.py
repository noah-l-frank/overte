"""Real private journals, independent synthetic sources, no native/device runs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest
import uuid

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.native_graphics_subject import NativeGraphicsSubject
from adapters.native_phone_scene_loads import NativePhoneSceneLoads,resource_hash
from adapters.native_phone_web_runtime import NativePhoneWebRuntime
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.graphics_resources import RESOURCE
from overte_phone_graphics_fixture import GraphicsFixtureReader
from overte_phone_graphics_lifetime import PhoneGraphicsLifetime
from overte_phone_script_history import pack,unpack
from overte_phone_script_lock import PhoneScriptSourceLock
from test_graphics_fixture_reader import Fixture,RUN,TICKET,URL
from test_graphics_scene import Model
from test_graphics_measurements import Sources
from test_graphics_images import BINDING
from self_tests.test_native_phone_scene_loads import Boundary as Loads,row as load_row
from self_tests.test_native_phone_web_runtime import Boundary as Web


class SourcesModel:
    def __init__(self):
        self.scene=Model();self.root=self.scene.root;self.clock=0.;self.okay=True;self.fault=None;self.commands=[]
        self.binding=deepcopy(BINDING);self.f=Fixture();self.scene_doc=Sources()
        self.native=deepcopy(self.scene_doc.subject_before);self.native['source'].update(subjectVersion=2,
            avatarPose=dict(feetPosition=[0,-.2,0],orientation=[0,0,0,1],modelScale=1.25))
        self.native['source']['sceneUrl']=URL+'/runs/'+RUN+'/tickets/'+TICKET+'/'+RESOURCE
        marker=next(row for row in self.native['source']['entities'] if row['type']=='Web')
        marker['sourceUrl']=URL+'/runs/'+RUN+'/tickets/'+TICKET+'/graphics-marker.v1.html'
        self.load=Loads();self.load.rows=[load_row(resourceSha256=resource_hash(self.native['source']['sceneUrl']))]
        self.web=Web();self.sequence=0;self.values={}
        self.original=deepcopy(self.native);self.original['source']=deepcopy(self.scene.original)
        self.original['source']['subjectVersion']=2
        self.released=False
        with self.f.graphics.response(RUN,TICKET,request_authority='controlled.invalid',request_scheme='http') as response:
            status,body,nonce,written=response
            written(dict(responseId=nonce,status=status,bytes=len(body),sha256=hashlib.sha256(body).hexdigest()))
        self.lock=PhoneScriptSourceLock(self.root/'phone-script-sources.lock')
    def close(self):self.scene.close()
    def state_path(self,_selector):return self.root/'session.json'
    def epoch(self):return 20000+round(self.clock*1000)
    def sleep(self,seconds):self.clock+=seconds;self.f.epoch=self.epoch()
    def normal_feature_runtime(self,_selector,*,read_only):
        assert read_only;return None,None,deepcopy(self.binding),lambda:self.okay,None
    def send_subject(self,request):
        self.commands.append(deepcopy(request));self.sequence+=1;value=deepcopy(self.native)
        value.update(requestId=request['commandId'],sequence=self.sequence,requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch())
        if self.fault=='subject-birth':value['instance']='f'*32
        if self.fault=='subject-cursor':value['sequence']=1
        if self.fault=='leak':value['source']['entities']=deepcopy(self.scene_doc.subject_before['source']['entities'][:1]);value['source']['absentIds']=value['source']['absentIds'][1:]
        if self.fault=='foreign-change':value['source']['scan']['unowned'][0]['sha256']='e'*64
        if self.fault=='pose':value['source']['avatarPose']['feetPosition'][0]+=1
        self.values['subject']=value
    def options(self):return dict(monotonic=lambda:self.clock,sleep=self.sleep)
    def _graphics_subject_observer(self,_selector,*,read_only):
        assert read_only
        return NativeGraphicsSubject(self.send_subject,lambda:json.dumps(self.values['subject']),self.epoch,lambda:self.okay,31,**self.options())
    def _scene_load_observer(self,_selector,*,read_only):
        assert read_only
        def send(request):
            self.commands.append(deepcopy(request));self.load.epoch=self.epoch();self.load.send(request)
            if self.fault=='load-birth':self.load.sample['instance']='f'*32
            if self.fault=='load-cursor':self.load.sample['sequence']=1
            if self.fault=='load-incomplete':self.load.sample['complete']=False
            if self.fault=='pending':
                row=self.load.sample['requests'][-1];row.update(pending=True,releasedEpochMs=None);self.load.sample['pendingLeases']=1
        return NativePhoneSceneLoads(send,self.load.original,self.epoch,lambda:self.okay,31,**self.options())
    def _web_runtime_observer(self,_selector,*,read_only):
        assert read_only
        def send(request):
            self.commands.append(deepcopy(request));self.web.clock=self.clock;self.web.revoked=self.released;self.web.send(request)
            if self.fault=='slow':self.sleep(1.501)
        def edit(packet):
            if self.fault=='web-birth':packet['instance']='f'*32
            if self.fault=='java-birth':packet['source']['java']['instance']='f'*32
            if self.fault=='web-cursor':packet['sequence']=1
            if self.fault=='java-remnant':
                row=packet['source']['java']['views'][0];row.update(sourceOwned=True,documentOwned=True)
            if self.fault=='callback':packet['source']['nativeAfter']['views'][0]['callbacks']=1
            if self.fault=='never-seen':
                for key in ('nativeBefore','nativeAfter'):packet['source'][key].update(knownHandles=[],views=[])
                packet['source']['java'].update(views=[],creations=[])
        self.web.edit=edit
        return NativePhoneWebRuntime(send,self.web.original,self.epoch,lambda:self.okay,31,**self.options())
    def source(self):return GraphicsFixtureReader(self.f.client,RUN,epoch_ms=self.epoch)
    def factory(self,role='primary',stage=0):return PhoneGraphicsLifetime(self,'controlled',self.source(),role,stage,self.lock,**self.options())
    def retire_fixture_and_restore(self):
        self.f.graphics.retire(RUN);self.f.journal.close(RUN);self.f.client.closed=True;self.released=True
        self.native['source']=deepcopy(self.original['source'])
        self.load.generation=2;self.load.rows.append(load_row(uuid.uuid4().hex,generation=2,resourceSha256=resource_hash(self.native['source']['sceneUrl'])))
    def archive(self,value,role='primary',stage=0):return PhoneGraphicsLifetime.archive(value,run=RUN,fixture_url=URL,
        provider_instance=self.f.graphics.instance,role=role,stage=stage,binding=self.binding)


class GraphicsLifetimeTests(unittest.TestCase):
    def setUp(self):self.m=SourcesModel();self.addCleanup(self.m.close)
    def test_active_native_and_java_ownership_then_whole_fixture_release_requires_real_three_second_window(self):
        m=self.m
        with m.lock.held():
            owner=m.factory();active=owner.observe_active();self.assertTrue(active['providerAfter']['active'])
            m.retire_fixture_and_restore();value=owner.wait_released(m.original);state=m.archive(value)
            self.assertEqual('released',state['phase']);window=state['windows'][-1]
            self.assertEqual(13,len(window['samples']));self.assertGreaterEqual(window['elapsedMs'],3000)
            self.assertTrue(owner.store.path.exists());self.assertEqual(1,len(state['activeProofs']))
        self.assertTrue(all(command['action'].endswith(('observe','observation')) for command in m.commands))
        self.assertEqual([],m.scene.sdk.inputs)
    def test_recreated_reader_preserves_each_original_source_history_and_active_proof(self):
        m=self.m
        with m.lock.held():
            owner=m.factory();first=owner.observe_active();owner=m.factory();second=owner.observe_active()
            self.assertGreater(second['subject']['sequence'],first['subject']['sequence'])
            self.assertGreater(second['web']['source']['java']['sequence'],first['web']['source']['java']['sequence'])
            m.retire_fixture_and_restore();owner=m.factory();state=m.archive(owner.wait_released(m.original))
            self.assertEqual(2,len(state['activeProofs']))
    def test_provider_retirement_without_original_user_scene_restoration_remains_red(self):
        m=self.m
        with m.lock.held():
            owner=m.factory();owner.observe_active();m.f.graphics.retire(RUN);m.released=True
            with self.assertRaises(NativeUIError):owner.wait_released(m.original)
            self.assertEqual('releasing',owner.state['phase']);self.assertFalse(owner.state['windows'][-1]['complete'])
    def test_never_observed_web_scope_cannot_claim_empty_cleanup(self):
        m=self.m
        with m.lock.held():
            owner=m.factory();m.retire_fixture_and_restore()
            with self.assertRaises(NativeUIError):owner.wait_released(m.original)
            self.assertEqual([],owner.state['windows'])
    def test_deleted_entities_cannot_hide_live_java_document_or_native_callback(self):
        for fault in ('java-remnant','callback','pending','load-incomplete','leak','foreign-change','pose'):
            m=SourcesModel()
            try:
                with m.lock.held():
                    owner=m.factory();owner.observe_active();m.retire_fixture_and_restore();m.fault=fault
                    with self.subTest(fault=fault),self.assertRaises(NativeUIError):owner.wait_released(m.original)
                    self.assertTrue(owner.store.path.exists());self.assertEqual('releasing',owner.state['phase'])
            finally:m.close()
    def test_recreated_scope_rejects_native_java_and_load_birth_or_cursor_reset(self):
        for fault in ('subject-birth','subject-cursor','load-birth','load-cursor','web-birth','web-cursor','java-birth'):
            m=SourcesModel()
            try:
                with m.lock.held():
                    owner=m.factory();owner.observe_active();m.retire_fixture_and_restore();m.fault=fault;owner=m.factory()
                    with self.subTest(fault=fault),self.assertRaises(NativeUIError):owner.wait_released(m.original)
                    self.assertTrue(owner.store.path.exists())
            finally:m.close()
    def test_provider_must_be_retired_before_any_quiet_sample_can_count(self):
        m=self.m
        with m.lock.held():
            owner=m.factory();owner.observe_active();source=deepcopy(m.native['source']);m.native['source']=deepcopy(m.original['source']);m.released=True
            with self.assertRaises(NativeUIError):owner.wait_released(m.original)
            self.assertTrue(m.f.graphics.runs[RUN]['active']);self.assertEqual(source['sceneUrl'],owner.state['activeProofs'][0]['subject']['source']['sceneUrl'])
    def test_a_late_remnant_invalidates_the_window_and_retry_requires_a_new_complete_window(self):
        m=self.m
        with m.lock.held():
            owner=m.factory();owner.observe_active();m.retire_fixture_and_restore()
            ordinary=m.sleep
            def sleep(value):
                ordinary(value)
                if m.clock>=2.75:m.fault='callback'
            owner.sleep=sleep
            with self.assertRaises(NativeUIError):owner.wait_released(m.original)
            first=m.clock;self.assertFalse(owner.state['windows'][-1]['complete']);m.fault=None;owner=m.factory()
            value=owner.wait_released(m.original);state=m.archive(value)
            self.assertGreaterEqual(m.clock-first,3);self.assertEqual(2,len(state['windows']))
            self.assertFalse(state['windows'][0]['complete']);self.assertTrue(state['windows'][1]['complete'])
    def test_each_role_has_separate_live_sources_and_cannot_borrow_the_other_role_journal(self):
        m=self.m
        with m.lock.held():
            primary=m.factory();p=primary.observe_active();actor=m.factory('actor');a=actor.observe_active()
            self.assertNotEqual(p['subject']['requestId'],a['subject']['requestId']);self.assertNotEqual(p['web']['commandId'],a['web']['commandId'])
            self.assertNotEqual(primary.store.path,actor.store.path)
            with self.assertRaises(NativeUIError):m.archive(primary.previous,role='actor')
    def test_original_user_scene_cannot_be_replaced_during_recovery(self):
        m=self.m
        with m.lock.held():
            owner=m.factory();owner.observe_active();m.retire_fixture_and_restore();m.fault='callback'
            with self.assertRaises(NativeUIError):owner.wait_released(m.original)
            other=deepcopy(m.original);other['source']['avatarPose']['feetPosition'][0]+=1;m.fault=None
            with self.assertRaises(NativeUIError):m.factory().wait_released(other)
    def test_lost_journal_write_retains_accepted_cursors_and_cannot_return_success(self):
        m=self.m
        with m.lock.held():
            owner=m.factory();owner.observe_active();m.retire_fixture_and_restore();write=owner.store.write
            def lost(value,previous):write(value,previous);raise RuntimeError('Synthetic lost write response')
            owner.store.write=lost
            with self.assertRaises(RuntimeError):owner.wait_released(m.original)
            owner=m.factory();self.assertEqual('releasing',owner.state['phase'])
            self.assertEqual('released',m.archive(owner.wait_released(m.original))['phase'])
    def test_ignored_journal_write_or_foreign_replacement_cannot_hide_unretired_scope(self):
        m=self.m
        with m.lock.held():
            owner=m.factory();owner.observe_active();m.retire_fixture_and_restore();owner.store.write=lambda *_args:None
            with self.assertRaises(NativeUIError):owner.wait_released(m.original)
            foreign=owner.store.read();foreign['runId']='f'*32;owner.store.write=PrivateFeatureState(owner.store.path).write
            owner.store.write(foreign,owner.store.read())
            with self.assertRaises(NativeUIError):m.factory()
            self.assertEqual('f'*32,owner.store.read()['runId'])
    def test_missing_native_results_and_slow_source_group_fail_without_input(self):
        m=self.m
        with m.lock.held():
            owner=m.factory();m.web.ignore=True
            with self.assertRaises(NativeUIError):owner.observe_active()
            self.assertEqual([],owner.state['activeProofs']);m.web.ignore=False;m.fault='slow';owner=m.factory()
            with self.assertRaises(NativeUIError):owner.observe_active()
        self.assertEqual([],m.scene.sdk.inputs)
    def test_archive_is_pure_and_refuses_fabricated_quiet_duration_or_changed_originals(self):
        m=self.m
        with m.lock.held():
            owner=m.factory();owner.observe_active();m.retire_fixture_and_restore();value=owner.wait_released(m.original)
        before=len(m.commands);self.assertEqual('released',m.archive(value)['phase']);self.assertEqual(before,len(m.commands))
        for edit in ('duration','sample','source','binding','complete'):
            other=deepcopy(value);state=unpack(other['payload'])[0]
            if edit=='duration':state['windows'][-1]['elapsedMs']=2999
            elif edit=='sample':state['windows'][-1]['samples']=state['windows'][-1]['samples'][-2:]
            elif edit=='source':state['web']['source']['java']['instance']='f'*32
            elif edit=='binding':state['binding']['artifactSha256']='f'*64
            else:state['windows'][-1]['complete']=False
            other['payload']=pack([state])
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):m.archive(other)
    def test_new_process_requires_explicit_stage_and_cannot_relabel_old_originals(self):
        m=self.m
        with m.lock.held():
            owner=m.factory();owner.observe_active();m.binding['processIdentity']='32:1234'
            with self.assertRaises(NativeUIError):m.factory()
            with self.assertRaises(NativeUIError):m.archive(owner.previous)
            self.assertTrue(owner.store.path.exists())

    def test_frozen_original_clocks_cannot_accumulate_a_quiet_window_from_local_time(self):
        m=self.m
        with m.lock.held():
            owner=m.factory();owner.observe_active();m.retire_fixture_and_restore()
            m.epoch=lambda:20000;m.sleep=lambda value:setattr(m,'clock',m.clock+value)
            m.web.now=lambda:20000;owner.source.epoch_ms=m.epoch;owner.sleep=m.sleep
            owner.subject=m._graphics_subject_observer('controlled',read_only=True)
            owner.loads=m._scene_load_observer('controlled',read_only=True);owner.web=m._web_runtime_observer('controlled',read_only=True)
            with self.assertRaises(NativeUIError):owner.wait_released(m.original)
            self.assertEqual('releasing',owner.state['phase']);self.assertFalse(owner.state['windows'][-1]['complete'])
    def test_slow_provider_with_frozen_clocks_is_included_in_whole_group_freshness(self):
        m=self.m
        with m.lock.held():
            owner=m.factory();actual=owner.source.status
            def slow(previous=None):
                value=actual(previous);m.clock+=1.501;return value
            owner.source.status=slow
            with self.assertRaises(NativeUIError):owner.observe_active()
            self.assertEqual([],owner.state['activeProofs'])
    def test_guard_loss_during_accepted_source_cannot_publish_or_erase_originals(self):
        m=self.m
        with m.lock.held():
            owner=m.factory();owner.observe_active();before=deepcopy(owner.previous);m.okay=False
            with self.assertRaises(NativeUIError):owner.observe_active()
            self.assertEqual(before,owner.store.read())
    def test_shared_quiet_history_cannot_be_relabelled_as_another_stage_or_run(self):
        m=self.m
        with m.lock.held():
            owner=m.factory();owner.observe_active();m.retire_fixture_and_restore();value=owner.wait_released(m.original)
        for field,new in [('role','actor'),('stage',1),('runId','f'*32),('providerInstance','f'*32),('graphicsLifetimeVersion',True)]:
            other=deepcopy(value);other[field]=new
            with self.subTest(field=field),self.assertRaises(NativeUIError):m.archive(other)


if __name__=='__main__':unittest.main()
