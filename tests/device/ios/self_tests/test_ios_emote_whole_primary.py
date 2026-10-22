"""Whole local Emote coordination; native/SDK producers remain modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.self_tests.emote_whole_primary_fixture import WholePrimaryFixture


class WholePrimaryTests(unittest.TestCase):
    def test_first_direct_act_binds_real_initial_barrier_before_input_and_repeat_keeps_it(self):
        f=WholePrimaryFixture(self);owner=f.flow;call=f.call('play',name='Waving')
        owner.act(call);barrier=owner.state['inputBarrier'];before=len(f.target.native.requests)
        owner.act(call);self.assertEqual(before,len(f.target.native.requests));self.assertEqual(barrier,owner.state['inputBarrier'])
        f.target.native.sleep(.25);played=owner.observe(dict(contractVersion=16,runId=owner.run,afterSequence=0))
        self.assertEqual('Waving',played['state']['animation']);self.assertEqual(barrier,f.target.observer.state['phaseBarrier'])
        self.assertGreater(barrier['index'],f.target.observer.state['baseline']['index'])
        actual=f.target.observer.decoder.source(barrier)
        self.assertFalse(actual['group']['native']['animation']['overrideActive'])

    def test_lost_outer_barrier_metadata_before_first_send_adopts_the_same_actual_original(self):
        f=WholePrimaryFixture(self);owner=f.flow;call=f.call('play',name='Waving');save=owner.save;lost=[]
        def interrupted():
            if owner.state['inputBarrier'] is not None and not lost:
                lost.append(True);raise OSError('Modeled interruption before feature barrier metadata write')
            return save()
        with patch.object(owner,'save',side_effect=interrupted),self.assertRaises(NativeUIError):owner.act(call)
        barrier=f.target.observer.state['phaseBarrier'];self.assertEqual([],f.target.vm.state['events'])
        owner.act(call);self.assertEqual(barrier,owner.state['inputBarrier']);self.assertEqual(1,len(f.target.vm.state['events']))
        f.target.native.sleep(.25);played=owner.observe(dict(contractVersion=16,runId=owner.run,afterSequence=0))
        self.assertTrue(played['state']['override']);self.assertEqual('Waving',played['state']['animation'])

    def test_real_actions_observation_and_complete_native_rendered_retirement(self):
        f=WholePrimaryFixture(self);owner=f.flow
        baseline=owner.observe(dict(contractVersion=16,runId=owner.run,afterSequence=0))
        self.assertEqual('idle',baseline['state']['animation'])
        owner.act(f.call('play',name='Waving'));f.target.native.sleep(.25)
        played=owner.observe(dict(contractVersion=16,runId=owner.run,afterSequence=0))
        self.assertEqual('Waving',played['state']['animation']);self.assertTrue(played['state']['override'])
        f.call('cleanup')
        with owner.held(30):
            owner.load();owner.phase.read();parts=owner.components();owner.clean_local(parts)
            public=owner.retirement_sample(parts,played['sequence'])
            derived=owner.retirement_owner(parts).derive(owner.state['cleanup'][-1])
        self.assertEqual(public,derived['public']);self.assertEqual([],public['resources']);self.assertEqual([],public['artifacts'])
        self.assertFalse(public['state']['override']);self.assertFalse(public['state']['panel'])
        self.assertEqual('released',f.target.scope.state['phase']);self.assertFalse(f.target.domain.running)
        self.assertEqual([],f.target.vm.state['timers']);self.assertEqual('restoreAnimation',f.target.vm.state['events'][-1]['method'])
        self.assertFalse(f.target.domain.files.root.exists());self.assertTrue(f.pointer.boundary.events)


if __name__=='__main__':unittest.main()
