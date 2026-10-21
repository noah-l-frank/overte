"""Ordinary iOS scene/camera ownership with real loopback resource responses.

Qt/UIKit, native entity/address/lease sources and the SDK boundary are synthetic.
No build, real app, device or simulator is invoked.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import json
from pathlib import Path
import secrets
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs,urlsplit
from urllib.request import urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adapters.native_feature_observation import need
from adapters.native_scene_loads import resource_hash
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI,NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from adapters.token_graphics_ui import TokenGraphicsUI
from feature_journeys import witness
from feature_journeys.server import make_server
from feature_journeys.graphics_resources import GraphicsResources
from feature_journeys.graphics_fixture import subject_ids
from ios.adapters import normal_input
from ios.adapters import feature_observation
from ios.adapters.graphics_scene import IOSGraphicsScene
from ios.adapters.graphics_fixture import GraphicsFixtureReader,GraphicsPhasePending,GraphicsRunRetired
from ios.adapters.graphics_source import IOSGraphicsSource
from ios.adapters.graphics_surface import IOSGraphicsSurface
from ios.adapters.normal_scripts import IOSScriptIO
from ios.self_tests.test_ios_graphics_surface import Boundary as InputSDK
from self_tests.test_completed_frame_lease import BINDING
from self_tests.test_native_scene_loads import Boundary as LoadsSDK,row as load_row
from self_tests.test_native_feature_observation import Boundary as CoreSDK

RUN='b'*32
TICKET='c'*32
BASELINE=json.dumps(dict(DataVersion=3,Entities=[])).encode()


def entity_rows(document):
    # Native SDK model reads the real delivered entity document. It does not
    # consume an adapter's expected state or copy the normalized output.
    output=[]
    for item in document['Entities']:
        haze=item.get('haze',{});color=item.get('color',dict(red=0,green=0,blue=0));hc=haze.get('hazeColor',dict(red=128,green=154,blue=179))
        output.append(dict(id=item['id'].strip('{}'),name=item['name'],type=item['type'],hostType='local',
            position=[item['position'][a] for a in 'xyz'],rotation=[item['rotation'][a] for a in 'xyzw'],
            dimensions=[item['dimensions'][a] for a in 'xyz'],color=[color[a] for a in ('red','green','blue')],visible=True,
            mirrorMode=item.get('mirrorMode','none'),hazeMode=2 if item['type']=='Zone' else 0,sourceUrl=item.get('sourceUrl',''),
            lastEditedEpochUs=20000000,haze=dict(range=haze.get('hazeRange',1000),color=[hc[a] for a in ('red','green','blue')],
                altitudeEffect=haze.get('hazeAltitudeEffect',False),glare=haze.get('hazeEnableGlare',False),backgroundBlend=haze.get('hazeBackgroundBlend',0))))
    return output


class SDK(InputSDK):
    def __init__(self):
        super().__init__();self.feet=[4.,0.,2.];self.orientation=[0,0,0,1];self.scale=1.25;self.boom=3.25
        self.scene_rows=[];self.fetched=[];self.loads=LoadsSDK();self.loads.rows=[]
        self.subject.source.update(subjectVersion=3,avatarPose={},cameraOrbit={})
        self.core=CoreSDK();self.core.mutate=self.core_packet;self.core_fault=''
        self.foreground=True;self.native_lifecycle=dict(backgrounds=0,activations=1,launches=1)
        self.target.update(platform='ios',physical=True,probe=dict(kind='ios-documents'))
    def host_epoch(self):return 1700000000000+round(self.clock*1000)
    def epoch(self):return self.host_epoch()+86400000
    def observed(self):return super().observed()|dict(fileControlsVersion=1)
    def process(self):return super().process()|dict(foreground=self.foreground)
    def initial(self,url):
        self.url=url;self.loads.rows=[load_row(generation=1,resourceSha256=resource_hash(url),
            startedEpochMs=self.epoch(),updatedEpochMs=self.epoch(),releasedEpochMs=self.epoch(),bytes=len(BASELINE))]
    def subject_packet(self,value):
        super().subject_packet(value)
        source=value['source'];source['subjectVersion']=3
        source['entities']=deepcopy(self.scene_rows);source['absentIds']=list(subject_ids(RUN).values())
        present={row['id'] for row in self.scene_rows};source['absentIds']=[item for item in source['absentIds'] if item not in present]
        source['avatarPose']=dict(feetPosition=deepcopy(self.feet),orientation=deepcopy(self.orientation),modelScale=self.scale)
        source['cameraOrbit']=dict(lookAtRotation=deepcopy(self.orientation),boomLength=self.boom,minimumBoomLength=0.,defaultBoomLength=3.25)
        source['view'].update(position=[self.feet[0],self.feet[1]+(1.8 if self.camera=='first person look at' else 2.2),
            self.feet[2]+(0 if self.camera=='first person look at' else self.boom)],rotation=deepcopy(self.orientation),aspectRatio=1.6)
        source['scan'].update(scannedEntities=len(self.scene_rows),unowned=[])
    def call(self,method,path,body=None):
        identifier=self.refs.get(path.split('/element/')[-1].split('/')[0],'') if '/element/' in path else ''
        old_mode,old_url=self.camera,self.url
        result=super().call(method,path,body)
        if self.camera!=old_mode:
            if self.camera=='first person look at':self.boom=0.
            elif self.boom==0:self.boom=3.25
        if path.endswith('/click') and identifier=='OverteNavigation.address.go':
            if self.fault=='ignored-navigation':self.url=old_url;return result
            with urlopen(self.url,timeout=3) as response:
                need(response.status==200);raw=response.read(262145);need(len(raw)<=262144)
            document=json.loads(raw);self.scene_rows=entity_rows(document);self.fetched.append((self.url,raw))
            values=parse_qs(urlsplit(self.url).query).get('location')
            if values:
                fields=values[0].split('/');self.feet=[float(v) for v in fields[1].split(',')]
                self.orientation=[float(v) for v in fields[2].split(',')]
            self.loads.generation+=1;self.loads.rows.append(load_row(format(self.loads.generation,'032x'),
                generation=self.loads.generation,resourceSha256=resource_hash(self.url),startedEpochMs=self.epoch(),
                updatedEpochMs=self.epoch(),releasedEpochMs=None if self.fault=='held-load' else self.epoch(),
                pending=self.fault=='held-load',bytes=len(raw)))
        return result
    def subject_reader(self):
        value=self.subject.reader(ios=True,native_clock_bound=True);value.pid=42;value.clock_ms=self.epoch;return value
    def loads_reader(self):
        def send(query):
            self.loads.epoch=self.epoch();self.loads.send(query);self.loads.sample['processId']=42
        value=self.loads.reader(ios=True);value.pid=42;value.send=send;value.clock_ms=self.epoch
        value.monotonic=lambda:self.clock;value.sleep=self.sleep;return value
    def core_packet(self,value):
        epoch=self.epoch()-(2000 if self.core_fault=='stale' else 0)
        value.update(processId=42,requestedEpochMs=epoch,capturedEpochMs=epoch,animation={},animationFence={})
        value['lifecycle']=deepcopy(self.native_lifecycle)
        value['graphics'].update(requestedResolutionScale=self.model.resolution,applicationResolutionScale=self.model.resolution,
            hazeSetting=self.model.haze,mirrorsSetting=self.model.mirrors)
        if self.core_fault=='foreign':value['instance']='f'*32
    def core_post(self,request,timeout):
        need(self.foreground)
        command=json.loads(request.data);need(command['action']=='feature-native-observe')
        self.core.send(command);self.response=json.dumps(command).encode();return self
    def execute(self,session,operation,values):
        if operation=='mobile: pullFile' and values['remotePath'].endswith('/feature-native-observation.json'):
            return base64.b64encode(self.core.original().encode()).decode()
        return super().execute(session,operation,values)
    def core_reader(self):
        observer=feature_observation.FeatureObservation(self,'owned-session',self.target,self.process,
            epoch_ms=self.host_epoch,monotonic=lambda:self.clock,sleep=self.sleep)
        return observer.bound_native_observer()
    def surface(self,run,intent,owns,lease,allow_url):
        native=normal_input.NativeInput(self,'owned-session',self.target,self.process,native_epoch_ms=self.epoch,
            monotonic=lambda:self.clock,sleep=self.sleep)
        ui=NativeUI(self,'owned-session',native._check,monotonic=lambda:self.clock,sleep=self.sleep)
        original=IOSScriptIO(ui,native);source=IOSGraphicsSource(original,self.epoch,native._check,42,monotonic=lambda:self.clock)
        controls=TokenGraphicsUI(source,lambda *_:need(False),monotonic=lambda:self.clock,sleep=self.sleep)
        return IOSGraphicsSurface(original,self.subject_reader(),controls,run,intent,owns,lease,allow_url)


class SceneHarness:
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup);self.root=Path(self.temporary.name)
        self.sdk=SDK();self.server=make_server(secrets.token_hex(32),secrets.token_hex(32),adapter_token=secrets.token_hex(32))
        self.origin='http://127.0.0.1:'+str(self.server.server_port)
        self.server.graphics_resources=GraphicsResources(self.origin+'/feature-fixture/v1',clock_ms=self.sdk.host_epoch)
        self.server.journal.clock=self.sdk.host_epoch
        original=self.server.RequestHandlerClass
        class Handler(original):
            def do_GET(self):
                if urlsplit(self.path).path=='/baseline.json':
                    self.send_response(200);self.send_header('Content-Length',str(len(BASELINE)));self.end_headers();self.wfile.write(BASELINE);return
                return super().do_GET()
        self.server.RequestHandlerClass=Handler;self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.close_server);self.sdk.initial(self.origin+'/baseline.json')
        self.patch=patch.object(normal_input,'urlopen',self.sdk.post);self.patch.start();self.addCleanup(self.patch.stop)
        core_patch=patch.object(feature_observation,'post_request',self.sdk.core_post);core_patch.start();self.addCleanup(core_patch.stop)
        self.time_patch=patch.object(witness.time,'time',lambda:self.sdk.host_epoch()/1000);self.time_patch.start();self.addCleanup(self.time_patch.stop)
        self.client=witness.Client(self.origin+'/feature-fixture/v1',self.server.reader_token)
        with patch.object(witness.secrets,'token_hex',return_value=RUN):self.client.register('graphics')
        self.client.activate(TICKET);self.client.graphics_status()
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock')
        def surface(_selector,run,intent,owns,lease,allow_url,*,lock):
            lock.assert_held();return self.sdk.surface(run,intent,owns,lease,allow_url)
        self.adapter=SimpleNamespace(state_path=lambda _:self.root/'session.json',
            normal_feature_runtime=lambda *_,**__: (None,None,deepcopy(BINDING),lambda:True,dict(installedCandidateVerified=True)),
            _graphics_subject_observer=lambda *_,**__:self.sdk.subject_reader(),_scene_load_observer=lambda *_,**__:self.sdk.loads_reader(),
            _native_feature_observer=lambda *_,**__:self.sdk.core_reader(),
            _graphics_surface=surface)
    def close_server(self):self.server.shutdown();self.thread.join(3);self.server.server_close()
    def scene(self):return IOSGraphicsScene(self.adapter,'owned',self.client,RUN,self.lock,
        monotonic=lambda:self.sdk.clock,sleep=self.sdk.sleep)


class SceneTests(SceneHarness,unittest.TestCase):
    def test_ordinary_third_person_preparation_alignment_and_original_camera_world_restoration(self):
        with self.lock.held():
            scene=self.scene();scene.prepare();self.assertEqual('active',scene.state['phase'])
            self.assertEqual('first person look at',self.sdk.camera);self.assertEqual([0.,-.2,0.],self.sdk.feet)
            self.assertEqual(7,len(self.sdk.scene_rows));self.assertEqual(2,len(self.sdk.fetched))
            self.assertEqual('look at',scene.state['original']['subject']['source']['view']['mode'])
            proof=self.scene().restore();self.assertEqual('look at',self.sdk.camera);self.assertEqual([4.,0.,2.],self.sdk.feet)
            self.assertEqual(3.25,self.sdk.boom);self.assertEqual([],self.sdk.scene_rows);self.assertEqual('closed',self.sdk.stage)
            self.assertFalse(any(self.scene().state['leases'].values()))
            self.assertEqual(0,proof['loads']['pendingLeases']);self.assertGreaterEqual(len(self.server.graphics_resources.runs[RUN]['responses']),2)
            self.scene().restore();self.scene().retire();self.assertIsNone(PrivateFeatureState(self.root/'ios-graphics-scene.json').read())

    def test_ignored_navigation_ack_is_not_readiness_and_reconstruction_never_resends_it(self):
        self.sdk.fault='ignored-navigation'
        with self.lock.held():
            with self.assertRaises(NativeUIError):self.scene().prepare()
            count=self.sdk.clicks.count('OverteNavigation.address.go');self.assertEqual(1,count)
            with self.assertRaises(NativeUIError):self.scene().prepare()
            self.assertEqual(count,self.sdk.clicks.count('OverteNavigation.address.go'))
            self.sdk.fault='';self.scene().restore();self.assertEqual('look at',self.sdk.camera)

    def test_unreproducible_original_zoom_refuses_before_any_pointer_or_scene_load(self):
        self.sdk.boom=2.25
        with self.lock.held(),self.assertRaises(NativeUIError):self.scene().prepare()
        self.assertEqual([],self.sdk.clicks);self.assertEqual([],self.sdk.fetched)

    def test_retained_scene_callback_prevents_active_readiness_even_after_real_http_success(self):
        self.sdk.fault='held-load'
        with self.lock.held(),self.assertRaises(NativeUIError):self.scene().prepare()
        self.assertGreater(len(self.server.graphics_resources.runs[RUN]['responses']),0)
        self.assertTrue(any(row['pending'] for row in self.sdk.loads.rows))

    def test_read_only_fixture_phase_is_metadata_and_crossed_activation_is_not_an_observation(self):
        reader=GraphicsFixtureReader(self.client,RUN,epoch_ms=self.sdk.host_epoch);phase=reader.read()
        self.assertEqual(TICKET,phase['ticket']);self.assertEqual('baseline',phase['verb']);self.assertNotIn('facts',phase)
        original=self.client.observe
        def crossed():self.client.activate('d'*32,'open',{});return original()
        with patch.object(self.client,'observe',side_effect=crossed),self.assertRaises(GraphicsPhasePending):reader.read()
        self.assertEqual([],self.sdk.clicks)

    def test_retired_provider_is_distinct_from_actual_native_resource_cleanup(self):
        reader=GraphicsFixtureReader(self.client,RUN,epoch_ms=self.sdk.host_epoch);reader.read();self.client.close()
        with self.assertRaises(GraphicsRunRetired):reader.read()
        self.assertEqual([],self.sdk.clicks);self.assertEqual(self.origin+'/baseline.json',self.sdk.url)


if __name__=='__main__':unittest.main()
