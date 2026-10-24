"""Normal paired cleanup and original scene ordering; SDK/native are models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest

from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import unpack
from feature_journeys.witness import Client
from ios.adapters.emote_rooted_feature import IOSEmoteRootedFeature
from ios.self_tests.emote_rooted_whole_fixture import paired


class RootedRepeatedCleanupTests(unittest.TestCase):
    def test_repeated_normal_primary_cleanup_retains_one_scene_receipt_and_new_role_originals(self):
        f=paired(self,retain_originals=True);primary,actor=f.flow,f.actor.flow
        observe=dict(contractVersion=16,runId=primary.run,afterSequence=0)
        primary.observe(observe);actor.observe(observe)
        primary.act(f.call('play',name='Waving'));f.target.native.sleep(.25)
        self.assertTrue(primary.observe(observe)['state']['override'])
        self.assertTrue(actor.observe(observe)['state']['override'])
        f.call('cleanup');cleanup=dict(contractVersion=16,runId=primary.run);admissions=[]

        def waiting(seconds):
            if primary.lock._owner is None and primary.primary_lock._owner is None:
                self.assertIsNone(actor.lock._owner);admissions.append(True)
                actor.cleanup(cleanup)
            f.target.domain.sleep(seconds)
        primary.sleep=waiting
        self.assertEqual(dict(performed=True),primary.cleanup(cleanup))
        self.assertTrue(admissions);self.assertEqual('primary-scene-ordered',primary.state['retirement']['kind'])
        first=deepcopy(primary.state['retirement']);first_actor=deepcopy(actor.state['cleanup'][-1])
        first_public=deepcopy(first['peerReceipt']['entry'])
        self.assertEqual(3,first_public['phaseRetirementVersion'])
        self.assertEqual('web-marker-scene-quiet',first_public['stage'])
        before=len(f.target.native.requests)
        print('First normal Primary cleanup joined the actual once-only Actor scene receipt',flush=True)

        # The independent worker acquires a new real cleanup cut after the
        # original scene is older than its ordinary 1500-ms freshness lease.
        # Only this historical scene-order owner can reuse that old receipt.
        f.target.domain.sleep(2)
        self.assertEqual(dict(performed=True),actor.cleanup(cleanup))
        self.assertEqual(dict(performed=True),primary.cleanup(cleanup))
        self.assertGreater(primary.state['retirement']['original']['index'],first['original']['index'])
        self.assertGreater(actor.state['cleanup'][-1]['index'],first_actor['index'])
        self.assertEqual(first_public,primary.state['retirement']['peerReceipt']['entry'])
        self.assertEqual(before,len(f.target.native.requests))
        self.assertIsNone(primary.lock._owner);self.assertIsNone(actor.lock._owner)

        witness=Client(f.target.client.url,'r'*64)
        journal=witness.request('/runs/'+primary.run+'/retirements')
        self.assertEqual([first_public],journal['entries'])
        order=PrivateFeatureState(primary.store.path.with_name('ios-emote-primary-scene-order-'+primary.run+'.json')).read()
        self.assertEqual(1,order['iosEmoteSceneOrderVersion'])
        self.assertEqual(3,order['reader']['phaseRetirementReaderVersion'])
        records=unpack(order['reader']['payload'])[0]['records']
        self.assertGreaterEqual(len(records),2)
        self.assertTrue(all(row['entry']==first_public for row in records))
        self.assertGreater(primary.epoch_ms()-first_public['scene']['capturedEpochMs'],1500)
        print('Repeated normal cleanup retained the original scene epoch and acquired advancing role cuts',flush=True)

        # Exercise the actual production constructor against the retained role
        # metadata. Fixture Flow subclasses still own the modeled transports;
        # this exact facade does not prepare/query an SDK or fabricate a root.
        facade=IOSEmoteRootedFeature(primary.runtime,primary.selector,primary.client,primary.run,'primary',
            primary.root,primary.policy,actor_selector=primary.actor_selector,monotonic=primary.monotonic,
            epoch_ms=primary.epoch_ms,sleep=primary.sleep)
        facade.lock=facade.primary_lock=primary.lock
        terminal=primary.runtime._emote_rooted_terminal(facade)
        self.assertEqual(actor.root,terminal.actor.root);self.assertEqual(actor.policy,terminal.actor.policy)
        self.assertIs(terminal.actor.primary_lock,primary.lock)
        self.assertEqual(before,len(f.target.native.requests))


if __name__=='__main__':unittest.main()
