"""Real private actor files and original fixture JS on explicit synthetic seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.chat_peer_input import ChatPeerInput, COMMAND, RECEIPT, command
from adapters.chat_actor_files import encode, node
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from self_tests import test_chat_actor_files as actor_seams
from self_tests.test_native_chat_observation import RUN


class PeerInputTests(unittest.TestCase):
    def setUp(self):
        self.h = actor_seams.ActorFileTests(); self.h.setUp(); self.addCleanup(self.h.doCleanups)
        self.store = PrivateFeatureState(self.h.root.parent / 'peer-input.json')
        self.peer = ChatPeerInput(self.h.transport, self.store, RUN)
        self.fd = -1; self.count = 0; self.ignored = False; self.mutate = None
        self.h.transport.sleep = self.sleep
        self.released = self.h.transport.released
        self.h.transport.released = lambda identity: False if self.fd >= 0 and node(os.fstat(self.fd)) == identity else self.released(identity)
        self.addCleanup(self.close)

    def close(self):
        if self.fd >= 0: os.close(self.fd); self.fd = -1

    def sleep(self, seconds):
        self.h.clock += seconds
        if self.ignored: return
        path = self.h.root / COMMAND; request = json.loads(path.read_bytes())
        previous = self.store.read()['receipt']
        if previous and previous['native']['commandId'] == request['commandId']: return
        self.count += 1
        temporary = self.h.root / '.native-input-result'
        fd = os.open(temporary, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
        value = dict(actorFileVersion=1, commandNode=node(path.stat()), resultNode=node(os.fstat(fd)),
            native=dict(peerInputVersion=1, commandId=request['commandId'], runId=RUN, operation=request['operation'],
                instance='d' * 32, sequence=self.count, processId=123, capturedEpochMs=20000))
        if self.mutate: self.mutate(value)
        os.write(fd, encode(value)); os.fsync(fd); os.replace(temporary, self.h.root / RECEIPT)
        self.close(); self.fd = fd

    def test_owned_consumed_inputs_remain_distinct_from_actual_position_send_or_restore_evidence(self):
        for operation, inputs in [('send', dict(channel='domain', textKey='reply')),
                ('hold', dict(position=dict(x=40, y=0, z=2))),
                ('send', dict(channel='local', textKey='hidden')), ('restore', {}), ('release', {})]:
            receipt = self.peer.issue(operation, **inputs)
            self.assertEqual(operation, receipt['operation']); self.assertNotIn('position', receipt)
            self.assertNotIn('delivered', receipt); self.assertNotIn('restored', receipt)
        self.assertEqual(5, len(self.store.read()['intents']))
        self.assertTrue(all(value['phase'] == 'consumed' for value in self.store.read()['intents']))
        with self.assertRaises(NativeUIError): self.peer.issue('send', channel='domain', textKey='hidden')
        self.assertTrue(self.store.path.exists())

    def test_consumed_send_cannot_be_reissued_under_another_nonce(self):
        self.peer.issue('send', channel='domain', textKey='reply')
        before = deepcopy(self.store.read())
        with self.assertRaises(NativeUIError): self.peer.issue('send', channel='domain', textKey='reply')
        self.assertEqual(before, self.store.read()); self.assertEqual(1, self.count)

    def test_lost_receipt_keeps_uncertain_input_and_only_allows_one_original_restoration(self):
        self.peer.issue('hold', position=dict(x=40, y=0, z=2)); self.ignored = True
        with self.assertRaises(NativeUIError): self.peer.issue('send', channel='local', textKey='hidden')
        self.assertEqual('uncertain', self.store.read()['intents'][-1]['phase'])
        before = len(self.store.read()['intents'])
        with self.assertRaises(NativeUIError): self.peer.issue('send', channel='local', textKey='hidden')
        self.assertEqual(before, len(self.store.read()['intents']))
        # The missing original command might already have been consumed. A
        # later restoration cannot assume its native counter or report success.
        self.ignored = False
        with self.assertRaises(NativeUIError): self.peer.issue('restore')
        self.assertEqual('restore', self.store.read()['intents'][-1]['command']['operation'])
        with self.assertRaises(NativeUIError): self.peer.issue('restore')

    def test_foreign_receipt_original_inode_or_actor_loss_retains_input(self):
        for fault in ('pid', 'node', 'sequence', 'instance', 'late'):
            if fault != 'pid': self.setUp()
            def mutate(value):
                if fault == 'node': value['commandNode']['inode'] = '0'
                elif fault == 'pid': value['native']['processId'] = 124
                elif fault == 'sequence': value['native']['sequence'] = 2
                elif fault == 'instance': value['native']['instance'] = 'private'
                else: value['native']['capturedEpochMs'] = 18000
            self.mutate = mutate
            with self.subTest(fault=fault), self.assertRaises(NativeUIError): self.peer.issue('send', channel='domain', textKey='reply')
            self.assertEqual('uncertain', self.store.read()['intents'][-1]['phase'])

    def test_failed_durable_intent_prevents_any_command_file(self):
        original = self.store.write
        self.store.write = lambda *_args: (_ for _ in ()).throw(OSError('injected private write failure'))
        with self.assertRaises(NativeUIError): self.peer.issue('send', channel='domain', textKey='reply')
        self.assertFalse((self.h.root / COMMAND).exists()); self.store.write = original

    def test_closed_input_inventory_rejects_arbitrary_bodies_expected_effects_and_coordinates(self):
        base = dict(schemaVersion=1, commandId='b' * 32, runId=RUN, operation='send', channel='domain', textKey='reply')
        for edit in ({'textKey':'private'}, {'expected':[]}, {'schemaVersion':True}, {'runId':'foreign'}, {'channel':'peer'}):
            with self.assertRaises(NativeUIError): command(base | edit)
        for position in ({'x':float('nan'),'y':0,'z':0}, {'x':True,'y':0,'z':0}, {'x':100001,'y':0,'z':0}):
            with self.assertRaises(NativeUIError): command(dict(schemaVersion=1, commandId='b'*32, runId=RUN, operation='hold', position=position))

    def test_original_fixture_normal_send_uses_actual_avatar_and_resumes_saved_motion(self):
        source = (Path(__file__).resolve().parents[1] / 'fixture/domain_peer_agent.js').read_text()
        program = r'''
const vm=require('vm');let update,ending,queue=[],sent=[],polls=0,point={x:2,y:0,z:2},ignore=false;
const clone=v=>JSON.parse(JSON.stringify(v));
const Avatar={displayName:''};Object.defineProperty(Avatar,'position',{get:()=>clone(point),set:v=>{if(!ignore)point=clone(v);}});
const context={Agent:{},Avatar,Messages:{featureChatActorInput:()=>{polls++;return queue.shift()||{};},sendMessage:(channel,raw)=>sent.push({channel,body:JSON.parse(raw)})},
 Script:{setInterval:()=>1,clearInterval:()=>{},resolvePath:v=>v,update:{connect:f=>update=f,disconnect:()=>{}},scriptEnding:{connect:f=>ending=f}},XMLHttpRequest:function(){}};
vm.runInNewContext(SOURCE,context);
update(.25);const original=clone(point);queue.push({operation:'hold',position:{x:40,y:0,z:2}});update(.5);update(.5);
if(point.x!==40)throw Error('actual hold overwritten by normal motion');
queue.push({operation:'send',runId:'a'.repeat(32),channel:'local',textKey:'hidden'});update(.5);
if(sent.length!==1||sent[0].channel!=='chat'||sent[0].body.position.x!==40||sent[0].body.message!=='hidden-'+'a'.repeat(32))throw Error('normal actual-position send missing');
queue.push({operation:'restore'});update(.5);if(JSON.stringify(point)!==JSON.stringify(original))throw Error('exact original not restored');
update(.25);if(Math.abs(point.x-(2+.75*Math.sin(.5)))>1e-8)throw Error('saved original motion phase not resumed');
queue.push({operation:'release'});update(.1);const released=polls;update(.1);if(polls!==released)throw Error('input poll remains active');ending();
// A refused position write must never copy requested coordinates into Send.
vm.runInNewContext(SOURCE,context);ignore=true;const actual=clone(point);
queue.push({operation:'hold',position:{x:100,y:0,z:0}});update(.1);
queue.push({operation:'send',runId:'a'.repeat(32),channel:'domain',textKey:'reply'});update(.1);
if(JSON.stringify(sent[sent.length-1].body.position)!==JSON.stringify(actual))throw Error('requested position laundered into original send');
'''.replace('SOURCE', json.dumps(source))
        result = subprocess.run(['node', '-e', program], capture_output=True, text=True, timeout=5)
        self.assertEqual(0, result.returncode, result.stderr[:2000])


if __name__ == '__main__': unittest.main()
