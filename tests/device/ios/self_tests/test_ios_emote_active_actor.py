"""Independent actor originals and publication over actual host transports."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from copy import deepcopy
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.self_tests.emote_active_observer_fixture import ActiveObserverFixture
from ios.self_tests.emote_active_actor_fixture import ActiveActorFixture


class ActiveActorTests(unittest.TestCase):
    def test_actor_acquires_own_primary_and_received_rendered_pixel_originals_then_publishes(self):
        primary=ActiveObserverFixture(self);actor=ActiveActorFixture(self,primary)
        baseline=actor.observer.observe(0);published=actor.observer.publish_latest()
        self.assertEqual('idle',baseline['state']['animation']);self.assertIsNotNone(published)
        self.assertEqual([],primary.sources.frames)
        primary.actions.act(primary.activate('play',name='Waving'));primary.native.sleep(.25)
        played=actor.observer.observe(baseline['sequence']);actor.observer.publish_latest()
        self.assertEqual('Waving',played['state']['animation']);self.assertTrue(played['state']['override'])
        original=actor.observer.original(actor.observer.state['records'][-1]);derived=actor.observer.decoder.derive(original)
        self.assertEqual(played,derived['public']);self.assertEqual(1,len(played['artifacts']))
        peer=actor.peers.frames[-1]['peer'];self.assertEqual(42,peer['receive']['processId'])
        self.assertNotEqual(peer['clockJoin']['nativeAfter']['capturedEpochMs'],actor.sources.frames[-1]['clockJoin']['nativeAfter']['capturedEpochMs'])
        self.assertTrue(actor.packet_bytes);self.assertNotIn(b'Waving',b''.join(actor.packet_bytes))
        self.assertNotEqual(str(primary.root),str(actor.root));self.assertTrue(all(row['avatarId'] for row in actor.samples.state['rows']))
        actor.sources.read();barrier=actor.observer.source_reference()
        primary.actions.act(primary.activate('cancel'))
        restored=actor.observer.observe(played['sequence'],input_barrier=barrier);actor.observer.publish_latest()
        self.assertFalse(restored['state']['override']);self.assertTrue(restored['state']['restoredBeforeNominalEnd'])
        self.assertEqual(3,len(primary.server.journal.snapshot(primary.observer.run)['entries']))

    def test_frozen_remote_renderer_cannot_be_replaced_by_real_incoming_motion_or_primary_clip(self):
        primary=ActiveObserverFixture(self);actor=ActiveActorFixture(self,primary);baseline=actor.observer.observe(0)
        actor.frozen_peer=True;primary.actions.act(primary.activate('play',name='Waving'));primary.native.sleep(.25)
        with self.assertRaises(NativeUIError):actor.observer.observe(baseline['sequence'])
        self.assertTrue(primary.rig.value['animation']['overrideActive'])
        self.assertGreater(actor.receive_sequence,1);self.assertEqual(1,len(actor.observer.state['records']))
        self.assertIsNotNone(actor.observer.state['pending']);self.assertEqual([],primary.server.journal.snapshot(actor.observer.run)['entries'])

    def test_lost_actual_actor_publication_return_reconciles_original_journal_without_resend(self):
        primary=ActiveObserverFixture(self);actor=ActiveActorFixture(self,primary);actor.observer.observe(0)
        request=actor.client.request;posts=[]
        def lost(path,value=None,*args,**kwargs):
            result=request(path,value,*args,**kwargs)
            if path.endswith('/samples'):
                posts.append(deepcopy(value));raise OSError('Modeled lost committed HTTP return')
            return result
        with patch.object(actor.client,'request',side_effect=lost),self.assertRaises(OSError):actor.observer.publish_latest()
        original=deepcopy(posts[0]);publisher=actor.observer.publisher()
        with patch.object(actor.client,'request',side_effect=lost):
            self.assertTrue(publisher.resolve());self.assertEqual(1,actor.observer.publish_latest())
        self.assertEqual([original],posts)
        self.assertEqual(original['capturedEpochMs'],primary.server.journal.snapshot(actor.observer.run)['entries'][0]['capturedEpochMs'])

    def test_foreign_actual_wire_sender_cannot_supply_the_primary_avatars_motion(self):
        primary=ActiveObserverFixture(self);actor=ActiveActorFixture(self,primary);baseline=actor.observer.observe(0)
        actor.sender_session='00000000-0000-4000-8000-000000000003'
        primary.actions.act(primary.activate('play',name='Waving'));primary.native.sleep(.25)
        with self.assertRaises(NativeUIError):actor.observer.observe(baseline['sequence'])
        self.assertIn(actor.sender_session.encode(),actor.packet_bytes[-1])
        self.assertEqual(1,len(actor.observer.state['records']));self.assertIsNotNone(actor.observer.state['pending'])


if __name__=='__main__':unittest.main()
