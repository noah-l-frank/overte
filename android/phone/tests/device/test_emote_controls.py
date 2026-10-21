"""Real Python/JS controls with explicit synthetic native and SDK boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.normal_ui import NativeUIError
from adapters.token_emote_ui import TokenEmoteUI
from overte_phone_emote_controls import PhoneEmoteIO
from self_tests.test_token_emote_ui import EmoteBoundary
from self_tests.test_native_feature_observation import probe_source
from audio_native_boundary import ControlNativeBoundary


class RawWidgets(EmoteBoundary):
    def capture(self):
        value=super().capture();scope=value['scope']
        return dict(emoteControlsVersion=1,instance=scope['instance'],generation=scope['generation'],
            ready=value['ready'],controls=value['controls'])


class PhoneEmoteControlsTests(unittest.TestCase):
    def boundary(self):
        widgets=RawWidgets();source=ControlNativeBoundary(widgets,'phone-emote-ui')
        io=PhoneEmoteIO(source.send,lambda:json.dumps(source.value),lambda:20000,lambda:True,31,
            tablet_shown=lambda:widgets.tablet,monotonic=lambda:widgets.clock,sleep=widgets.sleep)
        return widgets,source,io

    def test_original_phone_transport_consumes_input_without_claiming_pose(self):
        widgets,source,io=self.boundary();ui=TokenEmoteUI(io,widgets.intent,monotonic=lambda:widgets.clock,sleep=widgets.sleep)
        ui.open();ui.play('Love');ui.cancel();ui.close()
        self.assertEqual('',widgets.active);self.assertFalse(widgets.page)
        self.assertIn('down',widgets.actions)
        self.assertTrue(all(row['controlId']!='emote.play.Sit1' for row in source.input_requests))
        self.assertNotIn('animation',io.original_packet);self.assertNotIn('expected',str(source.commands))

    def test_fresh_admission_never_replaces_the_original_button_or_context(self):
        widgets,source,io=self.boundary();widgets.page=True;original=io.capture()
        for fault in ('context','token','consumed'):
            widgets,source,io=self.boundary();widgets.page=True;original=io.capture()
            if fault=='context':widgets.generation='e'*32
            elif fault=='token':widgets.active='Love'
            else:source.command_sequence+=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):io.activate('emote.play.Crying',reference=original)
            self.assertEqual([],source.input_requests)

    def test_native_re_resolution_rejects_changed_original_after_host_admission(self):
        widgets,source,io=self.boundary();widgets.page=True;original=io.capture()
        source.before_input=lambda:setattr(widgets,'active','Love')
        with self.assertRaises(NativeUIError):io.activate('emote.play.Crying',reference=original)
        self.assertEqual(1,len(source.input_requests));self.assertEqual([],widgets.actions)
        self.assertEqual(1,source.command_sequence)

    def test_old_foreign_unavailable_or_malformed_native_originals_are_red(self):
        for fault in ('pid','birth','old','cursor','version','ready','extra'):
            widgets,source,io=self.boundary();io.capture()
            def changed(value):
                if fault=='pid':value['processId']=32
                elif fault=='birth':value['instance']='e'*32
                elif fault=='old':value['capturedEpochMs']=18000
                elif fault=='cursor':value['sourceSequence']=1
                elif fault=='version':value['emoteControlsVersion']=True
                elif fault=='ready':value['ready']=False
                else:value['animation']='Crying'
            source.mutate=changed
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):io.capture()

    def test_actual_sdk_visibility_and_whole_capture_age_cannot_be_fabricated(self):
        widgets,source,io=self.boundary();widgets.page=True
        io.tablet_shown=lambda:False
        with self.assertRaises(NativeUIError):io.capture()
        widgets,source,io=self.boundary()
        def slow():widgets.clock+=2;return True
        io.tablet_shown=slow
        with self.assertRaises(NativeUIError):io.capture()
        self.assertIsNone(io.original_packet)

    def test_lost_or_ignored_native_input_receipt_cannot_be_returned_as_success(self):
        widgets,source,io=self.boundary();widgets.page=True;original=io.capture()
        def unavailable(value):
            if value['action']!='observe':value['performed']=False
        source.mutate=unavailable
        with self.assertRaises(NativeUIError):io.activate('emote.play.Crying',reference=original)
        self.assertEqual(1,len(source.input_requests));self.assertEqual('Crying',widgets.active)

    def factory(self,*,read_only=False):
        import test_feature_adapters as bound
        setup=bound.FeatureAdapterTests();setup.setUp();self.addCleanup(setup.doCleanups)
        setup.native.screen='home';widgets=RawWidgets();source=ControlNativeBoundary(widgets,'phone-emote-ui')
        def send(client,session,target,command,process):
            self.assertEqual({'running':True,'identity':'31:14'},process);source.send(command)
        def read(device,package,path,**kwargs):
            self.assertEqual('files/overte-e2e/phone-emote-ui.json',path);self.assertEqual({'attempts':1},kwargs)
            return json.dumps(source.value)
        for boundary in (patch.object(setup.adapter,'write_android_client_command',side_effect=send),
            patch.object(setup.fixture.adb,'read_debug_app_file',side_effect=read,create=True),
            patch.object(setup.fixture.adb,'epoch_milliseconds',return_value=20000,create=True)):
            boundary.start();self.addCleanup(boundary.stop)
        if read_only:setup.read_only_boundaries()
        return setup,widgets,source,setup.adapter._emote_controls(bound.SELECTOR,widgets.intent,read_only=read_only)

    def test_actual_candidate_bound_phone_factory_routes_original_input_and_refuses_changed_apk(self):
        setup,widgets,source,ui=self.factory();ui.open();ui.play('Crying')
        self.assertEqual('Crying',widgets.active);self.assertEqual([],setup.native.inputs)
        before=len(source.commands);setup.fixture.adb.digest='f'*64
        with self.assertRaises(NativeUIError):ui.play('Surprised')
        self.assertEqual(before,len(source.commands));self.assertEqual('Crying',widgets.active)

    def test_actual_read_only_factory_observes_without_session_repair_and_blocks_input(self):
        setup,widgets,source,ui=self.factory(read_only=True);value=ui.capture()
        self.assertTrue(value['open']);self.assertEqual([],setup.native.inputs)
        with self.assertRaises(NativeUIError):ui.open()
        self.assertEqual([],source.input_requests);self.assertTrue(all(command['request']['action']=='observe' for command in source.commands))
        self.assertEqual([],setup.native.lifecycle_inputs)

    def test_component_does_not_advertise_the_incomplete_feature_area(self):
        setup,_widgets,_source,_ui=self.factory()
        self.assertFalse(any(capability.startswith('feature.emotes.') for capability in setup.adapter.advertised_capabilities(setup.target)))

    def test_actual_probe_grammar_dedup_and_missing_hook_fail_closed(self):
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
let calls=[],files=[];
const Test={phoneEmoteUi:r=>{calls.push(r);return {commandId:r.commandId,performed:true};},saveObject:(v,name)=>files.push({v,name})};
SOURCE
function outer(request){return {schemaVersion:1,commandId:request.commandId,action:"phone-emote-ui",request};}
const observe={schemaVersion:1,commandId:"a".repeat(32),action:"observe"};
applyAndroidControlCommand(outer(observe));applyAndroidControlCommand(outer(observe));
if(calls.length!==1||files[0].name!=="phone-emote-ui.json")throw Error("original dispatch");
const input={schemaVersion:1,commandId:"b".repeat(32),action:"activate",instance:"c".repeat(32),generation:"d".repeat(32),
 sequence:1,observedElapsedMs:0,controlId:"emote.play.Sit",controlToken:"e".repeat(32)};
applyAndroidControlCommand(outer(input));
for(const edit of [{controlId:"emote.play.Sit1"},{controlId:"emote.page"},{controlId:"emote.play.Waving\n"},
 {sequence:true},{commandId:["f".repeat(32)]},{controlToken:["e".repeat(32)]},{expectedAnimation:"Sit2"},{action:"restore-animation"}]){
 applyClientCommand(outer({...input,commandId:"f".repeat(32),...edit}));}
if(calls.length!==2)throw Error("unknown or expected-state input admitted");
const scroll={...input,commandId:"1".repeat(32),action:"scroll",controlId:"emote.grid",direction:"down"};
applyAndroidControlCommand(outer(scroll));if(calls.length!==3)throw Error("ordinary scroll missing");
delete Test.phoneEmoteUi;applyClientCommand(outer({...observe,commandId:"2".repeat(32)}));
if(files[3].v.available!==false)throw Error("missing native hook green");
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
