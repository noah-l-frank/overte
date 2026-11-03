"""Original normal preparation + Parent; Qt/OS/renderer are explicit models.

The existing ephemeral TLS provider performs the complete original scene write.
No build, device, real renderer, changed-pixel verdict or whole Journey runs.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit
import uuid
from PIL import Image,ImageDraw

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_navigation_environment import NativeNavigationEnvironment
from adapters.native_fd_owner import OriginalDescriptor,QUERY
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.navigation_arrival import pose_packet
from adapters.navigation_stereo import NavigationStereo
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.navigation import NativeNavigationIO,PicoNavigation
from adapters.pico4.navigation_scene_prefix import NavigationScenePrefix,NavigationSceneIO
from adapters.pico4.navigation_scene_bridge import read_bridge
from adapters.pico4.navigation_scene_state import retained
from adapters.pico4.tablet_home import PicoTabletHome
from adapters.script_journey.history import same
from feature_journeys.navigation_fixture import NavigationResources
from feature_journeys.navigation_scene import PROFILE
from feature_journeys.stereo_navigation_evidence import original_name,observation,clocks
from feature_journeys.scenarios import VERSION as CONTRACT_VERSION
from navigation_observation import viewpoint_urls,owned_scene
from self_tests import test_pico_navigation_prefix as prefix
from self_tests import test_pico_navigation_transit_prefix as transit
from self_tests import test_pico_navigation_bookmark_prefix as bookmark
from self_tests import test_navigation_arrival as arrival_fixture
from self_tests.test_stereo_navigation_evidence import POLICY
from self_tests.test_stereo_graphics_evidence import JourneyPixels


class Model(bookmark.Model):
    def __init__(self,root):
        super().__init__(root);self.editor=False;self.address='';self.ignore_goto=False;self.loss_goto=False;self.scene_fetches=[]
    def raw(self):
        value=super().raw();value['loginControlsVersion']=2
        if self.shown and not self.login and not self.page and not self.lookup_mode:
            ids=['navigation.address'] if self.editor else ['navigation.goto','login.entry']
            retained=[] if self.editor else [row for row in value['controls'] if row['id']=='places.entry']
            value['controls']=retained+[dict(id=name,token=str(uuid.uuid5(uuid.NAMESPACE_URL,str((self.generation,self.focus,self.address,name)))),
                enabled=True,focused=self.focus==name,**(dict(inputReady=True) if name=='login.entry' else {})) for name in ids]
            if value.get('navigationAddressVersion')==1:
                for row in value['controls']:
                    if row['id']=='navigation.address':row.update(textSha256=hashlib.sha256(self.address.encode()).hexdigest(),textLength=len(self.address),inputReady=row['focused'])
        return value
    def send(self,command):
        name=command['controlId']
        if name=='login.entry' and getattr(self,'g1',False) and (self.root/'navigation-prefix-generation-1-restoration.json').exists():
            return super().send(command)
        if name not in ('navigation.goto','navigation.address','login.entry') or self.lookup_mode and name!='login.entry':
            reply=super().send(command)
            if name.startswith('places.visit.') and not self.ignore_arrival:
                self.fetch_scene(self.loaded_row['address'])
            elif name.startswith('places.bookmark.visit.') and not self.bookmark_ignored:
                from adapters.token_places_ui import sha
                selected=next(key for key in self.map if sha(key)==name.rsplit('.',1)[1]);self.fetch_scene(self.map[selected])
            return reply
        self.calls.append(deepcopy(command));self.sequence+=1
        if name=='navigation.goto':self.editor=True
        elif name=='login.entry':self.login=True;self.draft=self.selected;self.focus='';self.generation=str(uuid.uuid4())
        elif command['action']=='activate':self.focus=name
        elif command['action']=='replace':self.address=command['text']
        elif command['action']=='submit' and not self.ignore_goto:
            self.fetch_scene(self.address)
            observed=owned_scene(self.address,viewpoint_required=True)
            actual_base=observed._replace(query='',fragment='').geturl()
            labels=[key for key,url in viewpoint_urls(actual_base).items() if url==self.address]
            assert len(labels)==1;self.owner_test.world.position=labels[0]
            if self.loss_goto:raise NativeUIError('Synthetic applied Return reply lost')
        return dict(schemaVersion=1,bridgeId=self.bridge,commandId=command['commandId'],sequence=command['sequence'],
            performed=True,error='',processId=prefix.PID,updatedEpochMs=self.epoch()),self.epoch()
    def fetch_scene(self,address):
        with self.owner_test.opener.open(address,timeout=2) as response:
            body=response.read();self.scene_fetches.append(dict(url=address,bytes=len(body),receipt=response.headers['X-Overte-Fixture-Response']))
            self.scene_document=json.loads(body)
            self.owner_test.world.current_scene_url=address
    def consume_controller(self,envelope):
        parent=self.owner_test.flow
        preparing=parent.state is None or not parent.state['completed'] and parent.state['active'] is None
        if envelope['commands'][0]['operation']=='tablet.open' and preparing:
            self.controller_calls.append(deepcopy(envelope));self.shown=True;self.generation=str(uuid.uuid4());return
        if envelope['commands'][0]['operation']=='input.primary':self.editor=False
        return super().consume_controller(envelope)


@unittest.skipUnless(shutil.which('openssl'),'Existing ephemeral TLS fixture requires OpenSSL')
class NavigationScenePrefixTests(unittest.TestCase):
    fixture_type=bookmark.NavigationBookmarkPrefixTests
    model_type=Model
    @classmethod
    def setUpClass(cls):bookmark.NavigationBookmarkPrefixTests.setUpClass()
    @classmethod
    def tearDownClass(cls):bookmark.NavigationBookmarkPrefixTests.tearDownClass()
    def setUp(self):
        self.f=self.fixture_type();self.f.model_type=self.model_type;self.f.setUp();self.addCleanup(self.f.doCleanups)
        # Prefix setup already registered the ORIGINAL bound Model.close.
        # Keep that real cleanup (and all server/FD finalizers), while retaining
        # the model's original files even when it explicitly calls cleanup().
        self.f.world.temporary.cleanup=lambda:None
        self.late_parent_home=False;self.parent_created=None
        self.renderer_installed=False;self.render_fault=''
        self.late_environment_return=False
        self.lost_parent_environment_return=False
        self.use_probe_sdk=getattr(self,'use_probe_sdk',False)
        f=self.f;m=f.model;self.inputs=dict(prefix.INPUTS,sceneUrl=f.url+'/scene.json');m.scene_url=self.inputs['sceneUrl']
        self.patches=[patch.object(prefix,'INPUTS',self.inputs),patch.object(prefix.directory_fixture,'INPUTS',self.inputs),
            patch.object(arrival_fixture,'SCENE',self.inputs['sceneUrl']),patch.object(prefix.places,'ADDRESS',viewpoint_urls(self.inputs['sceneUrl'])['A'])]
        for change in self.patches:change.start();self.addCleanup(change.stop)
        provider=NavigationResources(self.inputs,scene_profile=PROFILE,clock_ms=m.epoch);provider.provision(prefix.RUN);provider.activate(prefix.RUN,f.ticket)
        m.provider=provider;f.server.navigation_resources=provider;m.owner_test=f;m.shown=False;m.login=False;f.world.position='C'
        self.bind_world(f.world,getattr(self,'original_scene_url',self.inputs['sceneUrl']))
        old=f.flow
        normal=PicoNavigation(NativeNavigationIO(old.transport.adapter,'owned-model',f.binding['processIdentity'],lambda _op:None),
            f.root/'normal-scene-setup.json',dict(schemaVersion=1,sourceRevision='a'*40,artifactSha256='b'*64,installedCandidateVerified=True),
            f.binding['processIdentity'],self.inputs['sceneUrl'],monotonic=lambda:m.clock,sleep=m.sleep)
        if self.use_probe_sdk:
            from self_tests.pico_navigation_probe_fixture import install_sdk,sdk_model_clock
            sdk_model_clock(self,lambda:self.f.model.epoch())
            install_sdk(self,normal.io.adapter,f.world,m)
        def environment_original():
            raw=json.dumps(m.packet) if m.packet else ''
            if self.late_environment_return:m.clock+=120.001
            if self.lost_parent_environment_return:self.owner.store.path.unlink()
            return raw
        environment=NativeNavigationEnvironment(m.source_send,environment_original,m.epoch,m.guard,prefix.PID,
            monotonic=lambda:m.clock,sleep=m.sleep)
        # Fresh actual independent pose sources configured for the same scene.
        arrival=f.world.arrival();arrival.binding=deepcopy(f.binding);arrival.scene_url=self.inputs['sceneUrl'];arrival.guard=m.guard
        arrival.clock_ms=m.epoch;arrival.monotonic=lambda:m.clock
        def stage(pose,*,intent,before_publish):return f.session.stage(f.binding['processIdentity'],'input.primary',pose,intent=intent,before_publish=before_publish)
        source=old.origin.home.source
        def observed_home():
            value=source.capture();value['onHomeScreen']=not (m.login or m.page or m.editor);return value
        home=PicoTabletHome(SimpleNamespace(pid=source.pid,capture=observed_home,guard=source.guard,clock_ms=source.clock_ms,
            monotonic=source.monotonic,sleep=source.sleep),stage)
        def parent(role,owner):
            def transport(adapter,target,identity,controller):return NavigationSceneIO(adapter,target,identity,controller,owner)
            cls=prefix.NavigationPrefix
            def original(*args,**kwargs):return cls(*args,**kwargs,outer_guard=owner.outer_guard)
            with patch.object(prefix,'NativeNavigationIO',side_effect=transport),patch.object(prefix,'NavigationPrefix',side_effect=original):result=f.make(role)
            original_transit=result.transit_factory
            def transit_owner(parent):
                cls=transit.NavigationTransitJoin
                def join(*args,**kwargs):return cls(*args,**kwargs,preparation=owner)
                with patch.object(transit,'NavigationTransitJoin',side_effect=join):return original_transit(parent)
            result.transit_factory=transit_owner
            if role=='primary':
                f.flow=result;self.parent_created=result
                if self.late_parent_home:
                    age=result.home_age
                    def delayed():age();m.clock+=120.001
                    result.home_age=delayed
            if self.use_probe_sdk:
                from self_tests.pico_navigation_probe_fixture import install_sdk
                install_sdk(self,result.transport.adapter,f.world,m)
            return result
        probe_factory=None
        if self.use_probe_sdk:
            from self_tests.pico_navigation_probe_fixture import probe_factory
        self.owner=NavigationScenePrefix(f.root/'navigation-scene-owner.json',normal,environment,arrival,home,old.phase,f.session,f.lock,
            f.binding,self.inputs,provider.instance,lambda:f.clients['primary'].request('/runs/'+prefix.RUN+'/navigation'),parent,
            self.stereo,
            monotonic=lambda:m.clock,probe_factory=probe_factory)
        self.addCleanup(self.owner.close_host)
    def bind_world(self,w,scene):
        w.current_scene_url=viewpoint_urls(scene)[w.position];tracked=w.update_subject;probe=w.probe
        def actual_probe(after):
            value=probe(after);value['scene']['url']=w.current_scene_url;return value
        def tracked_subject():
            tracked();feet=w.source['avatarPose']['feetPosition'];head=[feet[0],feet[1]+1.6,feet[2]]
            # Explicit producer tracking calibration. The actual consumed avatar
            # translation moves sensorToWorld, while local tracked head pose
            # remains independent; GPU cameras below derive from this HMD.
            w.source['sceneUrl']=w.current_scene_url;w.source['hmd']['sensorPose'][12:15]=[0,1.6,0]
            w.source['hmd']['worldPosition']=head;w.source['view']['position']=head.copy()
        w.update_subject=tracked_subject;w.probe=actual_probe
    def install_scene_renderer(self,w,m):
        f=self.f
        original_camera=w.gpu.mutate
        def camera(packet):
            original_camera(packet);head=w.source['hmd']['worldPosition'];source=packet['source']
            source['stereo']['cameraView'][12:15]=[-v for v in head]
            source['renderTrace']['recordedView']['position']=head.copy()
            for batch in source['renderTrace']['cameraBatches']:
                for value in batch['cameras']:
                    value['view'][12:15]=[-head[0]+(.03 if value['eye']=='left' else -.03),-head[1],-head[2]]
        w.gpu.mutate=camera
        if not getattr(w,'navigation_scene_renderer',False):
            original=w.gpu.send;w.navigation_scene_renderer=True
            def render(command):
                # Explicit existing GPU boundary model: current challenge comes
                # from the actual HTTP marker source; scene position comes from
                # the native original produced after consumed normal controls.
                # Every eye is rasterized separately. No adapter image verdict
                # or desired location is an input to this source fixture.
                with f.opener.open(f.url+'/feature-fixture/v1/runs/'+prefix.RUN+'/current',timeout=2) as response:
                    active=json.loads(response.read())['ticket']
                with f.opener.open(f.url+'/feature-fixture/v1/runs/'+prefix.RUN+'/tickets/'+active+'/marker.png',timeout=2) as response:
                    marker=response.read()
                image=Image.new('RGBA',(1600,800),(100,100,100,255))
                head=w.source['hmd']['worldPosition']
                with Image.open(io.BytesIO(marker)) as card:
                    for index,offset in enumerate((-.03,.03)):
                        eye_image=Image.new('RGBA',(800,800),(100,100,100,255));draw=ImageDraw.Draw(eye_image)
                        eye=[head[0]+offset,head[1],head[2]]
                        # Rasterize each eye from actual authored quads and its
                        # independently calibrated view. No requested viewpoint
                        # label or expected-state image enters this producer.
                        for entity in m.scene_document['Entities']:
                            if '-navigation-' not in entity.get('name','') or entity['type'] not in ('Web','Box'):continue
                            position=entity['position'];dimensions=entity['dimensions'];distance=eye[2]-position['z']
                            if distance<=0:continue
                            x=400+400*(position['x']-eye[0])/distance
                            y=400-400*(position['y']-eye[1])/distance
                            width=400*dimensions['x']/distance;height=400*dimensions['y']/distance
                            box=[round(x-width/2),round(y-height/2),round(x+width/2),round(y+height/2)]
                            if entity['type']=='Web':eye_image.paste(card.resize((box[2]-box[0],box[3]-box[1]),Image.Resampling.NEAREST).convert('RGBA'),tuple(box[:2]))
                            else:
                                color=entity['color'];draw.rectangle(box,fill=tuple(color[key] for key in ('red','green','blue'))+(255,))
                        image.paste(eye_image,(index*800,0))
                if self.render_fault=='duplicated-eye':image.paste(image.crop((0,0,800,800)),(800,0))
                out=io.BytesIO();image.save(out,format='PNG');w.gpu.raw=out.getvalue();w.gpu.pixels=hashlib.sha256(image.tobytes()).hexdigest();w.storage.raw=w.gpu.raw
                return original(command)
            w.gpu.send=render
    def stereo(self,parent,ticket):
        f=self.f;m=f.model;w=f.world;role=parent.role
        images=f.root/'navigation-prefix-images';images.mkdir(mode=0o700,exist_ok=True);journal=uuid.uuid4().hex
        w.owner_store=lambda selected:PrivateFeatureState(f.root/f'navigation-prefix-world-render-{selected}.json')
        self.install_scene_renderer(w,m)
        def graphics():
            value=w.ui.source();value.clock_ms=m.epoch;value.monotonic=lambda:m.clock;value.sleep=m.sleep;return value
        def native():return NativeFeatureObservation(w.features.send,w.features.original,m.epoch,m.guard,prefix.PID,monotonic=lambda:m.clock,sleep=m.sleep)
        def capture():
            value=w._world_render_capture('owned',read_only=True,role=role,require_frame_view=True,source_lock=f.lock)
            value.capture.clock_ms=value.storage.clock_ms=value.receipts.cleanup.clock_ms=m.epoch;return value
        return NavigationStereo(parent.source.arrival,capture,images/original_name(prefix.RUN,role,journal),images,prefix.RUN,f.binding,f.lock,
            parent.source.guard,role=role,journal_id=journal,ui_factory=graphics,native_factory=native,monotonic=lambda:m.clock)
    def verify_scene(self,role,ticket,sequence,previous=None,changed=False):
        actual=self.owner.observe(role);frame=self.owner.scene(role,ticket)
        row=self.owner.state['scenes'][-1];record=self.owner.journal.load(self.owner.state['chunks'])[row['chunk']]
        metadata=Path(record['originals'][0]['path']);raw=Path(record['originals'][1]['path']).read_bytes()
        epoch=frame['frame']['capture']['capturedEpochMs']
        sample=dict(schemaVersion=1,contractVersion=CONTRACT_VERSION,runId=prefix.RUN,sequence=sequence,capturedEpochMs=clocks(frame['frame'])[0],
            state=actual['state'],resources=[],lifecycle=deepcopy(frame['frame']['nativeBefore']['lifecycle']),artifacts=[
                dict(kind='image',name=frame['image']['name'],sequence=sequence,capturedEpochMs=epoch,ticket=ticket,source='world-render-target'),
                dict(kind='file',name=metadata.name,sequence=sequence,capturedEpochMs=epoch,ticket=ticket)])
        policy=deepcopy(POLICY);policy['sceneUrl']=self.inputs['sceneUrl']
        policy['eyes']=dict(left=dict(marker=[254,148,510,212],subject=[275,460,525,595]),
            right=dict(marker=[1042,148,1298,212],subject=[1075,460,1325,595]))
        return observation(raw,metadata.read_bytes(),prefix.RUN,ticket,self.f.flow.phase.fixture_url,policy,sample,
            role=role,previous=previous,changed=changed,monotonic=lambda:self.f.model.clock)
    def test_pre_setup_actual_c_origin_is_retained_while_normal_prepare_reaches_a_and_same_parent(self):
        result=self.owner.prepare();f=self.f;m=f.model;lease=self.owner.lease()
        self.assertEqual('ready',result['phase']);self.assertFalse(result['fullNavigationRecipe'])
        self.assertEqual(viewpoint_urls(self.inputs['sceneUrl'])['C'],lease['originalUrl'])
        self.assertEqual('C',pose_packet(lease['pose'],prefix.RUN,f.binding,self.inputs['sceneUrl'],lease['environment']['capturedEpochMs']))
        self.assertFalse(lease['ui']['open']);self.assertEqual('string',lease['environment']['settings']['selectedType'])
        self.assertEqual('A',f.world.position);self.assertFalse(m.shown);self.assertFalse(m.login)
        self.assertEqual(1,len(m.scene_fetches));self.assertEqual('stereo-scene',m.provider.snapshot(prefix.RUN)['responses'][0]['kind'])
        self.assertEqual(['tablet.open','input.primary','input.primary','tablet.close'],[row['commands'][0]['operation'] for row in m.controller_calls])
        self.assertEqual(lease['environment']['selectedServer'],f.flow.origin.state['original']['selectedServer'])
        self.assertEqual(self.owner.started+120,self.owner.deadline)
        primary=self.owner.observe('primary');actor=self.owner.observe('actor')
        self.assertEqual(primary['state'],actor['state']);self.assertEqual('A',primary['state']['location'])
        self.assertIsNot(self.owner.parents['primary'].source,self.owner.parents['actor'].source)
        self.assertTrue(self.owner.bill()['parts']<512);self.assertTrue(self.owner.raw.bill()['receipts'])
    def test_qurl_original_refuses_before_every_setup_input(self):
        self.f.model.selected_type='url'
        with self.assertRaises(NativeUIError):self.owner.prepare()
        self.assertEqual([],self.f.model.calls);self.assertEqual([],self.f.model.controller_calls)
        self.assertTrue(self.owner.raw.bill()['receipts']);self.assertIsNone(self.owner.state['lease'])
    def test_applied_lost_setup_return_retains_original_lease_and_does_not_replay(self):
        self.f.model.loss_goto=True
        with self.assertRaises(NativeUIError):self.owner.prepare()
        self.assertEqual('A',self.f.world.position);before=deepcopy(self.f.model.calls)
        self.assertEqual('goto',self.owner.state['phase']);self.assertIsNotNone(self.owner.state['lease'])
        with self.assertRaises(NativeUIError):self.owner.prepare()
        self.assertEqual(before,self.f.model.calls);self.assertEqual(1,len(self.f.model.scene_fetches))
    def test_global_deadline_after_actual_callback_intent_prevents_native_writer(self):
        # Delay occurs after the real original callback, not at source.guard.
        with self.f.lock.held():self.owner.original_lease()
        io=NavigationSceneIO(self.owner.normal.io.adapter,'owned-model',self.f.binding['processIdentity'],lambda _op:None,self.owner)
        retained=[]
        def original(command):retained.append(deepcopy(command));self.f.model.clock+=120.001
        io.bind_before_send(original)
        with self.assertRaises(NativeUIError):io.send(dict(commandId=uuid.uuid4().hex))
        self.assertEqual(1,len(retained));self.assertEqual([],self.f.model.calls)
        with self.assertRaises(NativeUIError):io.bind_before_send(lambda _command:None)
    def test_global_deadline_after_original_home_preparation_keeps_intent_without_session_publish(self):
        self.late_parent_home=True
        with self.assertRaises(NativeUIError):self.owner.prepare()
        self.assertIsNotNone(self.parent_created.state['home'])
        self.assertEqual('preparing',self.parent_created.state['phase'])
        self.assertEqual(['tablet.open','input.primary'],[row['commands'][0]['operation'] for row in self.f.model.controller_calls])
        self.assertEqual('parent',self.owner.state['phase']);self.assertEqual(1,self.f.model.home_count)
    def test_aggregate_other_parts_refuse_before_environment_send_or_setup_input(self):
        for index in range(512):
            path=self.f.root/f'foreign-original.part-{index:03d}.bin';path.write_bytes(b'original');path.chmod(0o600)
        before=self.f.model.source_sequence
        with self.assertRaises(NativeUIError):self.owner.prepare()
        self.assertEqual(before,self.f.model.source_sequence);self.assertEqual([],self.f.model.calls)
        self.assertEqual([],self.f.model.controller_calls);self.assertFalse(self.owner.raw.state['pending'])
    def test_qml_response_capacity_is_reserved_before_the_actual_native_writer(self):
        with self.f.lock.held():self.owner.original_lease()
        original=self.owner.raw.reserve
        def refused(role,command,limit,**kwargs):
            if command.get('source')=='navigation-ui' and command.get('kind')=='status':raise NativeUIError('Actual response admission refused')
            return original(role,command,limit,**kwargs)
        with patch.object(self.owner.raw,'reserve',side_effect=refused),self.f.lock.held(),self.assertRaises(NativeUIError):
            self.owner.normal.invoke('places.goto',dict(url=viewpoint_urls(self.inputs['sceneUrl'])['A']))
        self.assertEqual([],self.f.model.calls);self.assertEqual(1,len(self.owner.state['commands']))
        self.assertEqual(['tablet.open'],[row['commands'][0]['operation'] for row in self.f.model.controller_calls])
    def test_already_issued_late_literal_is_durable_before_parser_without_new_read_authority(self):
        self.late_environment_return=True
        with self.assertRaises(NativeUIError):self.owner.prepare()
        self.assertEqual(1,self.owner.raw.bill()['receipts']);self.assertEqual([],self.owner.raw.state['pending'])
        self.assertEqual(json.dumps(self.f.model.packet),self.owner.raw.literal(self.owner.raw_references[-1]))
        self.assertEqual([],self.f.model.calls);self.assertEqual([],self.f.model.controller_calls)
        self.assertIsNone(self.owner.state['lease'])
        with self.assertRaises(NativeUIError):self.owner.environment.read(prefix.RUN)
        self.assertEqual(1,self.f.model.source_sequence)
    def test_issued_literal_survives_lost_parent_header_with_zero_new_query_authority(self):
        self.lost_parent_environment_return=True
        with self.assertRaises(NativeUIError):self.owner.prepare()
        self.assertFalse(self.owner.store.path.exists());self.assertEqual(1,self.owner.raw.bill()['receipts'])
        self.assertEqual(json.dumps(self.f.model.packet),self.owner.raw.literal(self.owner.raw_references[-1]))
        with self.assertRaises(NativeUIError):self.owner.environment.read(prefix.RUN)
        self.assertEqual(1,self.f.model.source_sequence);self.assertEqual([],self.f.model.calls)
    def test_actual_original_primary_and_actor_stereo_follow_same_normal_preparation(self):
        self.owner.prepare();primary=self.owner.observe('primary');actor=self.owner.observe('actor')
        ticket=self.f.ticket
        left=self.owner.scene('primary',ticket);right=self.owner.scene('actor',ticket)
        self.assertEqual(primary['state'],actor['state']);self.assertEqual(2,len(self.owner.state['scenes']))
        self.assertNotEqual(left['frame']['capture']['requestId'],right['frame']['capture']['requestId'])
        self.assertNotEqual(left['image']['name'],right['image']['name'])
        self.assertEqual('primary',left['image']['role']);self.assertEqual('actor',right['image']['role'])
        self.assertFalse(left['proof']['memory']['present']);self.assertFalse(right['proof']['memory']['present'])
        self.assertIsNone(self.f.world.owner_store('primary').read());self.assertIsNone(self.f.world.owner_store('actor').read())
        self.assertEqual([],list(self.f.world.native_root.iterdir()))
        self.assertLess(self.owner.bill()['parts'],512)
    def test_unselected_scene_provider_refuses_before_normal_setup_mutation(self):
        self.f.model.provider.scene_profile=None;self.f.model.provider.version=1
        with self.assertRaises((ValueError,NativeUIError)):self.owner.prepare()
        self.assertEqual([],self.f.model.calls);self.assertEqual([],self.f.model.controller_calls)
        self.assertIsNone(self.owner.state['lease'])
    def root_refuses_without_input(self):
        before=self.f.model.source_sequence
        with self.f.lock.held(),self.assertRaises(NativeUIError):self.owner.bound()
        self.assertEqual(before,self.f.model.source_sequence)
        self.assertEqual([],self.f.model.calls);self.assertEqual([],self.f.model.controller_calls)
    def test_warm_metadata_foreign_scope_refuses_before_actual_query_or_input(self):
        self.owner.scope['binding']['processIdentity']='32:10002';self.root_refuses_without_input()
    def test_root_parent_callback_replacement_refuses_before_actual_query_or_input(self):
        self.owner.store._parent=lambda:None;self.root_refuses_without_input()
    def test_warm_metadata_current_scope_tuple_alias_refuses_before_actual_query(self):
        self.owner.scope['binding']=list(self.owner.scope['binding'].items());self.root_refuses_without_input()
    def test_root_seal_rejects_current_original_byte_rewrite_before_query(self):
        value=deepcopy(self.owner.state);value['phase']='retired'
        self.owner.store.write(value,self.owner.disk)
        self.root_refuses_without_input()
    def test_root_seal_rejects_equal_byte_replacement_inode_before_query(self):
        path=self.owner.path;replacement=path.with_name('equal-root-replacement.json')
        replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);os.replace(replacement,path)
        self.root_refuses_without_input()
    def test_root_seal_rejects_mutated_original_memory_before_query(self):
        self.owner.state['phase']='retired';self.root_refuses_without_input()
    def test_root_seal_rejects_equal_memory_replacement_before_query(self):
        self.owner.disk=deepcopy(self.owner.disk);self.root_refuses_without_input()
    def test_root_seal_rejects_equal_sealed_bytes_replacement_before_query(self):
        self.owner.root_raw=bytes(bytearray(self.owner.root_raw));self.root_refuses_without_input()
    def test_root_seal_rejects_equal_seal_tuple_replacement_before_query(self):
        self.owner.root_seal=tuple(value for value in self.owner.root_seal);self.root_refuses_without_input()
    def test_root_seal_actual_recycled_read_ofd_refuses_and_retains_foreign_description(self):
        foreign=OriginalDescriptor(self.owner.path,os.O_RDONLY|os.O_CLOEXEC)
        pread=os.pread;replaced=[]
        def swap(descriptor,size,offset):
            raw=pread(descriptor,size,offset)
            if not replaced:os.dup2(foreign.fd,descriptor,inheritable=False);replaced.append(descriptor)
            return raw
        with patch.object(os,'pread',side_effect=swap):self.root_refuses_without_input()
        self.assertEqual(1,len(replaced));foreign.require(foreign.fd)
        self.assertEqual(1,fcntl.fcntl(replaced[0],QUERY,foreign.anchor))
        # Both uncertain original and foreign OFD halves remain owned by this
        # actual runner until process finalization. Never force-close a number
        # merely because it once named our original read window.
        self.retained_fd_counter=foreign
    def test_already_a_with_old_same_ticket_scene_receipt_cannot_prove_ignored_goto_effect(self):
        f=self.f;m=f.model;f.world.position='A'
        with f.opener.open(viewpoint_urls(self.inputs['sceneUrl'])['A'],timeout=2) as response:response.read()
        self.assertEqual(1,len(m.provider.snapshot(prefix.RUN)['responses']));m.ignore_goto=True
        with self.assertRaises(NativeUIError):self.owner.prepare()
        self.assertEqual('arrival',self.owner.state['phase']);self.assertIsNone(self.owner.state['parent'])
        self.assertEqual(['tablet.open'],[row['commands'][0]['operation'] for row in m.controller_calls])
        self.assertEqual(1,len(m.provider.snapshot(prefix.RUN)['responses']))
    def test_same_eleven_normal_actions_have_independent_changed_a_b_a_stereo_for_both_roles(self):
        self.run_eleven()
    def run_eleven(self,*,stereo=True):
        self.owner.prepare();previous={};measured={role:[] for role in ('primary','actor')}
        if not stereo:
            # Baseline observations still belong to BOTH actual roles when
            # the optional enclosing image-proof acquisitions are absent.
            self.owner.observe('primary');self.owner.observe('actor')
            self.install_scene_renderer(self.f.world,self.f.model)
        if stereo:
            for role in measured:
                evidence,previous[role]=self.verify_scene(role,self.f.ticket,1);measured[role].append(evidence['location'])
        for index,verb in enumerate(prefix.VERBS):
            call=self.f.activate(verb);self.owner.act(call)
            primary=self.owner.observe('primary');actor=self.owner.observe('actor');self.assertEqual(primary['state'],actor['state'])
            if stereo and index in (7,10):
                for role in measured:
                    evidence,previous[role]=self.verify_scene(role,call['ticket'],len(measured[role])+1,previous[role],True)
                    measured[role].append(evidence['location'])
                    self.assertTrue(all(value['subjectChangedFraction']>=.05 for value in evidence['eyes'].values()))
        if stereo:self.assertEqual(dict(primary=['A','B','A'],actor=['A','B','A']),measured)
        self.assertEqual(11,len(self.owner.parents['primary'].state['completed']));self.assertEqual(6 if stereo else 0,len(self.owner.state['scenes']))
        self.assertEqual(viewpoint_urls(getattr(self,'original_scene_url',self.inputs['sceneUrl']))['C'],self.owner.lease()['originalUrl'])
        self.assertFalse(self.f.model.shown);self.assertLess(self.owner.bill()['parts'],512)
    def opened(self):
        self.owner.prepare();call=self.f.activate('open');self.owner.act(call);return call
    def test_bridge_is_exact_original_complete_session_chain_and_old_lease_replacement_refuses(self):
        self.opened();parent=self.owner.parent('primary');reference,prior=self.owner.directory_bridge(parent)
        self.assertEqual(self.owner.state['controllers'][-1]['envelope'],read_bridge(reference,parent))
        self.assertEqual(parent.state['home']['envelope']['sequence']+2,prior['sequence'])
        # Equal bytes on a genuinely new inode cannot be promoted by reloading
        # the ordinary chunks cache or recomputing a new reference.
        path=Path(reference['originalLease']['path']);replacement=path.with_name('equal-original-replacement.json')
        replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);os.replace(replacement,path)
        self.owner.journal.load(self.owner.state['chunks'])
        with self.assertRaises(NativeUIError):self.owner.directory_bridge(parent)
    def test_unknown_actual_neutral_answer_is_retained_and_blocks_places_entry_without_second_open(self):
        self.owner.prepare();call=self.f.activate('open');before=deepcopy(self.f.model.calls);read=self.f.xr.read_status
        def unknown(**kwargs):
            status=read(**kwargs)
            if kwargs.get('expected_sequence') is None and self.owner.state['controllers'][-1]['phase']=='opening':status.update(state='unknown')
            return status
        with patch.object(self.f.xr,'read_status',side_effect=unknown),self.assertRaises(NativeUIError):self.owner.act(call)
        self.assertEqual('unknown',self.owner.state['controllers'][-1]['statuses'][-1]['status']['state'])
        controllers=deepcopy(self.f.model.controller_calls)
        with self.assertRaises(NativeUIError):self.owner.act(call)
        self.assertEqual(controllers,self.f.model.controller_calls);self.assertEqual(before,self.f.model.calls)
        self.assertEqual('opening',self.owner.state['phase'])
    def test_actual_last_transit_home_callback_expiry_preserves_intent_with_zero_publish(self):
        self.owner.prepare()
        for verb in prefix.VERBS[:7]:self.owner.act(self.f.activate(verb))
        parent=self.owner.parent('primary');factory=parent.transit_factory
        def delayed(parent):
            child=factory(parent);original=child.age
            def age():
                original()
                if child.state is not None and child.state['controllers']['home'] is not None:self.f.model.clock=self.owner.deadline+.001
            child.age=age;return child
        parent.transit_factory=delayed;before=deepcopy(self.f.model.controller_calls)
        with self.assertRaises(NativeUIError):self.owner.act(self.f.activate('directory-select'))
        self.assertIsNotNone(parent.transit_join.state['controllers']['home'])
        self.assertEqual(before,self.f.model.controller_calls);self.assertEqual('acting',self.owner.state['phase'])
    def test_mutated_parent_transport_is_refused_before_another_native_source_query(self):
        self.owner.prepare();parent=self.owner.parent('primary');before=self.f.model.source_sequence
        parent.transport.identity='32:foreign-instance'
        with self.assertRaises(NativeUIError):self.owner.observe('primary')
        self.assertEqual(before,self.f.model.source_sequence)

    def test_registered_original_model_cleanup_retains_bytes_but_closes_owned_server_and_fds(self):
        from adapters.pico4.navigation_originals import read_original,signature
        world=self.f.world;root=world.root;calls=[]
        original_cleanup=world.temporary.cleanup
        def retained():calls.append('original-bound-close');return original_cleanup()
        world.temporary.cleanup=retained
        # Opaque producer-fixture originals solely exercise root retention;
        # these files grant no fresh Native/capture or recipe capability.
        for path,raw in ((world.native_root/'retention-original.png',world.raw),
                         (world.artifacts/'retention-original.bin',b'original-model-literal\0\xff')):
            descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(descriptor,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        originals=[read_original(path) for path in sorted(root.rglob('*')) if path.is_file()]
        self.assertGreaterEqual(len(originals),2);before=signature(root.lstat())
        self.doCleanups()  # Actual registered bound close + socket/thread/OFD cleanup.
        self.assertEqual(['original-bound-close'],calls)
        self.assertEqual(before,signature(root.lstat()))
        self.assertEqual(originals,[read_original(row['path']) for row in originals])
        self.assertFalse(self.f.thread.is_alive());self.assertEqual(-1,self.f.server.socket.fileno())
        self.assertTrue(self.owner.directory.closed);self.assertEqual((-1,-1),(self.owner.directory.fd,self.owner.directory.anchor))


class NavigationSceneStateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='navigation-scene-gate-');self.temp._finalizer.detach();self.root=Path(self.temp.name)
        self.root.chmod(0o700);print('Retained original Navigation host ownership fixture:',self.root,flush=True)
        self.adapter=SimpleNamespace(pico_configuration=('model-layer',self.root))
    def directory(self,target):
        key=hashlib.sha256(('org.overte.pico\0'+target).encode()).hexdigest()[:32]
        path=self.root/('feature-scripts-'+key);path.mkdir(mode=0o700);return path
    def test_rootless_raw_parts_indexes_pending_and_forged_done_remain_owned_per_target(self):
        for index,name in enumerate(('navigation-scene-owner.json','navigation-scene-owner.json.frame-000.json',
            'navigation-scene-raw.json.part-000.bin','navigation-scene-raw.json.index-00.json',
            'navigation-scene-raw.json.pending-unknown','normal-scene-setup.json')):
            target='owned-model-'+str(index);directory=self.directory(target);path=directory/name
            path.write_text('{"phase":"retired"}');path.chmod(0o600)
            with self.subTest(name=name):self.assertTrue(retained(self.adapter,target))
        self.assertFalse(retained(self.adapter,'unowned-model'))
    def test_symlinked_or_oversized_namespace_fails_closed_without_native_queries(self):
        target='owned-model';directory=self.directory(target)
        for index in range(4097):
            path=directory/f'unrelated-{index:04d}';path.write_bytes(b'original');path.chmod(0o600)
        with self.assertRaises(NativeUIError):retained(self.adapter,target)
        other='symlinked-model';path=self.directory(other);path.rmdir();path.symlink_to(directory,target_is_directory=True)
        with self.assertRaises(NativeUIError):retained(self.adapter,other)


if __name__=='__main__':unittest.main()
