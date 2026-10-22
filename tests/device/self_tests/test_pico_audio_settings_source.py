"""Explicit audio object/property boundaries; no audio engine or acoustic run."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.pico4 import audio_settings_source as audio
from adapters.normal_ui import NativeUIError
RUN='a'*32
ROOT=Path(__file__).resolve().parents[3]


class Boundary:
    def __init__(self):
        self.time=0.;self.epoch=20000;self.sequence=0;self.value=None;self.commands=[];self.alive=True;self.mutate=None
        self.properties={key:False for key in audio.BOOLEANS}
        self.properties.update({key:.5 for key in audio.NUMBERS});self.properties['context']='VR'
        self.source=dict(complete=True,hmd=True,inputPeakValuesEnabled=False,
            native=dict(recording=False,muted=False,localEcho=False,serverEcho=False,previewActive=False,previewCycle=0),
            properties=self.properties,mixerGains=dict(avatarGain=-.5,injectorGain=-.25),
            **{role+'Id':str(index+1)*32 for index,role in enumerate(audio.ROLES)})
    def clock(self):return self.epoch+round(self.time*1000)
    def send(self,request):
        self.commands.append(deepcopy(request));self.sequence+=1
        source=deepcopy(self.source);source.update({key:self.clock() for key in audio.CLOCKS})
        self.value=dict(audioSettingsVersion=1,commandId=request['commandId'],runId=request['runId'],instance='b'*32,
            sequence=self.sequence,processId=123,capturedEpochMs=self.clock(),source=source)
        if self.mutate:self.mutate(self.value)
    def read(self):return json.dumps(self.value)
    def sleep(self,amount):self.time+=amount
    def reader(self):return audio.PicoAudioSettings(self.send,self.read,self.clock,lambda:self.alive,123,
        monotonic=lambda:self.time,sleep=self.sleep)


class AudioSettingsTests(unittest.TestCase):
    def test_original_state_roles_raw_bytes_and_peak_changes_are_preserved_without_expected_effect(self):
        native=Boundary();reader=native.reader();first=reader.capture(RUN)
        native.source['inputPeakValuesEnabled']=True;native.properties['mutedHMD']=True
        second=reader.capture(RUN)
        self.assertFalse(first['source']['inputPeakValuesEnabled']);self.assertTrue(second['source']['inputPeakValuesEnabled'])
        self.assertTrue(second['source']['properties']['mutedHMD'])
        # Asynchronous script/client snapshots remain distinct original facts.
        self.assertFalse(second['source']['native']['muted'])
        self.assertEqual(native.read(),reader.last_raw);self.assertEqual(hashlib.sha256(native.read().encode()).hexdigest(),reader.last_sha256)
        self.assertEqual(first['source']['inputId'],second['source']['inputId']);self.assertEqual(2,len(native.commands))
    def test_missing_source_wrong_type_extra_expected_or_stale_per_thread_data_fails(self):
        faults=(lambda v:v['source'].update(complete=False),lambda v:v['source'].update(hmd=False),
            lambda v:v['source'].update(inputPeakValuesEnabled=1),lambda v:v['source']['properties'].update(mutedHMD=1),
            lambda v:v['source']['properties'].update(context='HMD'),lambda v:v['source']['properties'].update(inputVolume=float('nan')),
            lambda v:v['source']['mixerGains'].update(avatarGain=True),lambda v:v['source']['native'].update(previewCycle=True),
            lambda v:v['source'].update(clientCapturedEpochMs=18000),lambda v:v['source'].update(scriptCapturedEpochMs=20001),
            lambda v:v['source'].update(expectedMute=False),lambda v:v.update(available=True),
            lambda v:v['source'].update(inputId=v['source']['clientId']))
        for fault in faults:
            native=Boundary();native.mutate=fault
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):native.reader().capture(RUN)
            self.assertEqual(1,len(native.commands))
    def test_restore_binds_pid_run_roles_native_instance_and_monotone_cursors(self):
        faults=(lambda v:v.update(instance='f'*32),lambda v:v.update(processId=124),lambda v:v.update(runId='f'*32),
            lambda v:v.update(sequence=1),lambda v:v['source'].update(inputId='f'*32),
            lambda v:v['source']['native'].update(previewCycle=0))
        for fault in faults:
            native=Boundary();native.source['native']['previewCycle']=1;first=native.reader().capture(RUN)
            reader=native.reader();reader.restore(first);native.mutate=fault
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.capture(RUN)
            self.assertEqual(first,reader.previous)
    def test_final_accept_copy_guard_and_native_clock_jump_cannot_hide_source_age(self):
        for where in ('accept','copy','guard','native-guard'):
            native=Boundary();reader=native.reader();reader.clock_ms=lambda:native.epoch
            if where in ('accept','copy'):
                function='accept' if where=='accept' else 'deepcopy';original=getattr(audio,function)
                def late(*args):
                    value=original(*args);native.time+=2;return value
                with mock.patch.object(audio,function,side_effect=late):
                    with self.assertRaises(NativeUIError):reader.capture(RUN)
            else:
                calls=0
                def guard():
                    nonlocal calls
                    calls+=1
                    if calls==3:
                        if where=='guard':native.time+=2
                        else:native.epoch+=2000
                    return True
                reader.guard=guard
                with self.assertRaises(NativeUIError):reader.capture(RUN)
            self.assertIsNone(reader.previous);self.assertIsNone(reader.last_raw)
    def test_source_clock_before_requested_oversize_duplicate_keys_unavailable_and_lost_process_fail(self):
        native=Boundary();native.mutate=lambda v:v['source'].update(clientCapturedEpochMs=19999)
        with self.assertRaises(NativeUIError):native.reader().capture(RUN)
        for raw in (' '*262145,'{"commandId":"x","commandId":"x"}'):
            native=Boundary();reader=native.reader();reader.original=lambda:raw
            with mock.patch.object(audio,'decode',wraps=audio.decode) as decoder:
                with self.assertRaises(NativeUIError):reader.capture(RUN)
                if len(raw)>262144:decoder.assert_not_called()
        native=Boundary();native.mutate=lambda v:v.update(available=False)
        with self.assertRaises(NativeUIError):native.reader().capture(RUN)
        native=Boundary();native.alive=False
        with self.assertRaises(NativeUIError):native.reader().capture(RUN)
        self.assertEqual([],native.commands)
    def test_ignored_query_never_resends_and_bound_source_reuses_exact_parent_lock(self):
        from adapters.script_journey.lock import ScriptSourceLock
        import tempfile
        native=Boundary();reader=native.reader();reader.original=lambda:''
        with self.assertRaises(NativeUIError):reader.capture(RUN)
        self.assertEqual(1,len(native.commands))
        with tempfile.TemporaryDirectory() as directory:
            lock=ScriptSourceLock(Path(directory)/'sources.lock');reader=native.reader();reader.source_lock=lock
            with lock.held():reader.capture(RUN)
            self.assertIs(lock,reader.source_lock)


class AudioSettingsProbeTests(unittest.TestCase):
    def test_original_probe_keeps_payload_identity_and_closed_command_dedup(self):
        source=(ROOT/'tests/device/probe/overte_e2e_probe.js').read_text();action=source.index('command.action === "feature-audio-settings-observe"')
        start=source.rfind('        if (command &&',0,action);end=source.index('        if (command &&',action)
        harness=r'''
const assert=require('node:assert/strict');let lastAudioSettingsRequest='',saved=[],calls=[],result;
const objectKeysMatch=(value,keys)=>Object.keys(value).sort().join('|')===keys.sort().join('|');
const Test={featureAudioSettingsObservation:value=>{calls.push(value);return result;},saveObject:(value,file)=>saved.push({value,file})};
function apply(command){BODY}
const command={schemaVersion:1,commandId:'a'.repeat(32),runId:'b'.repeat(32),action:'feature-audio-settings-observe'};
result={...command,original:true};apply(command);assert.strictEqual(saved[0].value,result);apply(command);assert.equal(calls.length,1);
for (const bad of [{...command,commandId:'c'.repeat(32),expectedMuted:false},{...command,schemaVersion:true}])apply(bad);
assert.equal(calls.length,1);result=null;apply({...command,commandId:'c'.repeat(32)});
assert.equal(saved[1].value.available,false);assert.equal(saved[1].file,'feature-audio-settings.json');
'''.replace('BODY',source[start:end])
        subprocess.run(['node','-e',harness],check=True,timeout=5)


if __name__=='__main__':unittest.main()
