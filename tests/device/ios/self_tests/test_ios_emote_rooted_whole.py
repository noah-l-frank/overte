"""Actual whole coordinator/role/Node/input/PNG graph; native producers modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.self_tests.emote_rooted_whole_fixture import paired
from ios.self_tests.emote_scene_pair_fixture import local_retirement


class RootedWholeTests(unittest.TestCase):
    def test_normal_playback_both_roles_and_local_rooted_retirement_preserve_real_holders(self):
        f=paired(self);owner=f.flow;call=dict(contractVersion=16,runId=owner.run,afterSequence=0)
        first=owner.observe(call);self.assertEqual('idle',first['state']['animation'])
        peer=f.actor.flow.observe(call);self.assertEqual('idle',peer['state']['animation'])
        self.assertEqual(2,owner.previous['iosEmoteFeatureVersion'])
        self.assertEqual(3,f.target.scope.previous['iosEmoteMarkerScopeVersion'])
        self.assertEqual(2,f.actor.flow.previous['iosEmoteFeatureVersion'])
        owner.act(f.call('play',name='Waving'));f.target.native.sleep(.25)
        played=owner.observe(dict(call,afterSequence=first['sequence']))
        independently_played=f.actor.flow.observe(dict(call,afterSequence=peer['sequence']))
        self.assertEqual('Waving',played['state']['animation']);self.assertTrue(independently_played['state']['override'])
        f.call('cleanup');public=local_retirement(owner,played['sequence'])
        self.assertTrue(public['resources']);self.assertFalse(public['state']['override']);self.assertFalse(public['state']['panel'])
        self.assertEqual([],public['artifacts']);self.assertFalse(f.target.domain.running)
        self.assertFalse(f.target.domain.files.root.exists());self.assertEqual([],f.target.vm.state['timers'])
        with owner.held(30):
            parts=owner.components();keyed=owner.retirement_owner(parts)
            from ios.adapters.emote_rooted_scene_retirement import IOSEmoteRootedSceneRetirement
            actual=IOSEmoteRootedSceneRetirement(keyed).read(owner.state['cleanup'][-1])
        self.assertEqual(public,actual['public']);self.assertTrue({'qt-root','qimage','qsg-root','native-holder'}<={r['kind'] for r in actual['held']})

    def test_lost_whole_barrier_return_uses_same_actual_preinput_original_before_one_normal_send(self):
        f=paired(self);owner=f.flow;call=f.call('play',name='Waving');save=owner.save;lost=[]
        def interrupted():
            if owner.state['inputBarrier'] is not None and not lost:
                lost.append(True);raise OSError('Actual outer barrier return lost before normal send')
            return save()
        with patch.object(owner,'save',side_effect=interrupted),self.assertRaises(NativeUIError):owner.act(call)
        barrier=f.target.observer.state['phaseBarrier'];self.assertEqual([],f.target.vm.state['events'])
        owner.act(call);self.assertEqual(barrier,owner.state['inputBarrier']);self.assertEqual(1,len(f.target.vm.state['events']))
        f.target.native.sleep(.25);value=owner.observe(dict(contractVersion=16,runId=owner.run,afterSequence=0))
        self.assertEqual('Waving',value['state']['animation']);self.assertTrue(value['state']['override'])

    def test_actor_publishes_existing_scene3_after_genuine_paired_rooted_cleanup(self):
        f=paired(self);primary,actor=f.flow,f.actor.flow;call=dict(contractVersion=16,runId=primary.run,afterSequence=0)
        primary.observe(call);actor.observe(call)
        primary.act(f.call('play',name='Waving'));f.target.native.sleep(.25)
        primary.observe(call);actor.observe(call);f.call('cleanup')
        with primary.held(30):
            primary.load();primary.phase.read();primary.clean_local(primary.components())
        self.assertEqual({'performed':True},actor.cleanup(dict(contractVersion=16,runId=primary.run)))
        receipt=f.target.server.phase_retirements.snapshot(primary.run)['entries'][-1]
        self.assertEqual(3,receipt['phaseRetirementVersion']);self.assertEqual('web-marker-scene-quiet',receipt['stage'])
        self.assertEqual(['native-process-resources'],receipt['scene']['remaining']);self.assertNotIn('cleanup',receipt)
        self.assertEqual('actor-published',actor.state['retirement']['kind'])
        self.assertFalse(f.actor.target.domain.running);self.assertFalse(f.actor.target.domain.files.root.exists())
        self.assertTrue(f.actor.target.packet_bytes)


if __name__=='__main__':unittest.main()
