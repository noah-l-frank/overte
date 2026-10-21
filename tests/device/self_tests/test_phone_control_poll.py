"""Run the actual Phone private poll, marker and update code with a fake clock.

These cases qualify scheduling and nonce handling only, never native delivery.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import shutil
import subprocess
import unittest

from test_native_feature_observation import probe_source


PROBE = Path(__file__).resolve().parents[1] / 'probe/overte_e2e_probe.js'


@unittest.skipUnless(shutil.which('node'), 'Node is required for probe execution')
class PhoneControlPollTests(unittest.TestCase):
    def execute(self, scenario):
        source = PROBE.read_text()
        poll = source[source.index('    function pollAndroidControlCommand()'):
                      source.index('    function pollSoundCommand()')]
        update = source[source.index('    function updateProbe()'):
                        source.index('    Script.update.connect(updateProbe)')]
        exact = source[source.index('    function objectKeysMatch('):
                       source.index('    function httpUrl(')]
        scheduling = source[source.index('    var lastPhoneControlPollEpochMs ='):
                            source.index('    var nativeMotionUrl =')]
        program = r'''
const assert=require('assert');
let clock=10000,reads=0,legacyReads=0,markers=0,ray=0,motion=0;
let samples=[],calls=[],writes=[],command=null,readerThrows=false;
const Uuid={generate:()=>'{11111111-2222-3333-4444-555555555555}'};
const Script={require:url=>{
 if(url==='marker'){markers++;return marker;}
 legacyReads++;return command;
}};
let marker={schemaVersion:1,channel:'android-debug-file-v1',probe:'overte_e2e_probe.js',processId:123};
let Test={phoneReadFeatureCommand:()=>{reads++;if(readerThrows)throw Error('missing');return command;},
 phoneEmoteUi:request=>{calls.push(request.commandId);return {available:false,commandId:request.commandId};},
 saveObject:(value,name)=>writes.push({value,name})};
Date.now=()=>clock;
let androidControlEligible=true,androidControlAvailable=true,androidControlProcessId=123;
let androidControlMarkerUrl='marker',androidControlCommandUrl='commands',sampleSequence=0;
let lastSampleEpochMs=10000,sampleIntervalMs=250,lastHeartbeatEpochMs=10000,heartbeatIntervalMs=5000;
let nativeMotionAvailable=true,lastProbeError='',probeErrorCount=0;
function observeDispatcherRay(){ray++;}
function pollNativeMotion(){motion++;}
function observeVerticalMotion(){throw Error('native history must retain its original precedence');}
function print(){throw Error('no heartbeat due');}
function sample(now){samples.push(now);pollAndroidControlMarker();sampleSequence++;}
function input(id,control='emote.play.Waving'){
 return {schemaVersion:1,commandId:id.repeat(32),action:'phone-emote-ui',request:{
 schemaVersion:1,commandId:id.repeat(32),action:'activate',instance:'b'.repeat(32),
 generation:'c'.repeat(32),sequence:1,observedElapsedMs:0,controlId:control,controlToken:'d'.repeat(32)}};
}
''' + scheduling + exact + probe_source() + poll + update + scenario
        result = subprocess.run(['node', '-e', program], capture_output=True, text=True, timeout=5)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_distinct_commands_run_before_heavy_sample_without_replaying_input(self):
        self.execute(r'''
command=input('a');updateProbe();
for(clock=10001;clock<10250;clock++){
 if(clock===10020)command=input('e');updateProbe();
}
assert.deepEqual(calls,['a'.repeat(32),'e'.repeat(32)]);
assert.equal(reads,13);assert.deepEqual(samples,[]);assert.equal(ray,250);assert.equal(motion,250);
assert.equal(writes.length,2);assert(writes.every(row=>row.value.available===false));
clock=10250;updateProbe();assert.deepEqual(samples,[10250]);assert.equal(reads,13);
clock=10260;updateProbe();assert.equal(reads,14);assert.equal(calls.length,2);
''')

    def test_sample_and_fast_path_do_not_read_twice_at_the_same_epoch(self):
        self.execute(r'''
lastSampleEpochMs=9750;command=input('a');updateProbe();
assert.equal(reads,1);assert.deepEqual(samples,[10000]);assert.equal(calls.length,1);
updateProbe();assert.equal(reads,1);assert.equal(calls.length,1);
''')

    def test_marker_admission_precedes_fast_reads_and_invalid_marker_stays_closed(self):
        self.execute(r'''
androidControlAvailable=false;androidControlProcessId=null;command=input('a');
updateProbe();assert.equal(reads,0);assert.equal(markers,0);
marker.channel='foreign';clock=10250;updateProbe();assert.equal(reads,0);assert.equal(markers,1);
marker.channel='android-debug-file-v1';clock=10500;updateProbe();
assert.equal(markers,2);assert.equal(reads,1);assert.equal(androidControlProcessId,123);
clock=10520;command=input('e');updateProbe();assert.equal(reads,2);assert.equal(calls.length,2);
''')

    def test_non_phone_keeps_legacy_sample_polling_and_does_not_gain_fast_reads(self):
        self.execute(r'''
delete Test.phoneReadFeatureCommand;command=input('a');updateProbe();
clock=10020;updateProbe();assert.equal(legacyReads,0);assert.equal(reads,0);
clock=10250;updateProbe();assert.equal(legacyReads,1);assert.equal(calls.length,1);
clock=10270;command=input('e');updateProbe();assert.equal(legacyReads,1);
clock=10500;updateProbe();assert.equal(legacyReads,2);assert.equal(reads,0);assert.equal(calls.length,2);
''')

    def test_absent_test_api_does_not_enter_private_fast_path(self):
        self.execute(r'''
Test=undefined;updateProbe();clock=10020;updateProbe();
assert.equal(reads,0);assert.equal(legacyReads,0);assert.deepEqual(samples,[]);assert.equal(motion,2);
''')

    def test_clock_regression_rebases_without_dispatch_and_invalid_epochs_are_ignored(self):
        self.execute(r'''
command=input('a');updateProbe();clock=9000;command=input('e');updateProbe();
for(clock=9001;clock<9020;clock++)updateProbe();
assert.equal(reads,1);assert.equal(calls.length,1);
clock=9020;updateProbe();assert.equal(reads,2);assert.equal(calls.length,2);
for(const bad of [NaN,Infinity,-1,'9040',null])pollPhoneControlCommand(bad);
assert.equal(reads,2);clock=9021;updateProbe();assert.equal(reads,2);
''')

    def test_missing_and_malformed_commands_never_supply_results(self):
        self.execute(r'''
readerThrows=true;updateProbe();assert.equal(reads,1);assert.equal(writes.length,0);
readerThrows=false;
for(const mutate of [v=>null,v=>Object.assign(v,{schemaVersion:true}),
 v=>Object.assign(v,{expectedPassed:true}),v=>Object.assign(v,{commandId:'foreign'}),
 v=>{v.request.controlId='emote.play.Injected';return v;},
 v=>{v.request.commandId='e'.repeat(32);return v;}]){
 clock+=20;command=mutate(input('a'));updateProbe();
}
assert.equal(calls.length,0);assert.equal(writes.length,0);
clock+=20;command=input('a');updateProbe();assert.equal(calls.length,1);
assert.equal(writes[0].value.available,false);
''')

    def test_native_exception_is_consumed_once_and_cannot_become_delivery_success(self):
        self.execute(r'''
Test.phoneEmoteUi=request=>{calls.push(request.commandId);throw Error('ignored native input');};
command=input('a');updateProbe();clock+=20;updateProbe();
assert.equal(reads,2);assert.equal(calls.length,1);assert.equal(writes.length,1);
assert.deepEqual(writes[0],{name:'phone-emote-ui.json',value:{schemaVersion:1,commandId:'a'.repeat(32),available:false}});
''')


if __name__ == '__main__':
    unittest.main()
