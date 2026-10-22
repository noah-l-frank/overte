"""Actual source/control joins on synthetic Avatar/network/time boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.chat_actor_files import encode,node
from adapters.chat_peer_input import COMMAND,RECEIPT
from adapters.chat_journey.peer_distant import ChatPeerDistant
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import unpack
from feature_journeys.fixtures import context
from self_tests import test_chat_peer_send as send_seams
from self_tests import test_chat_peer_position as position_seams
from self_tests.test_native_chat_observation import RUN,PEER


class DistantTests(unittest.TestCase):
    def setUp(self):
        self.s=send_seams.PeerSendTests();self.s.setUp();self.addCleanup(self.s.doCleanups)
        self.point=dict(x=2.,y=0.,z=2.);self.original=None;self.mode='normal';self.release_time=None;self.polls=0
        self.fault=None;self.commands=[];self.s.files.sleep=self.tick
        self.pose=position_seams.Boundary()
        original_send=self.pose.send
        def send(request):
            original_send(request);self.pose.value['capturedEpochMs']=self.epoch()
            self.pose.value['source']['peerPosition']=self.actual()
            if self.fault=='foreign-pose' and self.original is not None:self.pose.value['source']['peerSha256']='9'*64
        self.pose.send=send
        sources=(self.pose.reader(),self.pose.reader())
        for source in sources:
            source.clock_ms=self.epoch;source.monotonic=lambda:self.s.clock;source.sleep=self.tick
        for boundary in (self.s.h.primary,self.s.h.peer,self.s.h.view,self.s.h.native):
            old=boundary.mutate
            def mutate(value,old=old):
                if old:old(value)
                value['capturedEpochMs']=self.epoch()
                if 'requestedEpochMs' in value:
                    value['requestedEpochMs']=self.epoch()
                    if value.get('animationFence'):value['animationFence']['requestedEpochMs']=self.epoch()
            boundary.mutate=mutate
        for role in self.s.owner.roles:
            role.monotonic=lambda:self.s.clock
            for reader in (role.primary,role.peer,role.view,role.lifecycle):reader.clock_ms=self.epoch
        self.s.files.clock_ms=self.epoch
        self.store=PrivateFeatureState(self.s.h.root/'distant.json')
        self.owner=ChatPeerDistant(self.s.owner,sources,self.store,monotonic=lambda:self.s.clock,sleep=self.sleep)

    def epoch(self):return 20000+int(self.s.clock*1000)
    def actual(self):
        if self.mode=='moving':return dict(x=2+.75*math.sin(self.s.clock-self.release_time),y=0.,z=2.)
        return deepcopy(self.point)
    def sleep(self,seconds):self.s.clock+=seconds

    def tick(self,seconds):
        self.s.clock+=seconds;request=json.loads((self.s.root/COMMAND).read_bytes());self.commands.append(request['operation'])
        self.s.issued+=1;operation=request['operation'];point=self.actual()
        if self.mode!='moving' or self.fault=='poll-leak':self.polls+=1
        temporary=self.s.root/'.receipt';fd=os.open(temporary,os.O_RDWR|os.O_CREAT|os.O_EXCL,0o600)
        receipt=dict(actorFileVersion=1,commandNode=node((self.s.root/COMMAND).stat()),resultNode=node(os.fstat(fd)),
            native=dict(peerInputVersion=3,commandId=request['commandId'],runId=RUN,operation=operation,
                instance='8'*32,sequence=self.s.issued,processId=456,capturedEpochMs=self.epoch(),
                avatarSha256=PEER,avatarPosition=point,scriptPolls=self.polls,releaseConsumed=self.mode=='moving' or operation=='release'))
        os.write(fd,encode(receipt));os.fsync(fd);os.replace(temporary,self.s.root/RECEIPT);self.s.close();self.s.fd=fd
        if operation=='hold':self.original=point;self.point=deepcopy(request['position']);self.mode='held'
        elif operation=='restore':self.point=deepcopy(self.original);self.mode='restored'
        elif operation=='release':self.mode='moving';self.release_time=self.s.clock
        elif operation=='send':
            if self.fault=='accepted':self.s.h.accept(context(RUN)['hidden'],channel='local')
            else:self.s.h.primary.event(text=context(RUN)['hidden'],channel='local')
            self.s.h.peer.event(text=context(RUN)['hidden'],channel='local')

    def test_actual_distance_send_rejection_exact_original_return_motion_and_poll_quiet(self):
        for key in ('unicode','reply','hidden'):
            self.s.h.accept(context(RUN)[key])
        self.s.h.accept(context(RUN)['reply'],channel='local')
        result=self.owner.run(20000)
        self.assertEqual('complete',result['phase']);self.assertEqual(dict(x=2.,y=0.,z=2.),result['original'])
        self.assertEqual(1,self.commands.count('hold'));self.assertEqual(1,self.commands.count('send'))
        self.assertEqual(1,self.commands.count('restore'));self.assertEqual(1,self.commands.count('release'))
        originals=unpack(result['transcript']);self.assertGreater(len(originals),30)
        self.assertTrue(any(value['positions'][0]['source']['peerPosition']['x']==40 for value in originals))
        self.assertTrue(any(value['avatars'][0]['avatarPosition']==result['original'] for value in originals))
        self.assertTrue(self.store.path.exists());self.assertTrue(self.s.input.store.path.exists())
        with self.assertRaises(NativeUIError):self.owner.run(20000)

    def test_accepted_distant_local_row_fails_and_attempts_original_restore_release_once(self):
        self.fault='accepted'
        with self.assertRaises(NativeUIError):self.owner.run(20000)
        self.assertEqual(1,self.commands.count('send'));self.assertEqual(1,self.commands.count('restore'))
        self.assertEqual(1,self.commands.count('release'));self.assertNotEqual('complete',self.store.read()['phase'])

    def test_foreign_native_peer_position_blocks_send_without_skipping_restoration(self):
        self.fault='foreign-pose'
        with self.assertRaises(NativeUIError):self.owner.run(20000)
        self.assertNotIn('send',self.commands);self.assertEqual(1,self.commands.count('restore'))
        self.assertEqual(1,self.commands.count('release'));self.assertTrue(self.store.path.exists())

    def test_actual_native_poll_leak_after_release_cannot_pass_a_fresh_quiet_window(self):
        self.fault='poll-leak'
        with self.assertRaises(NativeUIError):self.owner.run(20000)
        self.assertEqual(1,self.commands.count('send'));self.assertEqual(1,self.commands.count('restore'))
        self.assertEqual(1,self.commands.count('release'));self.assertNotEqual('complete',self.store.read()['phase'])

    def test_requested_coordinate_cannot_replace_either_actual_position_source(self):
        _observed,frame=self.owner.measure(20000)
        distant=dict(x=40.,y=0.,z=0.)
        for point in frame['positions']:point['source']['peerPosition']=distant
        self.assertFalse(ChatPeerDistant.distant(frame))
        for point in frame['positions']:point['source']['peerPosition']=dict(x=2.,y=0.,z=2.)
        for avatar in frame['avatars']:avatar['avatarPosition']=distant
        self.assertFalse(ChatPeerDistant.distant(frame));self.assertNotIn('send',self.commands)


if __name__=='__main__':unittest.main()
