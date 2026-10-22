"""Primary scene/PNG/Script/source owners joined at modeled product SDKs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from io import BytesIO
import unittest
from unittest.mock import patch
from PIL import Image,ImageDraw
from feature_journeys.fixtures import challenge
from feature_journeys.witness import Journal

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.create_marker_files import originals
from ios.adapters.create_marker_identity import PreparedCreateMarker
from ios.adapters.create_primary import CreatePrimary
from ios.adapters.create_export_artifact import CreateExportArtifact
from ios.self_tests import test_ios_create_actions as actions_tests
from ios.self_tests import test_ios_create_sources as sources_tests
from ios.self_tests import test_ios_create_sample as sample_tests
from ios.self_tests import test_ios_create_marker_measurements as marker_tests
from ios.self_tests.test_ios_create_peer import domain_pair
from ios.self_tests.test_ios_create_state import RUN,EPOCH
from ios.self_tests.test_ios_create_files import BINDING,URL


def subject_colors(domain):
    """Renderer SDK appearance from actual visible material/geometry only."""
    if not domain:color=(30,50,70)
    else:
        assert len(domain)==1;row=domain[0]
        if row['type']=='Model':color=(180,40,20) if row['textures'] else (160,180,200)
        elif row['type']=='PolyVox':
            filled=1
            for axis in row['voxels']['volume']:filled*=axis
            color=(170,40,180) if row['voxels']['onCount']<filled else (30,180,40)
        else:assert row['type'] in ('Shape','Box');color=(160,180,30)
    return color,tuple((channel+80)%256 for channel in color)


class ClockedSDK(sources_tests.OriginalSDK):
    def __init__(self,clock):self.shared=clock;super().__init__()
    @property
    def clock(self):return self.shared.clock
    @clock.setter
    def clock(self,value):self.shared.clock=value
    def epoch(self):return self.shared.epoch()
    def tick(self):self.clock+=.001;return self.epoch()


class CreatePrimaryImagesTests(unittest.TestCase):
    def setUp(self):
        self.sh=sample_tests.CreateSampleTests();self.sh.setUp();self.addCleanup(self.sh.doCleanups)
        self.ah=actions_tests.CreateActionsTests();self.ah.setUp();self.addCleanup(self.ah.doCleanups)
        self.h=sources_tests.CreateSourcesTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        bindings=patch.multiple(sample_tests,RUN=RUN,BINDING=BINDING);bindings.start();self.addCleanup(bindings.stop)
        self.sh.template['runId']=RUN
        for row in self.sh.template['source']['entities']:
            row['name']=row['name'].replace(sample_tests.RUN,RUN)
            if row['type']=='Web':
                row['name']='e2e-'+RUN+'-script';row['sourceUrl']=URL+'tickets/'+marker_tests.FILES['ticket']+'/graphics-marker.v1.html'
                row['userData']=json.dumps(dict(kind='create-marker-v1',runId=RUN,nonce=marker_tests.FILES['nonce']))
        image=Image.open(BytesIO(self.sh.sdk.png)).convert('RGBA');draw=ImageDraw.Draw(image)
        bits=''.join(f'{byte:08b}' for byte in challenge(RUN,'1'*32))
        for index,bit in enumerate(bits):
            x=187+(index%32)*8;y=70+(index//32)*16;draw.rectangle((x,y,x+7,y+15),fill='white' if bit=='1' else 'black')
        stream=BytesIO();image.save(stream,format='PNG');self.sh.sdk.png=stream.getvalue();self.sh.sdk.raw_pixels=image.tobytes()
        self.sh.root=self.h.root;self.sh.lock=self.h.lock;self.sh.store=PrivateFeatureState(self.h.root/'ios-create-sample.json')
        self.ah.root=self.h.root;self.ah.lock=self.h.lock
        self.h.sdk=ClockedSDK(self.sh.sdk);self.h.native_seam=self.sh.clock
        self.product=self.ah.product;self.product.value=deepcopy(self.sh.template);self.product.value['source']['entities']=[]
        def create(role,**kwargs):
            self.product.create(role,**kwargs)
            if self.product.page()['page']['selectedIds']:self.product.selected()['position']=[0,1,-3]
        self.ah.ui.create_domain=create
        self.scripts=None
        native_read=self.h.sdk.original
        def original(name):
            value=json.loads(native_read(name));actual=self.product.read(RUN)
            if name=='create':
                value['source']=deepcopy(actual['source']);value['iosCreateStateVersion']=actual['iosCreateStateVersion']
            elif name=='domain':
                value['source']['tree']=deepcopy(actual['source']['tree'])
                if self.scripts is not None:
                    current=deepcopy(self.scripts);current.update(requestId=value['requestId'],sequence=value['sequence'],
                        requestedEpochMs=value['clockBefore']['epochMs'],capturedEpochMs=value['clockBefore']['epochMs'])
                    value['source']['scriptOriginal']=current
            elif name=='work':
                value['source']['eventSequence']=4+value['sequence']*4
                for index,row in enumerate(value['source']['roles']):
                    row['latest']=deepcopy(row['events'][-1]);row['latest'].update(sequence=5+(value['sequence']-1)*4+index,
                        callerSequence=5+(value['sequence']-1)*4+index,capturedEpochMs=value['clockBefore']['epochMs'],invokedEpochMs=value['clockBefore']['epochMs'])
            return json.dumps(value)
        self.h.sdk.original=original
    def marker(self):
        original_before,_,scripts=marker_tests.frames();actual_marker=deepcopy(next(row for row in self.sh.template['source']['entities'] if row['type']=='Web'))
        self.product.value['source']['entities']=[actual_marker];self.product.marker=actual_marker
        after=self.product.read(RUN);before=deepcopy(after);before['source']['entities']=[];before['source']['tree']['entities']=[];before['source']['tree']['totalEntities']=0
        before['sequence']=after['sequence']-1;before['requestId']='ios-'+'0'*32
        # These originals model successful prior ordinary Script loading. The
        # actual owner verifies the submitted UTF16 bytes and manager assignment.
        scripts['source']['engines'][0]['url']=marker_tests.DIRECTORY+'/script-bundle/main.js'
        raw=originals(RUN,URL,marker_tests.FILES['ticket'],marker_tests.FILES['nonce'])
        files=dict(contractVersion=1,markerFilesVersion=1,binding=deepcopy(BINDING),ownerToken='f'*64,
            **marker_tests.FILES,hashes={name:hashlib.sha256(data).hexdigest() for name,data in raw.items()})
        domain_before,domain_after=domain_pair(before,after)
        lease=PreparedCreateMarker(BINDING,RUN,URL,before=before,after=after,scripts=scripts,files=files,directory=marker_tests.DIRECTORY,
            after_epoch=EPOCH-30,domain_before=domain_before,domain_after=domain_after)
        self.scripts=scripts;return lease
    def clean_owner(self):
        source=self.h.owner();store=PrivateFeatureState(self.h.root/'ios-create-primary.json')
        journal=Journal(clock=self.h.sdk.epoch)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):journal.register('create')
        journal.activate(RUN,'1'*32);self.journal=journal
        source.phase.client.request=lambda path,**kwargs:journal.phase(RUN,kwargs['phase_nonce'])
        owner=CreatePrimary(store,self.h.lock,BINDING,RUN,source,lambda:True)
        self.assertEqual([],owner.capture()['resources'])
        lease=self.marker();self.ah.marker=lease;actions=self.ah.owner();actions.prepare()
        actions.phase=source.phase
        owner.actions=actions;owner.marker=lease
        def resolve(request):
            sample=self.sh.owner(request);sample.source=source.readers['create'];return sample
        owner.sample_resolver=resolve
        return owner,source,actions,resolve,store,lease
    def model_owner(self):
        owner,source,actions,resolve,store,lease=self.clean_owner();journal=self.journal
        for index in (0,3):
            query=self.ah.query(index);journal.activate(RUN,query['ticket'],query['verb'],query['inputs']);actions.act(query)
        image=Image.open(BytesIO(self.sh.sdk.png)).convert('RGBA');draw=ImageDraw.Draw(image)
        bits=''.join(f'{byte:08b}' for byte in challenge(RUN,query['ticket']))
        for index,bit in enumerate(bits):
            x=187+(index%32)*8;y=70+(index//32)*16;draw.rectangle((x,y,x+7,y+15),fill='white' if bit=='1' else 'black')
        stream=BytesIO();image.save(stream,format='PNG');self.sh.sdk.png=stream.getvalue();self.sh.sdk.raw_pixels=image.tobytes()
        owner.actions=actions;owner.marker=lease
        def resolve(request):
            sample=self.sh.owner(request);sample.source=source.readers['create'];return sample
        owner.sample_resolver=resolve;sample=resolve(sample_tests.REQUEST)
        return owner,source,actions,resolve,sample,store,lease
    def test_primary_actual_model_scene_fenced_png_and_native_zero_gpu_storage_form_one_fresh_original(self):
        with self.h.held():
            owner,source,actions,resolve,sample,store,lease=self.model_owner()
            value=owner.capture(sample=sample,policy=self.sh.policy)
            self.assertEqual(['model'],value['state']['objects']);self.assertEqual(1,len(value['artifacts']))
            self.assertEqual(sample.frame_owner.name,value['artifacts'][0]['name']);self.assertIn('script:create-marker',value['resources'])
            self.assertFalse(sample.state['originals']['retirement']['source']['present'])
            calls=len(self.sh.sdk.commands)
            historical=CreatePrimary(store,self.h.lock,BINDING,RUN,source,lambda:True,actions=actions,marker=lease,sample_resolver=resolve)
            self.assertEqual(owner.previous,historical.previous);self.assertEqual(calls,len(self.sh.sdk.commands))
            # The action receipt remains successful, but a replaced original
            # PNG invalidates the primary evidence and historical reconstruction.
            (self.h.root/sample.frame_owner.name).write_bytes(b'foreign PNG')
            with self.assertRaises(NativeUIError):CreatePrimary(store,self.h.lock,BINDING,RUN,source,lambda:True,actions=actions,marker=lease,sample_resolver=resolve)

    def test_missing_or_failed_current_challenge_never_becomes_model_success_and_a_new_read_keeps_old_gpu_ownership(self):
        from feature_journeys.evidence import MarkerNotReady
        with self.h.held():
            owner,source,actions,resolve,sample,store,lease=self.model_owner()
            with self.assertRaises(NativeUIError):owner.capture()
            self.assertEqual([],self.sh.sdk.commands)
            image=Image.open(BytesIO(self.sh.sdk.png)).convert('RGBA');image.paste((128,128,128,255),tuple(self.sh.policy['marker']))
            original_png,original_pixels=self.sh.sdk.png,self.sh.sdk.raw_pixels
            stream=BytesIO();image.save(stream,format='PNG');self.sh.sdk.png=stream.getvalue();self.sh.sdk.raw_pixels=image.tobytes()
            with self.assertRaises(MarkerNotReady):owner.capture(sample=sample,policy=self.sh.policy)
            self.assertEqual('failed',sample.state['phase']);old=deepcopy(owner.state['pending'])
            self.assertEqual(sample.request,old['sample']['requestId']);self.assertIsNone(old['sample']['sha256'])
            self.assertEqual(1,len(owner.state['records']));self.assertTrue((self.h.root/sample.frame_owner.name).exists())
            old_commands=deepcopy(self.sh.sdk.commands)
            self.sh.next_gpu_request();self.h.sdk.shared=self.sh.sdk
            self.sh.sdk.png,self.sh.sdk.raw_pixels=original_png,original_pixels
            owner=CreatePrimary(store,self.h.lock,BINDING,RUN,source,lambda:True,actions=actions,marker=lease,sample_resolver=resolve)
            current=resolve('ios-'+'8'*32);value=owner.capture(sample=current,policy=self.sh.policy)
            self.assertEqual(['model'],value['state']['objects']);self.assertEqual(old,owner.state['interrupted'][0])
            self.assertEqual(1,sum(row['operation']=='read' for row in old_commands));self.assertEqual(1,sum(row['operation']=='read' for row in self.sh.sdk.commands))
            self.assertTrue((self.h.root/sample.frame_owner.name).exists())

    def test_fresh_export_observations_copy_only_actual_output_and_retain_distinct_original_host_inodes(self):
        with self.h.held():
            owner,source,actions,resolve,sample,store,lease=self.model_owner()
            self.ah.file_boundary.clock=self.h.sdk.tick;actions.files.native.clock_ms=self.h.sdk.tick
            actions.files.reserve('a'*32);actions.files.stage()
            def accept(role,id_,directory,run):
                self.assertEqual('export',role);selected=self.product.selected()
                row={key:deepcopy(selected[key]) for key in ('id','name','type','modelURL','textures')};row['dimensions']=dict(zip('xyz',selected['dimensions']))
                (self.ah.file_boundary.root/'export.json').write_text(json.dumps(dict(DataVersion=0,Entities=[row])))
                self.product.dismiss(role,id_)
            self.ah.ui.accept_file=accept
            for index in (4,5):
                query=self.ah.query(index);self.journal.activate(RUN,query['ticket'],query['verb'],query['inputs']);actions.act(query)
            def file_owner(name):return CreateExportArtifact(PrivateFeatureState(self.h.root/name),self.h.lock,self.h.root,BINDING,RUN,lambda:True)
            owner.export_resolver=file_owner
            first=file_owner('ios-create-export-'+'6'*32+'-artifact.json');value=owner.capture(export_artifact=first)
            second=file_owner('ios-create-export-'+'7'*32+'-artifact.json');other=owner.capture(export_artifact=second)
            self.assertEqual(['file'],[row['kind'] for row in value['artifacts']]);self.assertEqual(['model'],value['state']['objects'])
            self.assertNotEqual(first.state['file']['inode'],second.state['file']['inode']);self.assertEqual(first.read(),second.read())
            self.assertGreater(other['capturedEpochMs'],value['capturedEpochMs']);self.assertNotEqual(value['artifacts'][0]['name'],other['artifacts'][0]['name'])
            originals=[row for row in actions.files.state['originals'] if row['query']['operation']=='observe' and row['packet']['source']['exists']]
            self.assertFalse(originals[0]['packet']['source']['files'][1]['exists']);self.assertTrue(originals[-1]['packet']['source']['files'][1]['exists'])
            self.assertEqual(first.read(),(self.ah.file_boundary.root/'export.json').read_bytes())

    def test_renderer_sdk_ignores_uuid_metadata_but_observes_actual_material_and_voxel_geometry_changes(self):
        plain=dict(id='00000000-0000-0000-0000-000000000004',type='Model',textures='')
        textured=deepcopy(plain);textured['textures']=json.dumps({'checker.png':'http://actual/checker.png'})
        for identity in (plain['id'],'ffffffff-ffff-4fff-8fff-ffffffffffff'):
            other=deepcopy(plain);other['id']=identity;other['createdEpochUs']='12345'
            self.assertEqual(subject_colors([plain]),subject_colors([other]))
            self.assertGreater(max(abs(a-b) for left,right in zip(subject_colors([other]),subject_colors([textured])) for a,b in zip(left,right)),25)
        volume=dict(type='PolyVox',voxels=dict(volume=[8,8,8],onCount=512));removed=deepcopy(volume);removed['voxels']['onCount']=448
        self.assertNotEqual(subject_colors([volume]),subject_colors([removed]));self.assertNotEqual(subject_colors([]),subject_colors([plain]))

    def test_all_21_primary_steps_join_normal_actions_actual_native_states_original_images_and_fresh_exports(self):
        from feature_journeys.scenarios import SCENARIOS
        with self.h.held():
            owner,source,actions,resolve,store,lease=self.clean_owner()
            self.ah.file_boundary.clock=self.h.sdk.tick;actions.files.native.clock_ms=self.h.sdk.tick
            original_accept=self.ah.ui.accept_file
            def accept(role,id_,directory,run):
                if role=='import':
                    original_accept(role,id_,directory,run);self.product.selected()['position']=[0,1,-3];return
                selected=self.product.selected();row={key:deepcopy(selected[key]) for key in ('id','name','type','modelURL','textures')}
                row['dimensions']=dict(zip('xyz',selected['dimensions']))
                (self.ah.file_boundary.root/'export.json').write_text(json.dumps(dict(DataVersion=0,Entities=[row])));self.product.dismiss(role,id_)
            self.ah.ui.accept_file=accept
            def file_owner(name):return CreateExportArtifact(PrivateFeatureState(self.h.root/name),self.h.lock,self.h.root,BINDING,RUN,lambda:True)
            owner.export_resolver=file_owner;images=0
            for index,step in enumerate(SCENARIOS['create']['steps']):
                query=self.ah.query(index);self.journal.activate(RUN,query['ticket'],query['verb'],query['inputs']);actions.act(query)
                wanted=set(step['evidence']);sample=None;artifact=None
                if wanted & {'image','changed'}:
                    if images:self.sh.next_gpu_request();self.h.sdk.shared=self.sh.sdk
                    images+=1
                    # An explicit renderer SDK model makes subject pixels from
                    # the actual current domain entity properties, not a step
                    # number or expected state. Background remains nonuniform.
                    image=Image.new('RGBA',(640,400),(95,95,95,255));draw=ImageDraw.Draw(image)
                    domain=[row for row in self.product.value['source']['entities'] if row['hostType']=='domain']
                    colors=subject_colors(domain)
                    for y in range(170,400,10):
                        for x in range(0,640,10):
                            draw.rectangle((x,y,x+9,y+9),fill=colors[(x//10+y//10)%2]+(255,))
                    for cell,bit in enumerate(''.join(f'{byte:08b}' for byte in challenge(RUN,query['ticket']))):
                        x=187+(cell%32)*8;y=70+(cell//32)*16;draw.rectangle((x,y,x+7,y+15),fill='white' if bit=='1' else 'black')
                    stream=BytesIO();image.save(stream,format='PNG');self.sh.sdk.png=stream.getvalue();self.sh.sdk.raw_pixels=image.tobytes()
                    sample=resolve('ios-'+format(index+100,'032x'))
                if 'file' in wanted:artifact=file_owner('ios-create-export-'+format(index+200,'032x')+'-artifact.json')
                try:value=owner.capture(sample=sample,policy=self.sh.policy,export_artifact=artifact)
                except Exception as error:
                    raise AssertionError('Primary original failed for actual '+query['verb']+' ticket '+query['ticket']) from error
                self.assertEqual(step['state'],value['state'],step['verb']);self.assertEqual(index+2,value['sequence'])
            self.assertEqual(22,len(owner.state['records']));self.assertEqual(5,len(actions.state['owned']))
            self.assertEqual(12,images)
            commands=deepcopy(self.sh.sdk.commands);counts=deepcopy(self.h.sdk.counts)
            rebuilt=CreatePrimary(store,self.h.lock,BINDING,RUN,source,lambda:True,actions=actions,marker=lease,sample_resolver=resolve,export_resolver=file_owner)
            self.assertEqual(owner.previous,rebuilt.previous);self.assertEqual(commands,self.sh.sdk.commands);self.assertEqual(counts,self.h.sdk.counts)


if __name__=='__main__':unittest.main()
