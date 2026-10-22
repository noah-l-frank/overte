"""Normal HTTP scene input at explicit SDK/kernel/provider seams only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from self_tests.test_phone_navigation import NativePhone
from adapters.normal_ui import NativeUI,NativeUIError
from overte_phone_navigation_scene import configuration,provider
import appium_adapter as appium


class SDK(NativePhone):
    def __init__(self):super().__init__();self.connected=True
    def arrive(self,url):
        if '?' not in url:
            self.current=url;self.position=dict(x=0,y=0,z=4)
        else:super().arrive(url)
        self.connected=False
    def call(self,method,path,body=None):
        if path.endswith('/text'):
            self.calls.append((method,path,body));return self.field
        return super().call(method,path,body)


class Boundary:
    def __init__(self):
        self.sdk=SDK();self.adapter=appium.PhoneAppiumAdapter.__new__(appium.PhoneAppiumAdapter);self.adapter.candidate=object()
        self.target=dict(appId='io.github.noah_be.overte.phone',controls=dict(normalNavigation=self.sdk.profile),scene=dict(kind='android-debug-e2e'))
        self.adapter.target=lambda _:self.target;self.adapter.controlled_android_client=lambda _:True
        self.adapter.account_fixture_configuration=lambda _:None
        self.adapter.advertised_capabilities=lambda _:{'scene.load','places.goto','places.close'}
        self.adapter.ensure_session=lambda _:(self.sdk,'owned-session',self.sdk.state)
        self.installed=deepcopy(self.sdk.identity);self.process=dict(running=True,identity=self.sdk.process)
        self.adapter.installed_identity=lambda _:deepcopy(self.installed)
        self.adapter.process_state=lambda *_:deepcopy(self.process)
        self.adapter.query_app_state=lambda *_:4
        self.adapter.save_session=lambda *_:self.sdk.save()
        self.sdk.state['targetFingerprint']=self.adapter.snapshot_fingerprint(self.target)
        self.adapter.read_session=lambda _:self.sdk.state
    def patch(self):
        from contextlib import ExitStack
        scope=ExitStack();scope.enter_context(patch.dict('os.environ',{'OVERTE_E2E_SCENE_URL':self.sdk.scene,'OVERTE_PHONE_FEATURE_WORLD_NAVIGATION':'0'}))
        scope.enter_context(patch.object(appium.PhoneAdapter,'require_bound_operation',lambda *_:None))
        scope.enter_context(patch.object(appium,'NativeUI',lambda client,session,guard:NativeUI(client,session,guard,timeout=.8,monotonic=lambda:self.sdk.clock,sleep=self.sdk.sleep)))
        return scope
    def invoke(self,operation,values):return self.adapter.invoke('explicit-synthetic',operation,values)


class NavigationSceneTests(unittest.TestCase):
    def test_real_phone_dispatch_and_normal_ui_load_only_the_exact_owned_base_and_return_no_success_verdict(self):
        b=Boundary()
        with b.patch():result=b.invoke('scene.load',dict(url=b.sdk.scene))
        self.assertEqual({'requested':True},result);self.assertEqual(b.sdk.scene,b.sdk.current);self.assertFalse(b.sdk.connected)
        self.assertEqual(['Go to destination','PhoneAddressGoButton'],b.sdk.inputs)
        self.assertNotIn('verification',result);self.assertFalse(b.sdk.state['normalNavigation']['addressOwned'])
    def test_foreign_profile_env_or_viewpoint_is_rejected_before_any_ui_input(self):
        for target in ('foreign','environment','viewpoint','unbound'):
            b=Boundary();url=b.sdk.scene
            if target=='foreign':url=url.replace('controlled.test','foreign.test')
            elif target=='viewpoint':url+='?location=/0,0,4/0,0,0,1'
            elif target=='unbound':b.adapter.candidate=None
            with b.patch():
                if target=='environment':
                    with patch.dict('os.environ',{'OVERTE_E2E_SCENE_URL':'http://foreign.test/scene.json'}),self.assertRaises(Exception):b.invoke('scene.load',dict(url=url))
                else:
                    with self.assertRaises(Exception):b.invoke('scene.load',dict(url=url))
            self.assertEqual([],b.sdk.inputs)
    def test_ignored_input_remains_an_ack_and_does_not_create_an_arrival(self):
        b=Boundary();b.sdk.mutation='goto-ignored';before=b.sdk.current
        with b.patch():self.assertEqual({'requested':True},b.invoke('scene.load',dict(url=b.sdk.scene)))
        self.assertEqual(before,b.sdk.current);self.assertTrue(b.sdk.connected);self.assertEqual(1,b.sdk.inputs.count('PhoneAddressGoButton'))
    def test_preexisting_foreign_panel_cannot_be_taken_over(self):
        for kind in ('address','tablet'):
            b=Boundary()
            if kind=='address':b.sdk.address_open=True
            else:b.sdk.screen='settings'
            with b.patch(),self.assertRaises(NativeUIError):b.invoke('scene.load',dict(url=b.sdk.scene))
            self.assertEqual([],b.sdk.inputs)
    def test_owned_provider_is_fresh_and_source_build_and_url_are_independent_admission_inputs(self):
        b=Boundary();epoch=int(time.time()*1000)
        row=dict(navigationProviderVersion=1,instance='a'*32,inputs=dict(protocolSignature='AAAAAAAAAAAAAAAAAAAAAA==',sourceRevision='1'*40,sceneUrl=b.sdk.scene),capturedEpochMs=epoch,ready=True,activeRuns=0,failedResponses=0,internalErrors=0)
        self.assertEqual(row,provider(row,b.sdk.scene,'1'*40,epoch))
        for change in (dict(capturedEpochMs=epoch-1501),dict(ready=False),dict(activeRuns=True),dict(internalErrors=1),dict(inputs=row['inputs']|dict(sourceRevision='2'*40)),dict(inputs=row['inputs']|dict(sceneUrl='http://foreign.test/scene.json'))):
            with self.subTest(change=change),self.assertRaises(Exception):provider(row|change,b.sdk.scene,'1'*40,epoch)
    def test_candidate_or_process_change_after_normal_input_stays_red(self):
        for target in ('candidate','process'):
            b=Boundary();original=b.sdk.arrive
            def arrive(url):
                original(url)
                if target=='candidate':b.installed['artifactSha256']='3'*64
                else:b.process['identity']='other-original-process'
            b.sdk.arrive=arrive
            with b.patch(),self.assertRaises(Exception):b.invoke('scene.load',dict(url=b.sdk.scene))


if __name__=='__main__':unittest.main()
