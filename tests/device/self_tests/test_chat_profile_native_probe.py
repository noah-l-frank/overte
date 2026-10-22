"""Run the original probe dispatch; the native profile owner is a declared seam."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import subprocess
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from self_tests.test_native_feature_observation import probe_source


class ProfileProbeTests(unittest.TestCase):
    def test_original_probe_once_only_restore_closed_commands_and_missing_source(self):
        program=r'''
let calls=[],files=[];
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
const Test={featureChatProfile:c=>{calls.push(c);return {commandId:c.commandId,owned:true,restored:false};},
 saveObject:(v,name)=>files.push({v,name})};
SOURCE
const c={schemaVersion:1,commandId:'a'.repeat(32),runId:'b'.repeat(32),action:'feature-chat-profile',operation:'restore'};
applyClientCommand(c);applyAndroidControlCommand(c);applyClientCommand(c);
if(calls.length!==1||files.length!==1||files[0].name!=='feature-chat-profile.json'||files[0].v.restored!==false)throw Error('original replaced or resent');
for(const edit of [{history:[]},{expected:{restored:true}},{operation:'retire'},{operation:'set'},{commandId:c.commandId+'\n'},
 {runId:c.runId+'\n'},{schemaVersion:true}])applyClientCommand({...c,...edit});
if(calls.length!==1||files.length!==1)throw Error('desired or malformed command reached owner');
delete Test.featureChatProfile;const missing={...c,commandId:'c'.repeat(32)};
applyClientCommand(missing);applyClientCommand(missing);
if(calls.length!==1||files.length!==2||files[1].v.available!==false)throw Error('missing source green or retried');
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr[:2000])

    def test_native_profile_output_uses_original_private_result_writer(self):
        root=Path(__file__).resolve().parents[3]
        source=(root/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
        start=source.index('void TestScriptingInterface::saveObject(')
        private=source.index('overte::e2e::',start)
        # The integrated main branch also accepts all closed feature-*.json
        # through its tested universal writer; this packet's base uses aliases.
        self.assertIn('filename == "feature-chat-profile.json"',source[start:private])


if __name__=='__main__':unittest.main()
