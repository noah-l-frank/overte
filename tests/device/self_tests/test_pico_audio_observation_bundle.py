"""Declared packet boundaries and actual Node probe; no Qt, SDK or device run."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(os.environ.get('PICO_AUDIO_BUNDLE_TEST_REPO',Path(__file__).resolve().parents[3]))
sys.path.insert(0,str(ROOT/'tests/device'))
HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('pico_audio_bundle_private',HERE/'adapters/pico4/audio_observation_bundle.py')
bundle=importlib.util.module_from_spec(spec);spec.loader.exec_module(bundle)
from adapters.normal_ui import NativeUIError
from self_tests.test_native_feature_observation import Boundary as Native
from self_tests.test_pico_audio_settings_source import Boundary as Settings
from self_tests.test_pico_audio_pages import Boundary as Pages,BRIDGE
from self_tests.test_recorded_preview_history import voice


def fixture(offset=0):
    command=dict(schemaVersion=1,action=bundle.ACTION,runId='a'*32,
        commandId=f'{1+offset:032x}',nativeNonce=f'{2+offset:032x}',settingsNonce=f'{3+offset:032x}')
    native=Native();native.sequence=offset
    native.mutate=lambda value:value['audio'].update(muted=False,recordedVoice=voice([],cycle=0,started=0))
    native.send(dict(commandId=command['nativeNonce']))
    settings=Settings();settings.sequence=offset
    settings.send(dict(commandId=command['settingsNonce'],runId=command['runId']))
    pages=Pages();pages.sequence=offset
    packet=dict(picoAudioObservationBundleVersion=1,commandId=command['commandId'],runId=command['runId'],processId=123,
        requestedEpochMs=19999,capturedEpochMs=20000,status='ready',nativeNonce=command['nativeNonce'],
        settingsNonce=command['settingsNonce'],nativeRaw=native.original(),settingsRaw=settings.read(),pagesRaw=pages.read(),
        originalPageKnownClosed=True,nativeAdmissionJoined=False)
    return command,packet


def read(command,packet,epoch=20000):return bundle.validate(json.dumps(packet),command,123,BRIDGE,epoch)


class AudioBundleTests(unittest.TestCase):
    def test_original_subpackets_and_idle_projection_are_preserved(self):
        command,packet=fixture();value=read(command,packet)
        self.assertEqual(packet,value['envelope'])
        self.assertEqual(json.loads(packet['nativeRaw']),value['native'])
        self.assertEqual('idle',value['actual']['phase']);self.assertFalse(value['actual']['open'])
        self.assertIs(value,bundle.accept(None,value))

    def test_foreign_command_pid_nonce_admission_and_unconfirmed_close_fail(self):
        faults=(lambda p:p.update(commandId='f'*32),lambda p:p.update(processId=True),
            lambda p:p.update(nativeNonce='e'*32),lambda p:p.update(nativeAdmissionJoined=True),
            lambda p:p.update(originalPageKnownClosed=False),lambda p:p.update(status='pending'),
            lambda p:p.update(picoAudioObservationBundleVersion=True),lambda p:p.update(expectedQuiet=True))
        for fault in faults:
            with self.subTest(fault=fault):
                command,packet=fixture();fault(packet)
                with self.assertRaises((NativeUIError,ValueError)):read(command,packet)

    def test_outer_and_original_inner_age_are_independent(self):
        command,packet=fixture()
        for change in ({'requestedEpochMs':18000},{'capturedEpochMs':19998},{'requestedEpochMs':True}):
            with self.subTest(change=change),self.assertRaises(NativeUIError):read(command,dict(packet,**change))
        native=json.loads(packet['nativeRaw']);native['capturedEpochMs']=18000
        with self.assertRaises(NativeUIError):read(command,dict(packet,nativeRaw=json.dumps(native)))
        settings=json.loads(packet['settingsRaw']);settings['source']['clientCapturedEpochMs']=19998
        with self.assertRaises(NativeUIError):read(command,dict(packet,settingsRaw=json.dumps(settings)))
        pages=json.loads(packet['pagesRaw']);pages['picoAudioPages']['capturedEpochMs']=18000
        with self.assertRaises(NativeUIError):read(command,dict(packet,pagesRaw=json.dumps(pages)))

    def test_original_history_bridge_and_cross_source_disagreement_fail(self):
        for part,mutate in (
            ('nativeRaw',lambda v:v['audio']['recordedVoice'].pop('historyVersion')),
            ('settingsRaw',lambda v:v['source']['native'].update(muted=True)),
            ('settingsRaw',lambda v:v['source']['native'].update(previewCycle=1)),
            ('pagesRaw',lambda v:v.update(bridgeId='abcdef01-2345-4678-8123-456789abcdef'))):
            with self.subTest(part=part):
                command,packet=fixture();value=json.loads(packet[part]);mutate(value);packet[part]=json.dumps(value)
                with self.assertRaises((NativeUIError,ValueError)):read(command,packet)

    def test_duplicate_nonfinite_and_size_limits_fail_before_source_acceptance(self):
        command,packet=fixture()
        for raw in (' '*1048577,'{"x":1,"x":2}','{"x":NaN}'):
            with self.subTest(raw=raw[:20]),self.assertRaises((NativeUIError,ValueError)):
                bundle.validate(raw,command,123,BRIDGE,20000)
        for key,size in (('nativeRaw',262145),('settingsRaw',262145),('pagesRaw',65537)):
            with self.subTest(key=key),self.assertRaises(NativeUIError):read(command,dict(packet,**{key:' '*size}))

    def test_actual_progress_is_required_without_mutating_previous(self):
        command,packet=fixture();previous=read(command,packet);saved=deepcopy(previous)
        next_command,next_packet=fixture(10);current=read(next_command,next_packet)
        self.assertIs(current,bundle.accept(previous,current));self.assertEqual(saved,previous)
        for part,field,new_value in (('native','sequence',1),('native','instance','f'*32),
            ('settings','sequence',1),('pages','bridgeId','abcdef01-2345-4678-8123-456789abcdef')):
            with self.subTest(part=part,field=field):
                changed=deepcopy(current);changed[part][field]=new_value
                with self.assertRaises(NativeUIError):bundle.accept(previous,changed)
                self.assertEqual(saved,previous)
        with self.assertRaises(NativeUIError):bundle.accept(previous,previous)


class AudioBundleProbeTests(unittest.TestCase):
    def test_actual_probe_forwards_original_and_refuses_invalid_or_missing_hooks(self):
        source=(HERE/'probe/overte_e2e_probe.js').read_text()
        start=source.index('        if (command && command.action === "feature-pico-audio-observation-bundle")')
        end=source.index('        if (command && command.schemaVersion === 1',start+1)
        branch=source[start:end]
        command,_=fixture()
        program='''const assert=require('assert');
function objectKeysMatch(value,keys){return Object.keys(value).sort().join('|')===keys.slice().sort().join('|');}
let calls=0,saved=[];let original={commandId:COMMAND.commandId,status:'pending',actualNative:'original'};
let Test={featurePicoAudioObservationBundle(c){calls++;return original;},saveObject(v,p){saved.push([v,p]);}};
function apply(command){BRANCH}
const command=COMMAND;
apply(command);assert.strictEqual(calls,1);assert.strictEqual(saved[0][0],original);
assert.strictEqual(saved[0][1],'feature-pico-audio-observation-bundle.json');
for(const fault of [{schemaVersion:true},{nativeNonce:command.commandId},{settingsNonce:'bad'},{extra:1}]){
 const before=calls;apply({...command,...fault});assert.strictEqual(calls,before);assert.deepStrictEqual(saved.at(-1)[0],{});
}
Test.featurePicoAudioObservationBundle=undefined;apply(command);assert.deepStrictEqual(saved.at(-1)[0],{});
Test.featurePicoAudioObservationBundle=()=>({commandId:'foreign'});apply(command);assert.deepStrictEqual(saved.at(-1)[0],{});
Test.featurePicoAudioObservationBundle=()=>{throw Error('original');};apply(command);assert.deepStrictEqual(saved.at(-1)[0],{});
'''.replace('COMMAND',json.dumps(command)).replace('BRANCH',branch)
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
