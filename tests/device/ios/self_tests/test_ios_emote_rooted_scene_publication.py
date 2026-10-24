"""Actual scene HTTP policy; native decoder and ordinary facts are models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.phase_retirement_publisher import PublicationPending
from ios.adapters.emote_rooted_feature import IOSEmoteRootedFeature
from self_tests.test_phase_web_marker_scene_quiet import WebMarkerSceneQuietTests


class RootedScenePublicationTests(unittest.TestCase):
    def setUp(self):
        self.fixture=WebMarkerSceneQuietTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.f=self.fixture.f;self.f.attach('emotes');self.facts=[]
        self.flow=object.__new__(IOSEmoteRootedFeature);self.flow.role='actor';self.flow.phase=self.f.phase
        self.first=self.fixture.scene();self.flow.state=dict(cleanup=[self.first],retirement=None)
        self.flow.retirement_publisher=lambda _parts:self.fixture.owner();self.flow.save=lambda:None
        self.parts=dict(observer=SimpleNamespace(publisher=lambda:SimpleNamespace(resolve=lambda:True),
            publish_latest=lambda:self.facts.append('actual ordinary publisher selected')))

    def test_later_same_ticket_cut_publishes_facts_without_a_second_scene_post(self):
        calls,request=self.f.posts('normal')
        with self.f.lock.held(),patch.object(self.f.actor,'request',side_effect=request):
            self.assertEqual(dict(performed=True),self.flow.publish_retirement(self.parts))
            self.flow.state['cleanup'].append(self.fixture.scene(2))
            self.assertEqual(dict(performed=True),self.flow.publish_retirement(self.parts))
        self.assertEqual(1,len(calls));self.assertEqual(2,len(self.facts))
        self.assertEqual(self.first,self.flow.state['retirement']['original'])
        journal=self.f.adapter.request('/runs/'+self.f.run+'/retirements')
        self.assertEqual(1,len(journal['entries']));self.assertEqual(1,journal['entries'][0]['actorSequence'])

    def test_lost_committed_scene_return_resolves_original_without_another_post(self):
        calls,request=self.f.posts('lost-after')
        with self.f.lock.held(),patch.object(self.f.actor,'request',side_effect=request),self.assertRaises(OSError):
            self.flow.publish_retirement(self.parts)
        self.flow.state['cleanup'].append(self.fixture.scene(2));again,request=self.f.posts('normal')
        with self.f.lock.held(),patch.object(self.f.actor,'request',side_effect=request):
            self.assertEqual(dict(performed=True),self.flow.publish_retirement(self.parts))
        self.assertEqual(1,len(calls));self.assertEqual([],again);self.assertEqual(1,len(self.facts))
        self.assertEqual(self.first,self.flow.state['retirement']['original'])

    def test_unknown_uncommitted_scene_blocks_new_cut_publication_without_resend(self):
        calls,request=self.f.posts('lost-before')
        with self.f.lock.held(),patch.object(self.f.actor,'request',side_effect=request),self.assertRaises(OSError):
            self.flow.publish_retirement(self.parts)
        self.flow.state['cleanup'].append(self.fixture.scene(2));again,request=self.f.posts('normal')
        with self.f.lock.held(),patch.object(self.f.actor,'request',side_effect=request),self.assertRaises(PublicationPending):
            self.flow.publish_retirement(self.parts)
        self.assertEqual(1,len(calls));self.assertEqual([],again);self.assertEqual([],self.facts)
        self.assertIsNone(self.flow.state['retirement'])


if __name__=='__main__':unittest.main()
