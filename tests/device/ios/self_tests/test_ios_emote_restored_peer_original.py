"""Actual normal JS/W3C/UDP/PNG owner joins; native/SDK producers are models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import partial
import os
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import BLOCK
from ios.adapters.emote_observation import IOSEmoteObservationDecoder
from ios.adapters.emote_rooted_observation import IOSEmoteRootedObservationDecoder
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters import emote_peer_continuation as continuation
from ios.self_tests.test_ios_emote_peer import reseal
from ios.self_tests import emote_script_vm_fixture as vm_fixture
from ios.self_tests import emote_active_observer_fixture as native_fixture
from ios.self_tests.emote_animation_fixture import bundled_frames
from ios.self_tests.emote_rooted_whole_fixture import paired


class RestoredPeerOriginalTests(unittest.TestCase):
    def normal_restore(self):
        frames=bundled_frames()
        with (patch.object(vm_fixture,'ActualEmoteVM',partial(vm_fixture.ActualEmoteVM,frame_counts=frames)),
              patch.object(native_fixture,'ActualVMRig',partial(native_fixture.ActualVMRig,pose_profile='requested-clip'))):
            f=paired(self,retain_originals=True)
        primary,actor=f.flow,f.actor.flow;target=f.actor.target
        call=dict(contractVersion=16,runId=primary.run,afterSequence=0)
        primary.observe(call);actor.observe(call);actor.sleep=target.domain.sleep
        primary.act(f.call('play',name='Crying'));f.target.native.sleep(.25)
        playing=actor.observe(call);self.assertTrue(playing['state']['override'])
        owner=target.observer;anchor=deepcopy(owner.state['records'][-1]);actual=owner.original(anchor)
        self.assertEqual(1,actual['iosEmoteObservationOriginalVersion']);self.assertEqual('playback',actual['proof']['kind'])
        primary.act(f.call('cancel'))
        restored=actor.observe(call);original=owner.original(owner.state['records'][-1])
        self.assertFalse(restored['state']['override']);self.assertEqual(3,original['iosEmoteObservationOriginalVersion'])
        self.assertEqual(anchor,original['peerContinuation'])
        return f,owner,anchor,restored,original

    def test_normal_cancel_and_later_quiet_cut_keep_actual_original_pose_without_new_motion_claim(self):
        f,owner,anchor,restored,_original=self.normal_restore()
        events=deepcopy(f.target.vm.state['events']);inputs=deepcopy(f.target.native.requests)
        reader=f.target.rig.reader()
        for _ in range(36):reader.read(reader.sequence)
        later=f.actor.flow.observe(dict(contractVersion=16,runId=f.flow.run,afterSequence=restored['sequence']))
        current=owner.original(owner.state['records'][-1])
        self.assertEqual(3,current['iosEmoteObservationOriginalVersion']);self.assertEqual(anchor,current['peerContinuation'])
        self.assertFalse(later['state']['override']);self.assertEqual('idle',later['state']['animation'])
        self.assertTrue(later['artifacts']);self.assertTrue(f.actor.target.packet_bytes)
        self.assertEqual(events,f.target.vm.state['events']);self.assertEqual(inputs,f.target.native.requests)
        with f.actor.flow.held(30):self.assertEqual(later,owner.decoder.derive(current)['public'])

    def test_restored_profile_rejects_missing_future_self_changed_episode_and_nonfresh_cut(self):
        f,owner,_anchor,_restored,original=self.normal_restore()
        with f.actor.flow.held(30):
            current=owner.decoder.source(original['source'])
            after=owner.decoder.retained(owner.peers,original['peerAfter'])
            before=owner.decoder.retained(owner.peers,original['peerBefore'])
            proof=continuation.restored_derive(owner.decoder,original,current,after)
            self.assertGreater(proof['receivedSequences'][0],before['peer']['receive']['source']['receiveSequence']+1)
            self.assertEqual(after['peer']['receive']['source']['receiveSequence'],proof['receivedSequences'][-1])
            for fault in ('last-active','only-one-neutral','last-foreign'):
                changed=deepcopy(after);rows=changed['peer']['receive']['source']['records']
                if fault=='last-foreign':rows[-1]['avatarSha256']='f'*64
                else:rows[-1 if fault=='last-active' else -2]['joints'][0]['translation'][0]+=.25
                reseal(changed['peer'])
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):
                    continuation.restored_derive(owner.decoder,original,current,changed)
            for fault in ('hash','self','future','episode','same-cut','new-play'):
                value=deepcopy(original)
                if fault=='hash':value['peerContinuation']['sha256']='f'*64
                elif fault=='self':value['peerContinuation']['index']=value['sequence']
                elif fault=='future':value['peerContinuation']['index']=value['sequence']+1
                elif fault=='episode':value['proof']['played']=value['source']
                elif fault=='same-cut':value['peerBefore']=value['peerAfter']
                else:value['proof']['kind']='playback'
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):owner.decoder.derive(value)
            ordinary=object.__new__(IOSEmoteObservationDecoder)
            with self.assertRaises(NativeUIError):ordinary.original_shape(original)
            wrong=object.__new__(IOSEmoteRootedObservationDecoder);wrong.role='primary'
            with self.assertRaises(NativeUIError):wrong.original_shape(original)

    def test_same_byte_baseline_inode_replacement_is_rejected_by_the_actual_original_lease(self):
        f,owner,anchor,_restored,original=self.normal_restore()
        with f.actor.flow.held(30):
            playback=owner.original(anchor);reference=playback['peerBefore'];actual=owner.peers.originals
            manifest=actual.manifest(owner.peers.state['manifests'][(reference['index']-1)//BLOCK])
            path=actual.path(actual.expand(manifest[(reference['index']-1)%BLOCK]))
            lease=EmoteOriginalLease(owner.root,[]);owner.decoder.derive(original);lease.guard()
            raw=path.read_bytes();inode=path.stat().st_ino;replacement=path.with_suffix('.replacement')
            replacement.write_bytes(raw);replacement.chmod(0o600);os.replace(replacement,path)
            self.assertEqual(raw,path.read_bytes());self.assertNotEqual(inode,path.stat().st_ino)
            with self.assertRaises(NativeUIError):lease.guard()

    def test_fresh_wrong_remote_render_pose_cannot_become_an_original_restored_peer(self):
        f,_owner,_anchor,_restored,_original=self.normal_restore();target=f.actor.target
        inputs=deepcopy(f.target.native.requests);events=deepcopy(f.target.vm.state['events'])
        target.frozen_peer=True;target.remote_pose[0][4]+=.25
        with self.assertRaises(NativeUIError):f.actor.flow.observe(dict(contractVersion=16,runId=f.flow.run,afterSequence=0))
        self.assertEqual(inputs,f.target.native.requests);self.assertEqual(events,f.target.vm.state['events'])

    def test_fresh_foreign_udp_sender_cannot_borrow_the_original_playback_baseline(self):
        f,_owner,_anchor,_restored,_original=self.normal_restore();target=f.actor.target
        from ios.self_tests.test_ios_avatar_renderers import PEER
        inputs=deepcopy(f.target.native.requests);events=deepcopy(f.target.vm.state['events'])
        target.sender_session=PEER
        with self.assertRaises(NativeUIError):f.actor.flow.observe(dict(contractVersion=16,runId=f.flow.run,afterSequence=0))
        self.assertEqual(inputs,f.target.native.requests);self.assertEqual(events,f.target.vm.state['events'])


if __name__=='__main__':unittest.main()
