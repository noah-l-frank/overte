"""Real canonical witness POST and original files across a modeled restart."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from feature_journeys.witness import Client
from ios.self_tests import test_ios_navigation_feature_transfer as transfer


class NavigationPublicationsTests(unittest.TestCase):
    setUp=transfer.NavigationFeatureTransferTests.setUp
    action=transfer.NavigationFeatureTransferTests.action
    ready=transfer.NavigationFeatureTransferTests.ready
    restart_call=transfer.NavigationFeatureTransferTests.restart_call
    install=transfer.NavigationFeatureTransferTests.install

    def actor_client(self):return Client(self.h.harness.client.url,self.h.harness.server.actor_token)

    def test_literal_old_actor_publication_and_new_process_original_share_one_global_sequence(self):
        self.ready();h=self.h;actor=h.flow_fixture.flow('actor');client=self.actor_client()
        with actor.held():
            actor.load();old=actor.observer()
            # Existing stage-zero writer emits the original two-field reference.
            first=old.publish(client);old_carrier=deepcopy(old.publication_store().read())
        self.install();h.flow.act(self.restart_call())
        offset=h.flow.state['observerOffsets']['actor'];result=actor.observe(offset)
        self.assertEqual(offset+1,result['sequence']);self.assertEqual('A',result['state']['location'])
        with actor.held():
            actor.load();current=actor.observer();publications=actor.publications(current)
            before=publications.state();self.assertEqual(1,len(before['records']))
            reference=publications.reference(current)
            for bad in (reference|dict(stage=0),reference|dict(stage=True),reference|dict(expected=True)):
                with self.subTest(bad=bad),self.assertRaises(NativeUIError):publications.validate_original(bad)
            self.assertEqual(old_carrier,current.publication_store().read())
            second=publications.publish(client);value=deepcopy(current.publication_store().read())
            self.assertEqual(2,len(publications.state()['records']))
            self.assertEqual(second,publications.resolve(client));self.assertEqual(value,current.publication_store().read())
        entries=h.harness.client.observe()['entries'];self.assertEqual(2,len(entries))
        self.assertEqual(first['actorSequence'],entries[0]['actorSequence'])
        self.assertEqual(result['sequence'],entries[1]['actorSequence']);self.assertEqual(result['state'],entries[1]['facts'])
        self.assertGreater(entries[1]['actorSequence'],entries[0]['actorSequence'])
        self.assertEqual(['app.stop','app.launch'],h.lifecycle.calls)

    def test_lost_actual_new_process_post_is_resolved_without_resend_or_new_gpu_capture(self):
        self.ready();h=self.h;self.install();h.flow.act(self.restart_call())
        actor=h.flow_fixture.flow('actor');offset=h.flow.state['observerOffsets']['actor'];measured=actor.observe(offset)
        client=self.actor_client();request=client.request;posts=[]
        def lost(path,body=None,**options):
            value=request(path,body,**options)
            if path.endswith('/samples'):
                posts.append(deepcopy(body));raise OSError('Actual accepted POST lost its response')
            return value
        with actor.held():
            actor.load();owner=actor.publications(actor.observer())
            with patch.object(client,'request',side_effect=lost),self.assertRaises(OSError):owner.publish(client)
            self.assertEqual('issued',owner.state()['pending']['phase'])
        captures=self.new.gpu.frames
        with self.assertRaises(NativeUIError):actor.observe(measured['sequence'])
        self.assertEqual(captures,self.new.gpu.frames);self.assertEqual(1,len(posts))
        with actor.held():
            actor.load();owner=actor.publications(actor.observer());receipt=owner.resolve(client)
            self.assertEqual(measured['sequence'],receipt['actorSequence']);self.assertIsNone(owner.state()['pending'])
        self.assertEqual(1,len(h.harness.client.observe()['entries']));self.assertEqual(captures,self.new.gpu.frames)

    def test_public_primary_original_reconstructs_actual_current_image_and_never_posts_an_actor_sample(self):
        self.ready();h=self.h;self.install();h.flow.act(self.restart_call())
        offset=h.flow.state['observerOffsets']['primary'];result=h.flow.observe(offset)
        self.assertEqual(offset+1,result['sequence']);self.assertEqual(1,len(result['artifacts']))
        self.assertEqual(result['sequence'],result['artifacts'][0]['sequence'])
        self.assertEqual([],h.harness.client.observe()['entries'])
        with h.flow.held():
            h.flow.load();owner=h.flow.observer();current=h.flow.publications(owner)
            self.assertEqual(result,current.latest())
            before=deepcopy(h.lifecycle.calls);self.new.sdk.okay=False
            with self.assertRaises(NativeUIError):current.latest()
            self.assertEqual(before,h.lifecycle.calls)


if __name__=='__main__':unittest.main()
