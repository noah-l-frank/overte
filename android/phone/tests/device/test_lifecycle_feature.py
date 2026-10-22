"""Complete host composition at explicit synthetic OS/native/renderer seams.

Normal SDK inputs, actual closed native transports, immutable source files,
private PNG bytes and the unchanged common journey execute. Original Android
Qt/IME/kernel/physics callbacks remain synthetic here; no device acceptance.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import nullcontext
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone'),str(Path(__file__).resolve().parent)]
from PIL import Image,ImageDraw
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.pending_commit_owner import NativePendingCommitOwner
from feature_journeys.engine import Journey
from feature_journeys.fixtures import context,marker_bytes
from feature_journeys.phase_fixture import PhaseFixtureReader,PhasePending,PhaseRetired
from feature_journeys.scenarios import VERSION
from feature_journeys.witness import Journal,Client
from feature_journeys.evidence import read_private_artifact
from overte_phone_lifecycle_editor import PhoneLifecycleEditorSource
from overte_phone_lifecycle_world import PhoneLifecycleWorldSource
from overte_phone_lifecycle_feature import PhoneLifecycleInputFeature
from overte_phone_navigation_marker import layout
from overte_phone_script_history import unpack
from self_tests.test_pending_commit_owner import Boundary as PendingBoundary
from self_tests.test_native_feature_observation import Boundary as NativeBoundary
from self_tests.test_phone_navigation import NativePhone
from test_lifecycle_editor import Boundary as EditorBoundary
from test_lifecycle_world import Boundary as WorldBoundary
from test_navigation_feature import Composite as RenderComposite,POLICY,RUN,URL
from self_tests.test_native_phone_scene_loads import Boundary as SceneBoundary
from adapters.native_phone_scene_loads import NativePhoneSceneLoads,resource_hash


class SDK(NativePhone):
    def __init__(self,owner):
        super().__init__();self.owner=owner
        for name in ('CREATE','CHAT','app.scripts','NativeCreateTab_0','scriptFromUrl'):
            self.references[name]='n'+str(len(self.references));self.by_reference[self.references[name]]=name
        self.ui.sleep=owner.sleep;self.ui.timeout=1
    def visible(self,name):
        if name=='nav.home':return self.screen is not None
        if name in ('CREATE','CHAT','app.scripts'):return self.screen=='home'
        if name=='NativeCreateTab_0':return self.screen=='create'
        if name=='scriptFromUrl':return self.screen=='scripts'
        return super().visible(name)
    def call(self,method,path,body=None):
        if method=='POST' and path.endswith('/click'):
            name=self.by_reference[path.split('/element/',1)[1].split('/')[0]]
            if name=='tablet.open':self.screen='home';return None
            if name=='nav.home':self.owner.hide();self.screen='home';return None
            if name in ('CREATE','CHAT','app.scripts'):
                self.screen={'CREATE':'create','CHAT':'chat','app.scripts':'scripts'}[name];self.owner.open(self.screen);return None
            if name=='NativeCreateTab_0':return None
        return super().call(method,path,body)


class Target(RenderComposite):
    def __init__(self,root):
        super().__init__(root);self.sdk=SDK(self);self.foreground=True;self.editor=EditorBoundary();self.world=WorldBoundary();self.pending=PendingBoundary()
        self.editor.body.update(contexts=[],current=dict(status='none'));self.editor.body['canonicalSources']['scripts']=self.pending.cached['canonicalComponentUrl'] if self.pending.cached else 'qrc:/qml/hifi/dialogs/TabletRunningScripts.qml'
        self.editor.sequence=self.world.sequence=0;self.event=None;self.inputs=[];self.native_sequence=0;self.backgrounds=0
        self.journal=Journal(self.epoch)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.journal.register('lifecycle-input')
        self.reader.run=self.actor.run=RUN;self.reader.area=self.actor.area='lifecycle-input';self.activate(uuid.uuid4().hex)
        self.editor.body['instance']='4'*32;self.world.source['instance']='5'*32;self.world.motion['instance']='6'*32
        self.key_press_count=0;self.input_fault='';self.last_move=0
        self.loads=SceneBoundary();self.loads.rows[0]['resourceSha256']=resource_hash(self.sdk.current)
    def epoch(self):return 100000+round(self.sdk.clock*1000)
    def flow(self,role='primary'):
        return PhoneLifecycleInputFeature(self,'controlled',PhaseFixtureReader(self.reader if role=='primary' else self.actor,RUN,'lifecycle-input',epoch_ms=self.epoch,monotonic=lambda:self.sdk.clock),
            self.root,POLICY,role=role,**self.options())
    def activate(self,ticket,verb='baseline',inputs=None):self.journal.activate(RUN,ticket,verb,inputs or {})
    def request(self,role,path,value=None,method=None,**kwargs):
        if path.endswith('/phase'):return self.journal.phase(RUN,kwargs['phase_nonce'])
        if path.endswith('/samples'):
            assert role=='actor';return self.journal.publish(RUN,value)
        if path.endswith('/'+RUN):return self.journal.snapshot(RUN)
        raise AssertionError(path)
    def hide(self):
        current=self.editor.body['current']
        if current['status']=='ready':
            for row in self.editor.body['contexts']:
                if row['token']==current['token']:row.update(active=False,alive=False,attached=False,retiredEpochMs=self.epoch())
        self.editor.body.update(current=dict(status='none'),osKeyboardVisible=False)
    def open(self,editor):
        self.hide();token=uuid.uuid4().hex;field=uuid.uuid4().hex;url=self.editor.body['canonicalSources'][editor]
        row=dict(editor=editor,token=token,fieldToken=field,sourceUrl=url,createdEpochMs=self.epoch(),retiredEpochMs=0,alive=True,attached=True,active=True)
        self.editor.body['contexts'].append(row);self.editor.body['current']=dict(status='ready',editor=editor,token=token,fieldToken=field,sourceUrl=url,text='',focused=False,frame=[0,10,200,40])
        if editor=='scripts':self.pending.token=field
    def _lifecycle_editor(self,_selector,*,read_only=True,intent=None):
        state={}
        def send(request):
            self.editor.sequence+=1;epoch=self.epoch();body=self.editor.body;current=body['current'];performed=False
            if request['action'].endswith('-input'):
                assert not read_only and intent is not None;self.inputs.append(deepcopy(request));performed=True
                assert current['fieldToken']==request['fieldToken']
                if request['operation']=='focus' and self.input_fault!='ignore-focus':current['focused']=True;body['osKeyboardVisible']=True
                if request['operation']=='type' and self.input_fault!='ignore-type':current['text']=context(RUN)[dict(create='unicode',chat='reply',scripts='retry')[current['editor']]]
            body.update(sequence=self.editor.sequence,capturedEpochMs=epoch)
            state['value']=dict(schemaVersion=1,requestId=request['commandId'],runId=RUN,instance=self.birth,sequence=self.editor.sequence,processId=self.pid,
                requestedEpochMs=epoch,capturedEpochMs=epoch,performed=performed,source=deepcopy(body))
        return PhoneLifecycleEditorSource(send,lambda:json.dumps(state['value']),self.epoch,self.guard,self.pid,intent=intent,**self.options())
    def _lifecycle_world(self,_selector,*,read_only=True,intent=None):
        state={}
        def send(request):
            self.world.sequence+=1;epoch=self.epoch();source=self.world.source;motion=self.world.motion;source['performed']=False
            if request['operation']=='hold':
                assert not read_only and intent is not None;self.inputs.append(deepcopy(request));self.key_press_count+=1
                row=dict(gestureId=uuid.uuid4().hex,runId=RUN,commandId=request['commandId'],createdEpochMs=epoch,pressEpochMs=epoch,releaseEpochMs=0,releaseReason='',pressObserved=self.input_fault!='ignore-world',releaseObserved=False)
                if not row['pressObserved']:row['pressEpochMs']=0
                source['gestures'].append(row);source.update(pending=True,pendingRun=RUN,pendingGesture=row['gestureId'],timerActive=True,elapsedMs=0,performed=True)
                if self.editor.body['current']['status']=='none' and self.input_fault!='ignore-world':motion['effectiveDrive']=[0,0,1];motion['rawDrive']=[0,0,1];motion['upPressed']=1;self.sdk.position['z']-=.8
            elif request['operation']=='release':
                assert not read_only and intent is not None;self.inputs.append(deepcopy(request));source['performed']=True
                if self.input_fault!='ignore-release':
                    row=next(row for row in source['gestures'] if row['gestureId']==request['gestureId']);row.update(releaseObserved=True,releaseEpochMs=epoch,releaseReason='explicit')
                    source.update(pending=False,pendingRun='',pendingGesture='',timerActive=False,elapsedMs=0);motion.update(upPressed=0,effectiveDrive=[0,0,0],rawDrive=[0,0,0])
            source.update(sequence=self.world.sequence,commandId=request['commandId'],runId=RUN,capturedEpochMs=epoch)
            if source['pending']:source['elapsedMs']=min(9999,epoch-source['gestures'][-1]['createdEpochMs'])
            motion.update(sequence=self.world.sequence,capturedEpochMs=epoch,feetPosition=[self.sdk.position[k] for k in 'xyz'])
            state['value']=dict(schemaVersion=1,requestId=request['commandId'],runId=RUN,instance=self.birth,sequence=self.world.sequence,processId=self.pid,requestedEpochMs=epoch,capturedEpochMs=epoch,source=deepcopy(source),motion=deepcopy(motion))
        return PhoneLifecycleWorldSource(send,lambda:json.dumps(state['value']),self.epoch,self.guard,self.pid,intent=intent,**self.options())
    def _pending_owner(self,_selector,intent=None,*,read_only=False):
        def send(request):
            current=self.editor.body['current'];self.pending.clock=self.sdk.clock+80
            self.pending.alive=self.running;self.pending.token=current['fieldToken'] if current.get('editor')=='scripts' else self.pending.token
            self.pending.text=current.get('text','');self.pending.focused=current.get('focused',False)
            self.pending.send(request)
            if request['operation']!='observe':assert not read_only;self.inputs.append(deepcopy(request))
        def original():
            with patch('self_tests.test_pending_commit_owner.RUN',RUN):value=json.loads(self.pending.original())
            value['processId']=self.pid
            if self.editor.body['current'].get('editor')!='scripts':value['current']=dict(status='none')
            if value['commit']:value['commit']['observation']['processId']=self.pid
            return json.dumps(value)
        return NativePendingCommitOwner(send,original,self.epoch,self.guard,self.pid,intent=intent,**self.options())
    def _native_feature_observer(self,_selector,*,read_only=False):
        source=NativeBoundary()
        def send(request):
            source.send(request);self.native_sequence+=1
            source.sample.update(instance=self.birth,sequence=self.native_sequence,processId=self.pid,requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch(),lifecycle=dict(backgrounds=self.backgrounds,activations=self.activations,launches=self.launches))
            source.sample['animationFence']['requestedEpochMs']=self.epoch()
        return NativeFeatureObservation(send,source.original,self.epoch,self.guard,self.pid,**self.options())
    def _scene_load_observer(self,_selector,*,read_only=True):
        def send(request):self.loads.epoch=self.epoch();self.loads.send(request)
        return NativePhoneSceneLoads(send,self.loads.original,self.epoch,self.guard,self.pid,**self.options())
    def _navigation_probe(self,_selector,after=0):
        self.sdk.sequence=max(self.sdk.sequence,after);self.sdk.frame+=1;value=self.sdk.observe();value['sampleEpochMs']=self.epoch();value['render']['lastFrameEpochMs']=self.epoch();return value
    def _graphics_lifecycle_status(self,_selector,binding):return dict(foreground=self.foreground,process=dict(running=self.running,identity=self.binding['processIdentity']),binding=deepcopy(binding))
    def existing_session(self,_selector):return self,'owned-session',{}
    def execute(self,_session,operation,values):
        assert operation=='mobile: pressKey' and values==dict(keycode=4);self.inputs.append(dict(back=True))
        if self.input_fault!='ignore-back':self.hide();self.sdk.screen='home'
    def invoke(self,_selector,operation,values):
        if operation=='lifecycle.background':self.foreground=False;self.backgrounds+=1
        elif operation=='app.launch':
            self.foreground=True;self.activations+=1
            if self.input_fault!='ignore-background-focus':self.editor.body['current']['focused']=False;self.editor.body['osKeyboardVisible']=False
        elif operation=='scene.load':
            self.sdk.position=dict(x=0,y=0,z=4);self.loads.generation+=1;row=deepcopy(self.loads.rows[0]);row.update(id=uuid.uuid4().hex,generation=self.loads.generation,startedEpochMs=self.epoch(),updatedEpochMs=self.epoch(),releasedEpochMs=self.epoch());self.loads.rows.append(row)
        else:raise AssertionError(operation)
        return {'performed':True}
    def _navigation_marker_input(self,selector,request):
        value=super()._navigation_marker_input(selector,request)
        if request['operation']=='prepare':
            original=layout(self.marker)['marker'];self.marker['entities'][0].update(position=original['position'],dimensions=original['dimensions'],rotation=original['rotation'])
        return value
    def avatar(self):
        value=super().avatar();value['view']['position']=[0,1.6,self.sdk.position['z']+2];return value
    def send(self,key,request):
        # Existing actual renderer/binary/receipt transports, under this area's
        # persisted original acquisition intent instead of Navigation's state.
        assert key=='capture';self.counters[key]+=1;self.storage.present=True;self.paint()
        packet=deepcopy(self.scene.capture);packet.update(requestId=request['commandId'],instance=self.birth,processId=self.pid,sequence=self.counters[key],requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch())
        source=packet['source'];source.update(acquisitionSequence=self.counters[key],recordedEpochMs=self.epoch(),startedEpochMs=self.epoch(),capturedEpochMs=self.epoch(),sourceExtent=[640,480],sourceViewport=[0,0,640,480],targetExtent=[640,480])
        source['image'].update(name='world-render-image-'+request['commandId']+'.png',bytes=len(self.storage.raw),sha256=hashlib.sha256(self.storage.raw).hexdigest(),pixelSha256=self.pixel_sha,width=640,height=480)
        source['renderTrace'].update(frameId=uuid.uuid4().hex,recordedEpochMs=self.epoch(),begunEpochMs=self.epoch(),completedEpochMs=self.epoch(),recordedView=self.avatar()['view']);self.values[key]=packet
    def paint(self):
        image=Image.new('RGBA',(640,480),(128,128,128,255));image.paste(Image.open(io.BytesIO(marker_bytes(RUN,self.journal.active(RUN)['ticket']))).convert('RGBA'),(20,20));draw=ImageDraw.Draw(image)
        for y in range(100,420,16):
            for x in range(200,600,16):draw.rectangle((x,y,x+15,y+15),fill=((240,80,20,255) if self.sdk.position['z']<3.9 else (20,180,240,255)) if (x//16+y//16)%2 else (20,20,20,255))
        output=io.BytesIO();image.save(output,format='PNG');self.storage.raw=output.getvalue();self.pixel_sha=hashlib.sha256(image.tobytes()).hexdigest()
    def sleep(self,value):
        self.sdk.clock+=value
        if self.actor_enabled and not self.actor_busy and not self.actor_retired:
            import fcntl,os
            lock=os.open(self.root/'phone-script-sources.lock',os.O_RDWR|os.O_CREAT,0o600)
            try:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:return
                fcntl.flock(lock,fcntl.LOCK_UN)
            finally:os.close(lock)
            self.actor_busy=True
            try:self.flow('actor').publish()
            except PhaseRetired:self.actor_retired=True
            except PhasePending:pass
            finally:self.actor_busy=False
    def run(self,invoke=None):
        self.actor_enabled=True;reports=[]
        journey=Journey('lifecycle-input',RUN,URL+'/runs/'+RUN+'/',invoke=invoke or (lambda operation,values:getattr(self.flow(),operation.rsplit('.',1)[1])(values)),
            witness=lambda *_args:self.journal.snapshot(RUN),activate=lambda ticket,verb='baseline',inputs=None:self.activate(ticket,verb,inputs),
            read_artifact=lambda name:read_private_artifact(self.root,name),image_policy={'screen':POLICY['imagePolicy']},continuity=lambda *_:None,
            monotonic=lambda:self.sdk.clock,epoch_ms=self.epoch,sleep=self.sleep,report=reports.append)
        self.sleep(.01);return journey.execute(),reports


class LifecycleFeatureTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='phone-lifecycle-');self.addCleanup(self.tmp.cleanup);self.model=Target(Path(self.tmp.name))
        network=patch('feature_journeys.witness.build_opener',side_effect=AssertionError('Synthetic target must never use network transport'))
        network.start();self.addCleanup(network.stop)
    def registered(self):
        from test_account_fixture_launch import AccountFixtureLaunchTests
        fixture=AccountFixtureLaunchTests();fixture.setUp();self.addCleanup(fixture.doCleanups);f=fixture.f
        f.target['controls']=dict(move=dict(forward=dict(start=[.1,.7],end=[.1,.4],mode='hold')))
        f.adapter.read_session('test-only-appium')['targetFingerprint']=f.adapter.snapshot_fingerprint(f.target)
        return f
    def configuration(self):
        policy=self.model.root/'lifecycle-policy.json';access=self.model.root/'adapter-fixture-access.json'
        for path,value in ((policy,POLICY),(access,dict(fixtureAdapterAccessVersion=1,fixtureUrl=URL,adapterToken='d'*64))):
            store=PrivateFeatureState(path)
            if store.read() is None:store.write(value,None)
        return dict(OVERTE_PHONE_FEATURE_LIFECYCLE_INPUT='1',OVERTE_ANDROID_E2E_TEXT_INPUT='1',OVERTE_E2E_VOICE_TESTS='1',
            OVERTE_E2E_FEATURE_FIXTURE_URL=URL,OVERTE_PHONE_FEATURE_FIXTURE_CONFIG=str(access),
            OVERTE_PHONE_LIFECYCLE_INPUT_IMAGE_POLICY=str(policy),OVERTE_DEVICE_ARTIFACT_DIR=str(self.model.root))
    def test_default_off_and_missing_mandatory_foundations_or_external_policy_stay_red(self):
        f=self.registered();config=self.configuration()
        with patch.dict(os.environ,config|dict(OVERTE_PHONE_FEATURE_LIFECYCLE_INPUT='0')),patch.object(f.adapter,'_lifecycle_input_feature') as factory:
            self.assertFalse(any(op.startswith('feature.lifecycle-input.') for op in f.adapter.advertised_capabilities(f.target)))
            with self.assertRaises((ValueError,RuntimeError)):f.adapter.invoke('test-only-appium','feature.lifecycle-input.observe',dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
            factory.assert_not_called()
        for edit in (dict(OVERTE_PHONE_FEATURE_LIFECYCLE_INPUT='true'),dict(OVERTE_ANDROID_E2E_TEXT_INPUT='0'),dict(OVERTE_E2E_VOICE_TESTS='0'),
            dict(OVERTE_PHONE_LIFECYCLE_INPUT_IMAGE_POLICY=''),dict(OVERTE_PHONE_FEATURE_FIXTURE_CONFIG=''),dict(OVERTE_DEVICE_ARTIFACT_DIR='')):
            with self.subTest(edit=edit),patch.dict(os.environ,config|edit),self.assertRaises((ValueError,RuntimeError)):f.adapter.advertised_capabilities(f.target)
        with patch.dict(os.environ,config):
            values=f.adapter.advertised_capabilities(f.target)
            self.assertTrue({'feature.lifecycle-input.'+kind for kind in ('act','observe','cleanup')}<=set(values))
            catalog=json.loads((ROOT/'tests/device/catalog.json').read_text())
            for row in catalog['modules']:
                if row['id'] in ('text-input','tablet-input-isolation','lifecycle-under-load'):self.assertTrue(set(row['requires'])<=set(values))
            f.target['controls']={}
            with self.assertRaises((ValueError,RuntimeError)):f.adapter.advertised_capabilities(f.target)
    def test_actor_current_config_is_separate_and_pending_factory_is_actually_readonly(self):
        from script_observer import configuration
        path=self.model.root/'actor.json';store=PrivateFeatureState(path)
        value=dict(featureObserverVersion=7,area='lifecycle-input',target='controlled',candidateArguments=[],fixtureUrl=URL,actorToken='f'*64,durationSeconds=60)
        store.write(value,None);self.assertEqual(value,configuration(path))
        for version in (2,3,4,5,6):
            edited=value|dict(featureObserverVersion=version);store.write(edited,store.read())
            with self.assertRaises(RuntimeError):configuration(path)
        f=self.registered();source,_=f.pending_owner_boundaries(intent=False)
        owner=f.adapter._pending_owner('test-only-appium',read_only=True);owner.read('a'*32)
        before=len(source.commands)
        with self.assertRaises(RuntimeError):owner.focus('a'*32)
        self.assertEqual(before+1,len(source.commands));self.assertTrue(all(row['operation']=='observe' for row in source.commands))
        with self.assertRaises((ValueError,RuntimeError)):f.adapter._pending_owner('test-only-appium',source.intents.append,read_only=True)
    def test_complete_common_journey_and_independent_actor_and_v18_closed_retirement(self):
        model=self.model;f=self.registered()
        with patch.dict(os.environ,self.configuration()),patch.object(f.adapter,'_lifecycle_input_feature',side_effect=lambda *_a,**_k:model.flow()),\
                patch.object(f.adapter,'_feature_fixture_client',return_value=model.reader),\
                patch('overte_phone_feature_dispatch.PhaseFixtureReader',side_effect=lambda client,run,area:PhaseFixtureReader(client,run,area,epoch_ms=model.epoch,monotonic=lambda:model.sdk.clock)):
            phases,reports=model.run(lambda operation,values:f.adapter.invoke('test-only-appium',operation,values))
        self.assertTrue(reports[0]['sequenceCompleted']);self.assertFalse(reports[0]['deviceAcceptance'])
        self.assertGreater(len(phases),15);self.assertEqual(2,model.key_press_count);self.assertEqual([0,0,4],[model.sdk.position[k] for k in 'xyz'])
        model.journal.close(RUN);model.sleep(.25);self.assertTrue(model.actor_retired)
        # Freeze a real durable retirement plan, then interrupt before its NEW
        # original absence acquisition. A saved plan cannot hide late work.
        flow=model.flow()
        with patch.object(flow,'fresh_retired',side_effect=NativeUIError('synthetic interruption')):
            with self.assertRaises(NativeUIError):flow.finalize()
        plan=flow.retirement_store.read();self.assertIsNotNone(plan)
        for fault in ('primary-quiet','actor-close','late-browser','late-context','late-key','native-reset','scene-reset','late-scene-callback','missing-png','foreign-same-bytes-inode'):
            original_plan=deepcopy(plan);backup=None;path=None
            if fault in ('primary-quiet','actor-close'):
                body=unpack(plan['payload'])[0]
                if fault=='primary-quiet':body['roles']['primary']['quiet']['complete']=False
                else:body['roles']['actor']['closed']=None
                from overte_phone_script_history import pack
                edited=deepcopy(plan);edited['payload']=pack([body]);flow.retirement_store.write(edited,plan)
            elif fault=='late-browser':model.web.revoked=False
            elif fault=='late-context':
                old=deepcopy(model.editor.body['contexts'][-1]);old.update(token=uuid.uuid4().hex,fieldToken=uuid.uuid4().hex);model.editor.body['contexts'].append(old)
            elif fault=='late-key':
                old=deepcopy(model.world.source['gestures'][-1]);old.update(gestureId=uuid.uuid4().hex,commandId=uuid.uuid4().hex);model.world.source['gestures'].append(old)
            elif fault=='native-reset':backup=model.native_sequence;model.native_sequence=0
            elif fault=='scene-reset':backup=model.loads.sequence;model.loads.sequence=0
            elif fault=='late-scene-callback':
                old=deepcopy(model.loads.rows[-1]);old.update(id=uuid.uuid4().hex,kind='delivery',generation=0,result=None,bytes=None,phase='running',pending=True,releasedEpochMs=None);model.loads.rows.append(old)
            else:
                path=next(model.root.glob('navigation-*.png'));backup=path.with_suffix('.owned-backup');path.rename(backup)
                if fault=='foreign-same-bytes-inode':path.write_bytes(backup.read_bytes());path.chmod(0o600)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):model.flow().finalize()
            self.assertIsNotNone(model.flow().store.read());self.assertIsNotNone(model.flow().retirement_store.read())
            if fault in ('primary-quiet','actor-close'):flow.retirement_store.write(original_plan,flow.retirement_store.read())
            elif fault=='late-browser':model.web.revoked=True
            elif fault=='late-context':model.editor.body['contexts'].pop()
            elif fault=='late-key':model.world.source['gestures'].pop()
            elif fault=='native-reset':model.native_sequence=backup
            elif fault=='scene-reset':model.loads.sequence=backup
            elif fault=='late-scene-callback':model.loads.rows.pop()
            else:
                if path.exists():path.unlink()
                backup.rename(path)
        model.flow().finalize()
        with patch.dict(os.environ,self.configuration()),patch.object(f.adapter,'_feature_fixture_client',return_value=model.reader),\
                patch.object(f.adapter,'_lifecycle_input_feature',side_effect=lambda *_a,**_k:model.flow()),\
                patch('overte_phone_feature_dispatch.PhaseFixtureReader',side_effect=lambda client,run,area:PhaseFixtureReader(client,run,area,epoch_ms=model.epoch,monotonic=lambda:model.sdk.clock)):
            self.assertEqual({'performed':True},f.adapter.invoke('test-only-appium','feature.lifecycle-input.cleanup',dict(contractVersion=VERSION,runId=RUN)))
        self.assertIsNone(model.flow().store.read());self.assertIsNone(model.flow().role_path('actor').read());self.assertFalse(list(model.receipt_root.iterdir()))
        self.assertTrue((model.root/('lifecycle-retired-'+RUN+'.json')).is_file())

if __name__=='__main__':unittest.main()
