"""Typed publisher mutations cannot exempt original files or final expiry."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.phase_retirement_publisher import PhaseRetirementPublisher
from adapters.original_publication_delivery import delivery
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.retirement_receipts import WEB_SCENE_STAGE
from ios.adapters.world_web_observer import WorldWebObserver
from ios.adapters.world_web_actor_retirement import WorldWebActorRetirement
from ios.self_tests.world_web_actor_fixture import IndependentActor
from ios.self_tests.world_web_network_fixture import NetworkWorldWeb


class WorldWebPublicationRoundTests(unittest.TestCase):
    @contextmanager
    def fixture(self):
        network=NetworkWorldWeb(use_whole_snapshot=True)
        try:
            whole=network.whole;actor=IndependentActor(whole)
            try:
                observer=WorldWebObserver(PrivateFeatureState(actor.root/'ios-world-web-actor-observer.json'),actor.primary,whole.sdk.origins,lambda:True,role='actor',peer=actor.peer)
                observer.capture();retirement=WorldWebActorRetirement(PrivateFeatureState(actor.root/'ios-world-web-actor-retirement.json'),observer,sleep=whole.sdk.sleep)
                phase=PhaseFixtureReader(network.actor,network.run,'world-web',epoch_ms=whole.sdk.host_epoch,monotonic=lambda:whole.sdk.time);phase.read()
                publisher=PhaseRetirementPublisher(PrivateFeatureState(actor.root/('phase-retirement-world-web-'+network.run+'-actor.json')),actor.sdk.binding,phase,actor.lock,lambda:True,
                    retirement.validate_original,stage=WEB_SCENE_STAGE,epoch_ms=whole.sdk.host_epoch,monotonic=lambda:whole.sdk.time)
                posts=[];request=phase.client.request
                def counted(path,*args,**kwargs):
                    if path.endswith('/retirements') and (args or kwargs.get('body') is not None):posts.append(deepcopy((path,args,kwargs)))
                    return request(path,*args,**kwargs)
                phase.client.request=counted
                yield whole,actor,observer,retirement,publisher,posts
            finally:actor.close()
        finally:network.close()
    def test_actual_typed_journal_CAS_can_change_inode_while_all_source_originals_remain_fixed(self):
        with self.fixture() as (_whole,_actor,_observer,retirement,publisher,posts):
            before=publisher.store.path.stat().st_ino
            with retirement.publication_round(publisher):publisher.save()
            self.assertNotEqual(before,publisher.store.path.stat().st_ino);self.assertEqual([],posts)
    def test_journal_or_source_inode_sameinode_history_context_and_unrecorded_record_change_block_before_HTTP(self):
        for fault in ('journal-swap','source-swap','source-same-inode','context','unrecorded-record'):
            with self.subTest(fault=fault),self.fixture() as (_whole,_actor,observer,retirement,publisher,posts):
                source=observer.source;frame=source.frame(source.state['records'][0]);path=source.parts.snapshot.paths(frame['nativeSnapshot'])[0]
                with self.assertRaises(NativeUIError):
                    with retirement.publication_round(publisher):
                        if fault in ('journal-swap','source-swap'):
                            target=publisher.store.path if fault=='journal-swap' else path
                            replacement=target.with_suffix('.replacement');replacement.write_bytes(target.read_bytes());replacement.chmod(0o600);replacement.replace(target)
                        elif fault=='source-same-inode':path.write_bytes(path.read_bytes())
                        elif fault=='context':observer.origins['primary']='http://changed.invalid'
                        else:publisher.record_store(1).write({'unrecorded':'planned'},None)
                        publisher.phase.client.request('/runs/'+publisher.run+'/retirements',{'notASubstituteForFacts':True})
                self.assertEqual([],posts)
    def test_expiry_after_actual_last_CAS_save_refuses_before_HTTP_without_resetting_original_clock(self):
        with self.fixture() as (whole,_actor,observer,retirement,publisher,posts):
            entry=observer.entries()[-1];clock=observer.derive(entry)['acquisition'];before=deepcopy(clock)
            with self.assertRaises(NativeUIError):
                with retirement.publication_round(publisher):
                    publisher.save();whole.sdk.sleep(2)
                    with delivery(publisher,clock):publisher.phase.client.request('/runs/'+publisher.run+'/retirements',{'notASubstituteForFacts':True})
            self.assertEqual(before,clock);self.assertEqual([],posts)


if __name__=='__main__':unittest.main()
