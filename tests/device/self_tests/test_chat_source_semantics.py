"""Original Chat JS on explicit message/native seams; no product/device verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[3]
PROGRAM=r'''
const assert=require('node:assert/strict'),path=require('node:path');
const root=process.argv[1],mode=process.argv[2];
const {FakeSignal,createScriptApi,createTabletApi,createMessagesApi,runProductionScript}=require(path.join(root,'tests/javascript/support'));
const Script=createScriptApi(),Tablet=createTabletApi(),Messages=createMessagesApi();
const tablet=Tablet.getTablet('com.highfidelity.interface.tablet.system'),values=new Map();
tablet.toolbarMode=false;tablet.tabletShown=true;
const remote=[],local=[];let mixer=true;
// Explicit synthetic native seam: no-mixer local delivery is source-reviewed
// MessagesClient behavior, not execution/qualification of that C++ producer.
Messages.sendMessage=(channel,message,localOnly=false)=>{
 const data=JSON.parse(message);
 if(channel==='chat') { if(mixer&&!localOnly)remote.push(data);else local.push(data); }
 if(Messages.subscriptions.has(channel))Messages.messageReceived.emit(channel,message,'self',localOnly||!mixer);
};
Messages.sendLocalMessage=(channel,message)=>Messages.sendMessage(channel,message,true);
runProductionScript(path.join(root,'scripts/communityScripts/armored-chat/armored_chat.js'),{
 Script,Tablet,Messages,PlatformInfo:{getComputer:()=>JSON.stringify({OS:'ANDROID'})},HMD:{active:false},
 Settings:{getValue:(key,fallback)=>values.has(key)?values.get(key):fallback,setValue:(key,value)=>values.set(key,value)},
 Controller:{keyPressEvent:new FakeSignal()},MyAvatar:{position:{x:0,y:0,z:0},sessionDisplayName:'Controlled'},
 AvatarManager:{getPalData:()=>({data:[]}),avatarAddedEvent:new FakeSignal()},Users:{avatarDisconnected:new FakeSignal()},
 Vec3:{distance:(a,b)=>Math.hypot(a.x-b.x,a.y-b.y,a.z-b.z)},console:{log:()=>{}}
});
const open=()=>{tablet.buttons[0].click();tablet.fromQml.emit({type:'initialized'});};
const send=text=>tablet.fromQml.emit({type:'send_message',message:text,channel:'domain'});
const receive=(text,channel,position={x:0,y:0,z:0})=>Messages.injectMessage('chat',JSON.stringify({
 action:'send_chat_message',message:text,channel,position,displayName:'Actual peer'}));
const history=()=>Array.from(values.get('ArmoredChat-Messages')||[],row=>row.message);
open();
if(mode==='fallback'){
 mixer=false;send('retry-run');assert.deepEqual(history(),['retry-run']);assert.equal(remote.length,0);assert.equal(local.length,1);
 mixer=true;for(const id of Array.from(Script.timers.keys()))Script.runTimer(id);assert.equal(remote.length,0); // no queued work in original script
 send('retry-run');assert.deepEqual(history(),['retry-run','retry-run']);assert.equal(remote.length,1);
 assert.equal(remote[0].message,'retry-run');
}else if(mode==='channels'){
 receive('domain hidden by Local tab','domain');receive('near','local',{x:19.99,y:0,z:0});
 receive('boundary','local',{x:20,y:0,z:0});receive('distant rejected','local',{x:20.01,y:0,z:0});
 assert.deepEqual(history(),['domain hidden by Local tab','near','boundary']);
 assert.deepEqual(Array.from(tablet.qmlMessages.filter(row=>row.type==='show_message'),row=>row.channel),['domain','local','local']);
}else if(mode==='history'){
 send('Overte ä Ω 東京 run');tablet.gotoHomeScreen();const before=tablet.qmlMessages.length;
 receive('while closed','domain');assert.equal(tablet.qmlMessages.length,before);open();
 const replay=tablet.qmlMessages.slice(before);
 assert.equal(replay.filter(row=>row.type==='clear_messages').length,1);
 assert.deepEqual(Array.from(replay.filter(row=>row.type==='show_message'),row=>row.message),['Overte ä Ω 東京 run','while closed']);
}else throw Error('Unknown closed test mode');
Script.end();assert.equal(Messages.subscriptions.size,0);assert.equal(tablet.buttons.length,0);
process.stdout.write('original-script-boundary-pass');
'''


class ChatSourceSemantics(unittest.TestCase):
    def original(self,mode):
        result=subprocess.run(['node','-e',PROGRAM,str(ROOT),mode],capture_output=True,text=True,timeout=10)
        self.assertEqual(0,result.returncode,result.stderr)
        self.assertEqual('original-script-boundary-pass',result.stdout)

    def test_original_script_keeps_local_fallback_and_does_not_queue_replay(self):self.original('fallback')
    def test_original_script_retains_both_channels_and_rejects_distant_local_sender(self):self.original('channels')
    def test_original_script_replays_actual_unicode_history_once_after_reopen(self):self.original('history')


if __name__=='__main__':unittest.main()
