"""Normal Pico Python/HTTP composition with explicit Qt/VM/Android/OS seams.

All input changes occur in declared original control consumers. No scenario or
expected state is supplied to these producers. No HMD image is generated here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import uuid

from adapters.android.input_geometry import observed_grip_pose
from adapters.native_feature_observation import NativeFeatureObservation,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.navigation import NativeNavigationIO,PicoNavigation
from adapters.pico4.normal_scripts import PicoScriptIO
from adapters.pico4.browser_vm import PicoBrowserVm,reviewed
from adapters.pico4.world_browser_ray import PicoWorldBrowserIO,rotate
from adapters.script_journey.lock import ScriptSourceLock
from adapters.token_script_ui import TokenScriptUI
from openxr_input.adapter_session import PicoOpenXrAdapterSession
from self_tests.pico_browser_fixture import OriginalBrowserTarget,PicoTarget
from self_tests.test_token_script_ui import NativeBoundary
from self_tests.test_pico_openxr_adapter_session import FakeTransport
from self_tests.test_native_feature_observation import Boundary as FeatureBoundary
from self_tests.test_native_script_observation import code_source
from self_tests.test_native_script_membership import membership_source,manager
from self_tests import test_pico_browser_vm as original_vm


class WorldTarget(OriginalBrowserTarget):
    surface='world'
    def __init__(self,clock,client,foreign,path):
        super().__init__(clock,client,foreign,path)
        self.configuration=('owned-world',Path(path));self.selector='world-host'
        self.binding.update(sessionId=str(uuid.uuid4()),generation=0,
            targetFingerprint=hashlib.sha256((self.selector+'\0'+str(self.configuration)).encode()).hexdigest())
        self.pico_configuration=self.configuration;self.scene_url='http://controlled.invalid/scene.json'
        self.feature_root=self.path/('feature-world-web-'+hashlib.sha256(('org.overte.pico\0'+self.selector).encode()).hexdigest()[:32]);self.feature_root.mkdir(mode=0o700)
        self.lock=ScriptSourceLock(self.path/'script-sources.lock');self.qt=NativeBoundary(menu=True)
        self.ui_generation=str(uuid.uuid4());self.qt_sequence=0;self.qt_status=None
        self.qt_command=None;self.normal_inputs=[];self.fail_script_reply=False;self.ignore_ray=False;self.ignore_ime=False
        self.lost_controls=set();self.ignored_controls=set()
        self.geometry_sequence=0;self.pending_ray=None;self.entity_id=None;self.script_bytes=None;self.vm_epoch=None
        self.native=FeatureBoundary();self.native.mutate=self.native_packet
        self.runtime_sequence=0;self.runtime_raw=None;self.renderer_rows={};self.capture_stores=[]
        self.ui_path=self.path/'world-normal-ui.json'
        with patch.object(original_vm,'reviewed',side_effect=lambda:reviewed('world')):self.vm_boundary=original_vm.Boundary(self.feature_root)
        self.vm_boundary.lock=self.lock
        self.vm_boundary.objects.send_original=self.vm_boundary.objects.send
        def objects(request):
            self.vm_boundary.objects.epoch=self.clock.epoch();self.vm_boundary.objects.host=self.clock.now()
            return self.vm_boundary.objects.send_original(request)
        self.vm_boundary.objects.send=objects
        model=self
        class Transport(FakeTransport):
            def stage(inner,envelope,profile,*,before_publish=None):
                if before_publish is not None:before_publish(deepcopy(envelope))
                inner.envelopes.append(deepcopy(envelope));model.consume(envelope)
                return dict(sequence=envelope['sequence'])
        self.transport=Transport();self.session=PicoOpenXrAdapterSession(self.transport,self.selector,self.path)
        self.session.begin(self.binding['processIdentity'])
        self.adb=SimpleNamespace(read_debug_app_file=self.read,write_debug_app_file=self.write,
            epoch_milliseconds=lambda _target:self.clock.epoch(),foreground_package=lambda _target:'org.overte.pico')

    def _world_render_store(self,target):return PrivateFeatureState(self.path/('capture-default-'+target+'.json'))
    def _browser_world_render_store(self,target,role):return PrivateFeatureState(self.path/('capture-browser-'+role+'-'+target+'.json'))
    def _emote_world_render_store(self,target,role):return PrivateFeatureState(self.path/('capture-emote-'+role+'-'+target+'.json'))

    def guard(self):need(self.foreground);return True
    def require_pico_session_identity(self,target):need(target==self.selector);self.guard();return self.binding['processIdentity']
    require_controlled_debug_identity=require_pico_session_identity
    def require_same_process(self,target,identity,_reason):need(self.require_pico_session_identity(target)==identity)
    def require(self,target):need(target==self.selector)
    def _installation(self,target):
        self.require(target);return dict(schemaVersion=1,installedCandidateVerified=True,
            **{key:self.binding[key] for key in ('sourceRevision','artifactSha256')})
    def probe_retry_policy(self):return 1,0
    def pico_input_session(self,target):self.require(target);return self.session
    def _script_journey(self):return SimpleNamespace(_lock=lambda target,provided=None:self.lock)

    def _script_runtime(self,target):
        need(target==self.selector)
        io=NativeNavigationIO(self,target,self.binding['processIdentity'],lambda _op:need(False))
        navigation=PicoNavigation(io,self.ui_path,self._installation(target),self.binding['processIdentity'],self.scene_url,
            monotonic=self.clock.now,sleep=self.clock.sleep)
        normal=TokenScriptUI(PicoScriptIO(navigation),monotonic=self.clock.now,sleep=self.clock.sleep)
        return normal,self.diagnostic,deepcopy(self.binding)

    def diagnostic(self,after):
        self.native_sequence=max(self.native_sequence+1,after+1)
        return dict(schemaVersion=1,instance=self.instance,sampleSequence=self.native_sequence,sampleEpochMs=self.clock.tick(),complete=True,
            requestId=uuid.uuid4().hex,scripts=deepcopy(self.qt.rows)),self.clock.epoch()

    def ui(self):
        actual=self.qt.capture();rows=[]
        for row in actual['controls']:
            value=deepcopy(row);value['token']=str(uuid.uuid5(uuid.NAMESPACE_URL,row['id']+row.get('sourceUrl','')))
            rows.append(value)
        return dict(schemaVersion=1,bridgeId=self.binding['sessionId'],generation=self.ui_generation,processId=31,
            elapsedMs=100+round(self.clock.now()*1000),updatedEpochMs=self.clock.tick(),lastCommandSequence=self.qt_sequence,
            featureControlsVersion=1,open=actual['open'],ready=actual['ready'],controls=rows)

    def read(self,target,package,path,**_kwargs):
        need((target,package)==(self.selector,'org.overte.pico'))
        if path.endswith('navigation-ui-observation.json'):return json.dumps(self.ui())
        if path.endswith('navigation-ui-status.json'):return json.dumps(self.qt_status)
        if path.endswith('tablet-home-observation.json'):return json.dumps(self.home_raw)
        raise AssertionError(path)

    def write(self,target,package,path,raw):
        need((target,package)==(self.selector,'org.overte.pico'));call=json.loads(raw)
        if path.endswith('tablet-home-observation-command.json'):
            from self_tests.test_pico_tablet_home import original
            self.home_raw=original()|dict(commandId=call['commandId'],processId=31,capturedEpochMs=self.clock.tick(),
                sourceSequence=getattr(self,'home_seq',0)+1,elapsedMs=100+round(self.clock.now()*1000),
                tabletShown=self.qt.opened,onHomeScreen=self.qt.page=='home')
            self.home_seq=self.home_raw['sourceSequence'];return
        need(path.endswith('navigation-ui-command.json'));current=self.ui()
        row=next(item for item in current['controls'] if item['id']==call['controlId'])
        need(row['token']==call['controlToken'] and call['generation']==current['generation'] and call['sequence']==self.qt_sequence+1)
        self.qt_sequence+=1;self.normal_inputs.append(deepcopy(call))
        if call['action']=='replace':self.qt.replace(call['controlId'],call['text'])
        else:self.qt.activate(call['controlId'],source=row.get('sourceUrl'))
        if call['controlId']=='scripts.url.submit':
            self.script=self.qt.rows[-1]['url'];status,body,_receipt=self.fetch(self.script)
            need(status==200);self.script_bytes=body;self.vm_epoch=self.clock.epoch()
            self.vm_boundary.objects.row.update(registeredEpochMs=self.vm_epoch,workerCreatedEpochMs=self.vm_epoch+1)
            self.clock.sleep(.004);self.entity_id=str(uuid.uuid4());self.source=self.script.rsplit('/',1)[0]+'/index.html';self.load(self.source)
            if self.fail_script_reply:raise RuntimeError('Synthetic applied normal Script submit reply lost')
        self.qt_status=dict(schemaVersion=1,bridgeId=self.binding['sessionId'],commandId=call['commandId'],sequence=self.qt_sequence,
            performed=True,error='',processId=31,updatedEpochMs=self.clock.tick())

    def consume(self,envelope):
        op=envelope['commands'][0]['operation']
        if op.startswith('tablet.'):
            self.qt.tablet(op=='tablet.open');self.ui_generation=str(uuid.uuid4());return
        need(op=='input.primary' and self.pending_ray is not None)
        control=self.pending_ray['control']
        if not self.ignore_ray and control not in self.ignored_controls:
            if control in ('text','foreign'):self.current['focused']=True
            elif control=='bridge':
                # The modeled ordinary button hit transfers DOM focus away
                # from the editor before its real page event handler runs.
                self.current['focused']=False;self.input(dict(control='bridge'))
            elif control in ('second','back'):
                self.input(dict(control=control))
            else:raise AssertionError(control)
        if control in self.lost_controls:raise RuntimeError('Applied original ray status lost: '+control)

    def _browser_originals(self,target,*,source_lock,tablet=False,read_only=True):
        need(target==self.selector and source_lock is self.lock and tablet is False)
        return PicoWorldBrowserIO(self.send,lambda:self.raw,self.clock.epoch,self.guard,31,source_lock=self.lock,read_only=read_only,
            monotonic=self.clock.now,sleep=self.clock.sleep)

    def geometry(self,call):
        self.geometry_sequence+=1;editing=call['control'] in ('text','foreign');text=self.current['text'];units=len(text.encode('utf-16le'))//2
        return dict(webGeometryVersion=1,requestId=call['commandId'],instance=self.current['instance'],sequence=self.geometry_sequence,
            capturedEpochMs=self.clock.tick(),document=dict(runId=self.run,href=self.current['url'],responseId=self.current['response'],readyState='complete'),
            control=call['control'],editor=dict(focused=self.current['focused'],text=text if editing else None,cursor=units if editing else None,anchor=units if editing else None),
            viewport=dict(width=int(1.8*39.3701*40),height=int(2.2*39.3701*40),scale=1,offsetLeft=0,offsetTop=0),rect=dict(x=80,y=60,width=160,height=80),
            center=dict(x=160,y=100),hit=True,enabled=True,connected=True)

    def send(self,call):
        if call['operation'] not in ('measure-ray','commit-text'):return super().send(call)
        self.request=deepcopy(call);self.sequence+=1;geometry=self.geometry(call);view=self.dom_packet(call['commandId'])['source']['nativeView']
        if call['operation']=='measure-ray':
            factor=39.3701*40;dimensions=[1.8,2.2,.01];size=[int(x*factor) for x in dimensions[:2]]
            point=[160,100];position=[0,1.4,-2.5]
            local=[point[0]/factor-dimensions[0]/2,dimensions[1]/2-point[1]/factor,0]
            ray=dict(worldWebRayVersion=1,capturedEpochMs=self.clock.epoch(),sourceIdentity=view['sourceIdentity'],entityId=self.entity_id,
                entityName='OVERTE_PARITY_WEB_REFERENCE',entityType='Web',hostType='local',sourceUrl=self.source,visible=True,ignorePickIntersection=False,
                position=position,rotation=[0,0,0,1],dimensions=dimensions,registrationPoint=[.5,.5,.5],dpi=40,scenePoint=point,
                itemQuad=[[0,0],[size[0],0],size,[0,size[1]]],surfaceSize=size,worldPoint=[position[i]+local[i] for i in range(3)],
                sensorToWorld=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1],headPosition=[0,1.6,0])
            self.pending_ray=deepcopy(call);source=dict(nativeView={key:view[key] for key in ('handle','creation','grant','page','url')},
                geometryRaw=json.dumps(json.dumps(geometry)),worldRay=ray);version=3
        else:
            need(self.current['focused']);text=self.current['text'];units=len(text.encode('utf-16le'))//2
            source=dict(delivered=True,focusRaw=json.dumps(json.dumps(geometry)),nativeBeforeIME=dict(text=text,cursor=units,anchor=units,
                absoluteCursor=units,kind='text',sensitive=False,focused=True,enabled=True),imeEpochMs=self.clock.epoch(),
                nativeView={key:view[key] for key in ('handle','creation','grant','page','url')});version=4
            if not self.ignore_ime:self.current['text']=call['text']
        self.raw=json.dumps(dict(picoBrowserVersion=version,commandId=call['commandId'],runId=self.run,ownerToken=self.owner,
            instance=self.instance,sequence=self.sequence,processId=31,capturedEpochMs=self.clock.tick(),status='ready',source=source))

    def dom_packet(self,request):
        packet=super().dom_packet(request);packet['source']['nativeView']['sourceIdentity']='web-entity:'+self.entity_id
        return packet

    def native_packet(self,value):
        epoch=self.clock.tick();value.update(processId=31,instance=self.instance,requestedEpochMs=epoch,capturedEpochMs=epoch,lifecycle=deepcopy(self.lifecycle))
        value['animationFence']['requestedEpochMs']=epoch
    def _native_feature_observer(self,target):
        need(target==self.selector)
        return NativeFeatureObservation(self.native.send,self.native.original,self.clock.epoch,self.guard,31,monotonic=self.clock.now,sleep=self.clock.sleep)

    def _world_browser_vm(self,target,run,url,script_url,*,role,source_lock,http):
        need(target==self.selector and source_lock is self.lock and script_url==self.script)
        b=self.vm_boundary;pins=reviewed('world')[0]
        def compiled(value):
            epoch=self.clock.tick();value.update(instance=self.instance,processId=31,requestedEpochMs=epoch,capturedEpochMs=epoch)
            code_source(value,self.script_bytes.decode(),submitted=self.vm_epoch+2)
            membership_source(value,[manager(url=self.script,epoch=self.vm_epoch+1)],1)
            value['source'].update(effectSourceVersion=1,effects=dict(complete=True,scanRadiusMeters=64,scannedEntities=0,entities=[],absentIds=[]),
                loadSourceVersion=1,loads=dict(complete=True,instance='d'*32,sequence=0,events=[]),compiledSourceVersion=1)
            for engine in value['source']['engines']:
                engine.update(url=self.script);engine['required'].update(sequence=0,modules=[])
                engine['compiled']=dict(compiledSourcesVersion=1,complete=True,compilations=[dict(scriptId=17,resourceName=self.script,
                    **pins,compiledEpochMs=self.vm_epoch+3)])
        b.script.mutate=compiled;scripts=b.script.reader();scripts.clock_ms=self.clock.epoch;scripts.monotonic=self.clock.now
        b.objects.fault=lambda packet:packet.update(instance=self.instance)
        reader=b.objects.reader();reader.clock_ms=self.clock.epoch;reader.monotonic=self.clock.now
        return PicoBrowserVm(run,url,script_url,role,self.binding,scripts,reader,
            PrivateFeatureState(self.feature_root/('pico-world-web-'+role+'-vm.json')),self.lock,http,surface='world')

    _web_runtime_observer=PicoTarget._web_runtime_observer
