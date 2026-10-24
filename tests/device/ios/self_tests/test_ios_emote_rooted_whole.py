"""Actual whole coordinator/role/Node/input/PNG graph; native producers modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from copy import copy
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
        f.call('cleanup')
        with (patch.object(owner,'rendered_retirement_owner',wraps=owner.rendered_retirement_owner) as rendered_factory,
              patch.object(owner,'retirement_owner',wraps=owner.retirement_owner) as keyed_factory):
            public=local_retirement(owner,played['sequence'])
        native_arguments=[call.kwargs['native'] for call in rendered_factory.call_args_list if 'native' in call.kwargs]
        keyed_arguments=[call.kwargs for call in keyed_factory.call_args_list if 'rendered' in call.kwargs]
        self.assertTrue(native_arguments);self.assertTrue(keyed_arguments)
        for arguments in keyed_arguments:
            self.assertTrue(any(arguments['rendered'].native_owner is native for native in native_arguments))
            self.assertIsNotNone(arguments['keys'])
        self.assertTrue(public['resources']);self.assertFalse(public['state']['override']);self.assertFalse(public['state']['panel'])
        self.assertEqual([],public['artifacts']);self.assertFalse(f.target.domain.running)
        self.assertFalse(f.target.domain.files.root.exists());self.assertEqual([],f.target.vm.state['timers'])
        with owner.held(30):
            parts=owner.components();keyed=owner.retirement_owner(parts)
            from ios.adapters.emote_rooted_scene_retirement import IOSEmoteRootedSceneRetirement
            actual=IOSEmoteRootedSceneRetirement(keyed).read(owner.state['cleanup'][-1])
        self.assertEqual(public,actual['public']);self.assertTrue({'qt-root','qimage','qsg-root','native-holder'}<={r['kind'] for r in actual['held']})
        # Reuse is limited to this exact live component and SDK/candidate.
        # No copied value, historical reader or stale source guard may enter.
        native=keyed.rendered_owner.native_owner
        for change in (dict(historical=True),dict(binding=dict(native.binding,processIdentity='99')),
                       dict(phase_instance='e'*32),dict(guard=lambda:False)):
            foreign=copy(native)
            for name,value in change.items():setattr(foreign,name,value)
            with self.subTest(changed=list(change)),owner.held(30),self.assertRaises(NativeUIError):
                owner.rendered_retirement_owner(parts,native=foreign)

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
        from ios.adapters.emote_rooted_live import IOSEmoteRootedLive
        for flow in (primary,actor):
            with flow.held(30):
                flow.load();parts=flow.components();live=IOSEmoteRootedLive(flow.retirement_owner(parts))
                self.assertIsNone(live.state['pending']);self.assertTrue(live.state['records'])
                reference=live.state['records'][-1];row=live.record(reference)
                frame=live.originals.read(live.originals.expand(reference))
                self.assertEqual(flow.state['cleanup'][-1],frame['snapshot']['reference'])
                self.assertEqual([r['resource'] for r in row['measurement']['held']],row['measurement']['public']['resources'])


if __name__=='__main__':unittest.main()
