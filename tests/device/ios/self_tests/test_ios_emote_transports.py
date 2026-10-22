"""Actual fixture/probe dispatch with synthetic native hooks; never C++ build."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import subprocess
import unittest
from fixture.serve import FixtureState
from self_tests.test_native_feature_observation import probe_source
from ios.self_tests.test_ios_emote_controls import NativeBoundary
from ios.adapters.normal_input import observation


class IOSEmoteTransportTests(unittest.TestCase):
    def test_existing_native_input_parser_accepts_only_complete_original_emote_metadata(self):
        value=NativeBoundary().capture();observation(value,31,20000)
        value['controls'].append(dict(value['controls'][-1],id='emote.expected'))
        with self.assertRaises(RuntimeError):observation(value,31,20000)
    def test_existing_fixture_accepts_closed_root_and_receive_reads_only(self):
        fixture=FixtureState()
        for action in ('feature-script-roots-observe','feature-avatar-receive-observe'):
            command=dict(schemaVersion=1,commandId='ios-'+'a'*32,action=action)
            self.assertEqual(command,fixture.set_client_command(command))
            for extra in ({'expected':'Waving'},{'url':'file:///scripts/'},{'jointPose':[1,2,3]}):
                with self.assertRaises(ValueError):fixture.set_client_command(command|extra)
    def test_actual_iOS_probe_preserves_originals_deduplicates_and_rejects_requested_results(self):
        program='''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
let calls=[],files=[];
const Test={featureScriptRoots:q=>{calls.push(q);return {commandId:q.commandId,original:{clock:123,root:"file:///actual/scripts"}};},
featureAvatarReceive:q=>{calls.push(q);return {commandId:q.commandId,original:{receiveSequence:17,joints:[1,2,3]}};},
saveObject:(v,name)=>files.push({v,name})};
SOURCE
for(const [action,hook,file] of [["feature-script-roots-observe","featureScriptRoots","feature-script-roots.json"],
["feature-avatar-receive-observe","featureAvatarReceive","feature-avatar-receive.json"]]){
 let q={schemaVersion:1,commandId:"ios-"+"a".repeat(32),action};
 const before=calls.length;
 applyClientCommand(q);applyClientCommand(q);
 if(calls.length!==before+1||files.at(-1).name!==file||!files.at(-1).v.original)throw Error("lost original or replay");
 applyClientCommand({...q,commandId:"ios-"+"b".repeat(32),expected:"Waving"});
 if(calls.length!==before+1)throw Error("expected-value accepted");
 delete Test[hook];applyClientCommand({...q,commandId:"ios-"+"c".repeat(32)});
 if(files.at(-1).v.available!==false)throw Error("missing hook green");
}
'''.replace('SOURCE',probe_source())
        run=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,run.returncode,run.stderr)

if __name__=='__main__':unittest.main()
