"""Unchanged Phone foundation modules through real public adapter dispatch.

Ordinary SDK input/contract/module/session code is original. Kernel, installed
candidate, SDK, native-view and probe producers are explicit host seams. These
checks never start a device, Appium service, network fixture or Android build.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager,ExitStack
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone'),str(Path(__file__).resolve().parent)]
import appium_adapter as appium
from adapters.normal_ui import NativeUI,NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from contracts import validate_operation_arguments,validate_operation_result
from feature_journeys.session import prepare
from overte_phone_navigation_native import PhoneNavigationView
from self_tests.test_vertical_locomotion import snapshot
from test_navigation_scene import Boundary as SceneBoundary

DOMAIN_ID='11111111-2222-4333-8444-555555555555'
DOMAIN='hifi://controlled.domain.invalid:40102'
DOMAIN_MARKERS=['OVERTE_E2E_DOMAIN_EAST','OVERTE_E2E_DOMAIN_FLOOR','OVERTE_E2E_DOMAIN_NORTH','OVERTE_E2E_DOMAIN_ORIGIN']
SIGNATURE='AAAAAAAAAAAAAAAAAAAAAA=='
POLICY=dict(imageExtent=[640,480],markerRoi=[20,20,180,60],imagePolicy=dict(source='world-render-target',marker=[24,24,152,56],subject=[200,100,600,420]))


class Foundations(SceneBoundary):
    def __init__(self,root):
        super().__init__();self.root=Path(root);self.base=1700000000000;self.operations=[];self.commands=[];self.probes=[];self.views=[]
        self.fault='';self.sequence=0;self.view_sequence=0;self.view_birth='a'*32;self.provider_reads=0
        self.endpoint='http://controlled.test';self.signature=SIGNATURE
        self.target.update(platform='android',physical=True,probe=dict(kind='android-run-as',relativePath=appium.PhoneAppiumAdapter.ANDROID_DEBUG_PROBE),
            process=dict(kind='adb',selector='explicit-synthetic-host-seam'),clientControl=dict(kind='android-run-as-command',relativePath=appium.PhoneAppiumAdapter.ANDROID_CLIENT_COMMAND),
            capabilities={'appium:udid':'explicit-synthetic-host-seam','appium:appPackage':'io.github.noah_be.overte.phone'})
        self.target['controls'].update(look=dict(start=[.7,.5],end=[.8,.5]),move=dict(forward=dict(start=[.1,.7],end=[.1,.4],mode='hold')),jump=[.9,.8])
        del self.adapter.advertised_capabilities;del self.adapter.controlled_android_client
        self.adapter.platform='android';self.adapter.probe_snapshot=lambda *_:self.probe()
        self.target['serverUrl']='http://explicit-synthetic.invalid:4723'
        self.sdk.process='31415:271828';self.process['identity']=self.sdk.process
        original_call=self.sdk.call
        def sdk_call(method,path,body=None):
            if method=='GET'and path=='/session/owned-session':return {}
            return original_call(method,path,body)
        self.sdk.call=sdk_call
        original_arrive=self.sdk.arrive
        def arrive(url):
            if url==DOMAIN:
                if self.fault!='ignored-domain':self.sdk.current=url;self.sdk.connected=True
            else:original_arrive(url)
        self.sdk.arrive=arrive
        self.sdk.state['targetFingerprint']=self.adapter.snapshot_fingerprint(self.target)
        self.adapter.read_session=lambda _:self.sdk.state
        self.adapter.write_android_client_command=self.consume;self.adapter._navigation_view=self.native_view
        self.adapter._feature_fixture_client=lambda:self
        self.provider=dict(navigationProviderVersion=1,instance='b'*32,inputs=dict(protocolSignature=SIGNATURE,sourceRevision=self.installed['sourceRevision'],sceneUrl=self.sdk.scene),
            capturedEpochMs=self.epoch(),ready=True,activeRuns=0,failedResponses=0,internalErrors=0)
        self.url=self.endpoint+'/feature-fixture/v1'
        self.bookmark=self.root/'original-bookmarks.json';self.bookmark.write_text('{}');self.bookmark.chmod(0o600)
        self.policy=self.root/'navigation-policy.json';PrivateFeatureState(self.policy).write(POLICY,None)
        self.sdk.ui.sleep=self.sdk.sleep
    def epoch(self):return self.base+round(self.sdk.clock*1000)
    def request(self,path):
        assert path=='/navigation-provider';self.provider_reads+=1;value=deepcopy(self.provider);value['capturedEpochMs']=self.epoch()
        if self.fault=='stale-provider':value['capturedEpochMs']-=1501
        if self.fault=='foreign-provider-url':value['inputs']['sceneUrl']='http://foreign.invalid/scene.json'
        if self.fault=='foreign-source':value['inputs']['sourceRevision']='2'*40
        if self.fault=='failed-provider':value['failedResponses']=1
        return value
    def consume(self,_client,_session,_target,command,*_args):
        self.commands.append(deepcopy(command));assert command['action']=='enter-domain' and command['url']==DOMAIN
        if self.fault!='ignored-domain':self.sdk.connected=True
    def probe(self):
        self.sequence+=1;value=snapshot();epoch=self.epoch();value.update(sampleSequence=self.sequence,sampleEpochMs=epoch)
        value['build']['platform']='Synthetic Android producer';value['render']=dict(frameCount=self.sequence,lastFrameEpochMs=epoch)
        value['domain']=dict(connected=self.sdk.connected,hostname='controlled.domain.invalid' if self.sdk.connected else '',id=DOMAIN_ID if self.sdk.connected else '',
            protocol='hifi' if self.sdk.connected else 'http',serverless=not self.sdk.connected)
        value['scene'].update(url=DOMAIN if self.sdk.connected else self.sdk.current,fixtureMarkers=[] if self.sdk.connected else self.sdk.markers,
            fixtureMarkerCount=0 if self.sdk.connected else len(self.sdk.markers),domainMarkers=DOMAIN_MARKERS if self.sdk.connected else [],domainMarkerCount=len(DOMAIN_MARKERS) if self.sdk.connected else 0,
            entityCount=5)
        value['avatar'].update(position=dict(x=self.sdk.position['x'],y=1.,z=self.sdk.position['z']),feetPosition=deepcopy(self.sdk.position))
        value['tablet'].update(open=self.sdk.screen is not None,home=self.sdk.screen=='home')
        if self.fault=='stale-probe':value['sampleSequence']=1
        self.probes.append(deepcopy(value));return value
    def native_view(self,_selector,*,read_only=True):
        assert read_only;state={}
        pid=int(self.process['identity'].split(':')[0])
        def send(request):
            self.view_sequence+=1;epoch=self.epoch();raw=self.bookmark.read_bytes()
            source=dict(tabletShown=self.sdk.screen is not None,ui=dict(present=False,addressDialog=self.sdk.address_open,notFoundModal=False,bookmarkDialog=False,pendingCommands=0,activeTimers=0,notFound={}),
                storage=dict(present=True,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),bookmarks=json.loads(raw)),
                preferences={key:dict(present=False,value=None) for key in ('placesAppMetaverseToFetch','placesAppPinnedMetaverse','placesAppMaturityFilter','private/places/federation')},
                endpoint=self.endpoint,protocolSignature=self.signature,keyboard=dict(available=True,backend='native-touch-metrics',visible=False))
            value=dict(navigationViewVersion=1,commandId=request['commandId'],runId=request['runId'],instance=self.view_birth,sequence=self.view_sequence,processId=pid,
                requestedEpochMs=epoch,capturedEpochMs=epoch,source=source)
            if self.fault=='foreign-native-endpoint':value['source']['endpoint']='http://foreign.invalid'
            if self.fault=='foreign-native-protocol':value['source']['protocolSignature']='BBBBBBBBBBBBBBBBBBBBBB=='
            if self.fault=='stale-native':value['capturedEpochMs']-=1600
            if self.fault=='native-birth' and self.view_sequence%2==0:value['instance']='c'*32
            if self.fault=='native-pid':value['processId']=pid+1
            self.views.append(deepcopy(value));state['value']=value
        return PhoneNavigationView(send,lambda:json.dumps(state['value']),self.epoch,lambda:True,pid,monotonic=lambda:self.sdk.clock,sleep=self.sdk.sleep)
    def environment(self):
        return dict(OVERTE_DEVICE_ADAPTER_MANIFEST=str(ROOT/'tests/device/adapters/android-phone/appium.json'),OVERTE_DEVICE_TARGET_SELECTOR='explicit-synthetic',OVERTE_DEVICE_ARTIFACT_DIR=str(self.root),
            OVERTE_E2E_SCENE_URL=self.sdk.scene,OVERTE_E2E_DOMAIN_URL=DOMAIN,OVERTE_E2E_DOMAIN_HOST='controlled.domain.invalid',OVERTE_E2E_DOMAIN_ID=DOMAIN_ID,
            OVERTE_E2E_DOMAIN_MARKERS_JSON=json.dumps(DOMAIN_MARKERS),OVERTE_E2E_DOMAIN_STABLE_SAMPLES='3',OVERTE_E2E_TIMEOUT_SECONDS='1',OVERTE_E2E_POLL_SECONDS='.05',
            OVERTE_PHONE_FEATURE_WORLD_NAVIGATION='1',OVERTE_PHONE_NAVIGATION_IMAGE_POLICY=str(self.policy),OVERTE_ANDROID_E2E_FLYING='1')
    @contextmanager
    def scope(self):
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ,self.environment()))
            import module_support,overte_session
            stack.enter_context(patch.object(appium,'NativeUI',lambda client,session,guard,**_options:NativeUI(client,session,guard,timeout=.8,monotonic=lambda:self.sdk.clock,sleep=self.sdk.sleep)))
            def sdk_client(endpoint):
                assert endpoint==self.target['serverUrl'],'Foreign synthetic SDK endpoint'
                return self.sdk
            stack.enter_context(patch.object(appium,'WebDriver',sdk_client))
            stack.enter_context(patch.object(appium.AppiumAdapter,'probe_snapshot',lambda _adapter,_client,_session,_target:self.probe()))
            stack.enter_context(patch.object(module_support,'ARTIFACT_DIR',self.root));stack.enter_context(patch.object(overte_session,'ARTIFACT_DIR',self.root))
            stack.enter_context(patch.object(module_support,'invoke',lambda _manifest,_target,operation,arguments:self.invoke(operation,arguments or {})))
            stack.enter_context(patch('time.time',lambda:self.epoch()/1000));stack.enter_context(patch('time.monotonic',lambda:self.sdk.clock));stack.enter_context(patch('time.sleep',self.sdk.sleep))
            stack.enter_context(patch('urllib.request.build_opener',side_effect=AssertionError('Synthetic fixture must never use remote transport')))
            stack.enter_context(patch('feature_journeys.witness.build_opener',side_effect=AssertionError('Synthetic fixture must never use remote transport')))
            yield
    def invoke(self,operation,values):
        self.operations.append((operation,deepcopy(values)));validate_operation_arguments(operation,values)
        return validate_operation_result(operation,self.adapter.invoke('explicit-synthetic',operation,values))
    def module(self,name):
        import module_support
        scope={'__name__':'original_'+name+'_host_contract','__file__':str(ROOT/'tests/device/modules'/name)}
        with patch.object(module_support,'module_main',lambda _main:None):
            path=ROOT/'tests/device/modules'/name;exec(compile(path.read_bytes(),str(path),'exec'),scope)
        return scope['main']()
    def close_controls(self):return self.invoke('places.close',{})


class NavigationFoundationsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='phone-nav-foundations-');self.addCleanup(self.tmp.cleanup);self.boundary=Foundations(Path(self.tmp.name))
    def test_unchanged_domain_roundtrip_places_and_feature_prepare_share_one_http_scene_normal_inputs(self):
        b=self.boundary
        with b.scope():
            from overte_session import OverteSession
            b.module('domain_roundtrip.py');self.assertTrue(b.sdk.connected)
            b.module('places_navigation.py');self.assertFalse(b.sdk.connected)
            prepare(OverteSession(),'world-navigation');b.close_controls()
        scene=[fields['url'] for operation,fields in b.operations if operation=='scene.load']
        self.assertEqual([b.sdk.scene]*3,scene);self.assertEqual(b.sdk.scene,b.target['controls']['normalNavigation']['sceneUrl']);self.assertEqual(b.sdk.scene,b.provider['inputs']['sceneUrl'])
        self.assertGreaterEqual(b.provider_reads,3);self.assertGreaterEqual(len(b.views),6)
        self.assertIn('Go to destination',b.sdk.inputs);self.assertIn('editor-enter',b.sdk.inputs);self.assertEqual(2,b.sdk.inputs.count('goBack'));self.assertEqual(2,b.sdk.inputs.count('goForward'))
        self.assertIsNone(b.sdk.screen);self.assertFalse(b.sdk.address_open);self.assertNotIn('normalNavigation',b.sdk.state)
        self.assertEqual([],b.commands);self.assertIn(('navigation.enter-domain',{'url':DOMAIN}),b.operations)
        self.assertTrue((b.root/'domain-roundtrip.json').is_file());self.assertTrue((b.root/'places-navigation-observation.json').is_file())
    def test_full_flag_requires_real_provider_and_both_original_native_brackets_before_any_scene_input(self):
        for fault in ('stale-provider','foreign-provider-url','foreign-source','failed-provider','foreign-native-endpoint','foreign-native-protocol','stale-native','native-birth','native-pid'):
            b=self.boundary;b.fault=fault
            with self.subTest(fault=fault),b.scope(),self.assertRaises((RuntimeError,ValueError)):b.invoke('scene.load',dict(url=b.sdk.scene))
            self.assertFalse(b.sdk.inputs);b.fault=''
    def test_ignored_normal_goto_ack_cannot_satisfy_unmodified_domain_or_places_or_prepare(self):
        for name in ('domain_roundtrip.py','places_navigation.py','prepare'):
            with self.subTest(name=name):
                temp=tempfile.TemporaryDirectory(prefix='nav-ignored-');self.addCleanup(temp.cleanup);b=Foundations(Path(temp.name));b.sdk.mutation='goto-ignored'
                with b.scope():
                    from module_support import AssertionFailure,InfrastructureError
                    with self.assertRaises((AssertionFailure,InfrastructureError,AssertionError)):
                        if name=='prepare':
                            from overte_session import OverteSession
                            prepare(OverteSession(),'world-navigation')
                        else:b.module(name)
                with b.scope():b.close_controls()
                self.assertTrue(b.sdk.connected);self.assertFalse(b.sdk.address_open);self.assertIsNone(b.sdk.screen);self.assertNotIn('normalNavigation',b.sdk.state)
    def test_stale_probe_never_qualifies_actual_domain_roundtrip(self):
        b=self.boundary;b.fault='stale-probe'
        with b.scope(),self.assertRaises(RuntimeError):b.module('domain_roundtrip.py')
        with b.scope():b.close_controls()
        self.assertNotIn('normalNavigation',b.sdk.state)
    def test_module_gate_uses_actual_advertised_union_and_refuses_a_missing_original_foundation(self):
        b=self.boundary
        with b.scope():
            capabilities=b.adapter.advertised_capabilities(b.target)
            import module_support
            scope={'__name__':'original_feature_gate_contract','__file__':str(ROOT/'tests/device/modules/feature_capability_gate.py')}
            with patch.object(module_support,'module_main',lambda _main:None):
                path=ROOT/'tests/device/modules/feature_capability_gate.py';exec(compile(path.read_bytes(),str(path),'exec'),scope)
            with patch.dict(os.environ,OVERTE_DEVICE_CAPABILITIES_JSON=json.dumps(sorted(capabilities))),patch.object(sys,'argv',['gate','--area','world-navigation']):scope['main']()
            with patch.dict(os.environ,OVERTE_DEVICE_CAPABILITIES_JSON=json.dumps(sorted(set(capabilities)-{'places.goto'}))),patch.object(sys,'argv',['gate','--area','world-navigation']),self.assertRaises(module_support.InfrastructureError):scope['main']()
    def test_original_sdk_context_process_or_code_replacement_during_scene_submission_stays_red(self):
        for fault in ('session','generation','fingerprint','target','process','candidate'):
            with self.subTest(fault=fault):
                temp=tempfile.TemporaryDirectory(prefix='nav-context-');self.addCleanup(temp.cleanup);b=Foundations(Path(temp.name));original=b.sdk.arrive
                def arrive(url):
                    original(url)
                    if fault=='session':b.sdk.state['sessionId']='foreign-sdk-session'
                    elif fault=='generation':b.sdk.state['generation']+=1
                    elif fault=='fingerprint':b.sdk.state['targetFingerprint']='f'*64
                    elif fault=='target':b.target['displayName']='Replaced original target'
                    elif fault=='process':b.process['identity']='31416:32'
                    else:b.installed['artifactSha256']='f'*64
                b.sdk.arrive=arrive
                with b.scope(),self.assertRaises((RuntimeError,ValueError)):b.invoke('scene.load',dict(url=b.sdk.scene))
                self.assertEqual(1,b.sdk.inputs.count('editor-enter'))
                self.assertTrue(b.sdk.state['normalNavigation']['addressOwned'])
                self.assertNotIn('PhoneAddressCancelButton',b.sdk.inputs)
    def test_inconsistent_original_session_is_refused_before_provider_or_native_input(self):
        b=self.boundary;b.sdk.state['targetFingerprint']='f'*64
        with b.scope(),self.assertRaises(ValueError):b.invoke('scene.load',dict(url=b.sdk.scene))
        self.assertFalse(b.sdk.inputs);self.assertFalse(b.views);self.assertEqual(0,b.provider_reads)
    def test_lost_real_enter_reply_is_never_replayed_and_original_close_can_retire_partial_intent(self):
        b=self.boundary;original=b.sdk.call
        def lost(method,path,body=None):
            value=original(method,path,body)
            if path.endswith('/appium/device/press_keycode'):raise OSError('lost synthetic SDK response after actual Enter')
            return value
        b.sdk.call=lost
        with b.scope(),self.assertRaises(NativeUIError):b.invoke('scene.load',dict(url=b.sdk.scene))
        self.assertEqual(1,b.sdk.inputs.count('editor-enter'));self.assertTrue(b.sdk.state['normalNavigation']['addressOwned'])
        b.sdk.call=original
        with b.scope():b.close_controls();b.close_controls()
        self.assertEqual(1,b.sdk.inputs.count('editor-enter'));self.assertNotIn('normalNavigation',b.sdk.state)
    def test_default_off_has_no_public_feature_triple_and_keeps_ordinary_foundation_input(self):
        b=self.boundary
        with b.scope(),patch.dict(os.environ,OVERTE_PHONE_FEATURE_WORLD_NAVIGATION='0'):
            self.assertFalse(any(cap.startswith('feature.world-navigation.') for cap in b.adapter.advertised_capabilities(b.target)))
            self.assertEqual({'requested':True},b.invoke('scene.load',dict(url=b.sdk.scene)));b.close_controls()
        self.assertEqual(0,b.provider_reads);self.assertFalse(b.views);self.assertFalse(b.sdk.connected)
    def test_ignored_original_domain_reentry_cannot_complete_unchanged_roundtrip(self):
        b=self.boundary;b.fault='ignored-domain'
        with b.scope(),self.assertRaises(RuntimeError):b.module('domain_roundtrip.py')
        self.assertIn(('navigation.enter-domain',{'url':DOMAIN}),b.operations);self.assertFalse(b.commands);self.assertFalse((b.root/'domain-roundtrip.json').exists())
        with b.scope():b.close_controls()
        self.assertNotIn('normalNavigation',b.sdk.state)
    def test_ignored_actual_places_transition_fails_and_ordinary_finally_retires_only_its_controls(self):
        b=self.boundary;b.sdk.connected=False;b.sdk.current=b.sdk.scene;original=b.sdk.arrive
        def arrive(url):
            if '/2,0,4/' not in url:original(url)
        b.sdk.arrive=arrive
        with b.scope(),self.assertRaises(RuntimeError):b.module('places_navigation.py')
        report=json.loads((b.root/'places-navigation-observation.json').read_text())
        self.assertFalse(report['sequenceCompleted']);self.assertTrue(report['cleanupSucceeded'])
        self.assertIsNone(b.sdk.screen);self.assertFalse(b.sdk.address_open);self.assertNotIn('normalNavigation',b.sdk.state)
    def test_ignored_owned_control_close_preserves_original_lease_and_retry_observes_actual_absence(self):
        from navigation_observation import viewpoint_urls
        b=self.boundary
        with b.scope():
            b.invoke('places.goto',dict(url=viewpoint_urls(b.sdk.scene)['B']));b.invoke('places.back',{})
            original=b.sdk.call
            def ignored(method,path,body=None):
                if path.endswith('/click') and b.sdk.by_reference[path.split('/element/',1)[1].split('/')[0]]=='nav.close':return None
                return original(method,path,body)
            b.sdk.call=ignored
            with self.assertRaises(RuntimeError):b.close_controls()
            self.assertTrue(b.sdk.state['normalNavigation']['tabletOwned']);self.assertIsNotNone(b.sdk.screen)
            b.sdk.call=original;b.close_controls();b.close_controls()
        self.assertNotIn('normalNavigation',b.sdk.state);self.assertIsNone(b.sdk.screen)

if __name__=='__main__':unittest.main()
