"""Execute actual Probe JS Source4 branch; native Qt remains uncompiled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import subprocess
import unittest

from self_tests.test_native_feature_observation import probe_source


class StreamProbeTests(unittest.TestCase):
    def node(self,body):
        program=r'''
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
let files=[],calls=[];
const Test={featurePicoRemoteAvatarStreamControl:c=>{calls.push(c);return {requestId:c.commandId,nativeOriginal:true};},
  saveObject:(v,name)=>files.push({v,name})};
SOURCE
const request={schemaVersion:1,commandId:"a".repeat(32),action:"feature-pico-remote-avatar-stream-control",
  operation:"arm",runId:"d".repeat(32),subjectSessionId:"11111111-1111-4111-8111-111111111111",ownerPolicy:"{}"};
BODY
'''.replace('SOURCE',probe_source()).replace('BODY',body)
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_actual_control_dispatch_preserves_original_once_and_never_writes_native_sample(self):
        self.node(r'''
applyAndroidControlCommand(request);applyAndroidControlCommand(request);
if(calls.length!==1||files.length!==1||files[0].v.nativeOriginal!==true
  ||files[0].name!=="feature-pico-remote-avatar-stream-control.json")throw Error("replayed or relabelled native original");
request.commandId="b".repeat(32);request.expectedPose=true;applyAndroidControlCommand(request);
if(calls.length!==1||files.length!==1)throw Error("accepted wanted effect input");
''')

    def test_actual_control_allowance_is_32_and_cannot_reset_by_new_run(self):
        self.node(r'''
for(let i=0;i<33;i++){
 request.commandId=(i+1).toString(16).padStart(32,"0");request.runId=i===32?"e".repeat(32):"d".repeat(32);
 applyAndroidControlCommand(request);
}
if(calls.length!==32||files.length!==32)throw Error("renewed or exceeded native control allowance");
if(files.some(row=>row.name!=="feature-pico-remote-avatar-stream-control.json"))throw Error("JS emitted native sample");
''')

    def test_missing_native_capability_only_records_unavailable_and_default_source3_still_uses_own_path(self):
        self.node(r'''
delete Test.featurePicoRemoteAvatarStreamControl;applyAndroidControlCommand(request);
if(files.length!==1||files[0].v.available!==false||calls.length!==0)throw Error("invented runtime capability");
let legacyCalls=0;const legacy={schemaVersion:1,requestId:"c".repeat(32),source:{actualLegacy:true}};
Test.featurePicoRemoteAvatarObservation=c=>{legacyCalls++;return legacy;};
const old={schemaVersion:1,commandId:"c".repeat(32),action:"feature-pico-remote-avatar-observe",
 runId:"d".repeat(32),subjectSessionId:"11111111-1111-4111-8111-111111111111"};
applyAndroidControlCommand(old);applyAndroidControlCommand(old);
if(legacyCalls!==1||files.length!==2||files[1].v!==legacy||files[1].name!=="feature-pico-remote-avatar.json")
 throw Error("changed legacy JS path");
''')


if __name__=='__main__':unittest.main()
