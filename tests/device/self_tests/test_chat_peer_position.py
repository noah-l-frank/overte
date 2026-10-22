"""Original private peer-position reader/probe with synthetic native avatars."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.native_chat_peer_position import NativeChatPeerPosition, command
from adapters.normal_ui import NativeUIError
from self_tests.test_native_feature_observation import probe_source
from self_tests.test_native_chat_observation import RUN, SELF, PEER


class Boundary:
    def __init__(self):
        self.clock=0.;self.sequence=0;self.value=None;self.commands=[];self.mutate=None;self.alive=True;self.ignore=False
    def send(self,request):
        self.commands.append(deepcopy(request))
        if self.ignore:return
        self.sequence+=1
        self.value=dict(chatPeerPositionVersion=1,commandId=request['commandId'],runId=RUN,
            instance='8'*32,sequence=self.sequence,processId=123,capturedEpochMs=20000,
            source=dict(selfSha256=SELF,peerSha256=PEER,selfPosition=dict(x=0,y=0,z=0),peerPosition=dict(x=2,y=0,z=2)))
        if self.mutate:self.mutate(self.value)
    def sleep(self,seconds):self.clock+=seconds
    def reader(self):return NativeChatPeerPosition(self.send,lambda:json.dumps(self.value) if self.value else '',
        lambda:20000,lambda:self.alive,123,monotonic=lambda:self.clock,sleep=self.sleep)


class PeerPositionTests(unittest.TestCase):
    def test_actual_native_points_remain_observations_and_requested_coordinates_are_refused(self):
        n=Boundary();value=n.reader().read(RUN,SELF,PEER)
        self.assertEqual(dict(x=2,y=0,z=2),value['source']['peerPosition'])
        self.assertNotIn('position',n.commands[0])
        with self.assertRaises(NativeUIError):command(n.commands[0]|dict(position=dict(x=40,y=0,z=2)))

    def test_peer_hash_process_birth_sequence_time_and_actual_points_cannot_change(self):
        for fault in ('peer','self','pid','birth','sequence','time','private','coordinate'):
            n=Boundary();reader=n.reader();reader.read(RUN,SELF,PEER)
            def change(value):
                if fault=='peer':value['source']['peerSha256']='9'*64
                elif fault=='self':value['source']['selfSha256']=PEER
                elif fault=='pid':value['processId']=124
                elif fault=='birth':value['instance']='9'*32
                elif fault=='sequence':value['sequence']=1
                elif fault=='time':value['capturedEpochMs']=19999
                elif fault=='private':value['source']['displayName']='private'
                else:value['source']['peerPosition']['x']=True
            n.mutate=change
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read(RUN,SELF,PEER)

    def test_missing_source_late_capture_and_lost_process_never_trigger_a_second_query(self):
        for fault in ('ignore','late','dead'):
            n=Boundary()
            if fault=='ignore':n.ignore=True
            elif fault=='late':n.mutate=lambda _v:setattr(n,'clock',2)
            else:n.mutate=lambda _v:setattr(n,'alive',False)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):n.reader().read(RUN,SELF,PEER)
            self.assertEqual(1,len(n.commands))

    def test_original_probe_preserves_native_positions_and_missing_hook_is_unavailable(self):
        program=r'''
let files=[],calls=0;
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(value,keys)=>JSON.stringify(Object.keys(value).sort())===JSON.stringify(keys.sort());
const Test={featureChatPeerPosition:c=>{calls++;return {commandId:c.commandId,source:{peerPosition:{x:37,y:1,z:2}}};},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const c={schemaVersion:1,commandId:'a'.repeat(32),runId:'b'.repeat(32),action:'feature-chat-peer-position',peerSha256:'c'.repeat(64)};
applyAndroidControlCommand(c);
if(calls!==1||files[0].v.source.peerPosition.x!==37||files[0].name!=='feature-chat-peer-position.json')throw Error('native source changed');
for(const edit of [{position:{x:50,y:0,z:0}},{expected:[]},{commandId:c.commandId+'\n'},{peerSha256:c.peerSha256+'\n'},{schemaVersion:true}])applyClientCommand({...c,...edit});
if(calls!==1)throw Error('desired or malformed accepted');
delete Test.featureChatPeerPosition;applyClientCommand({...c,commandId:'d'.repeat(32)});
if(files[1].v.available!==false)throw Error('missing hook green');
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr[:2000])


if __name__=='__main__':unittest.main()
