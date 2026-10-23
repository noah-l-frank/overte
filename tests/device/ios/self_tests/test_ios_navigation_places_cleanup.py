"""Whole ordinary Places recovery with real journals and modeled Qt/SDK."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
import uuid
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack
from feature_journeys.fixtures import context
from ios.self_tests.test_ios_navigation_feature_places import NavigationFeaturePlacesTests


class NavigationPlacesCleanupTests(unittest.TestCase):
    setUp=NavigationFeaturePlacesTests.setUp
    observe=NavigationFeaturePlacesTests.observe
    act=NavigationFeaturePlacesTests.act

    def cleanup_call(self):
        h=self.h;ticket=uuid.uuid4().hex;h.harness.client.activate(ticket,'cleanup',{})
        return dict(iosNavigationCleanupCallVersion=1,contractVersion=16,runId=h.run,ticket=ticket,verb='cleanup',inputs={},fixtureUrl=h.fixture.fixture_url)

    def owner(self):
        h=self.h;h.flow.load();return h.flow.runtime._navigation_places_cleanup(h.flow.selector,h.flow.admission())

    def test_cleanup_delivers_original_tokens_and_retains_every_actual_pretransport_intent(self):
        h=self.h;ctx=context(h.run);self.act('bookmark-add',name=ctx['name']);self.act('directory-search',query=ctx['hidden'])
        call=self.cleanup_call()
        with h.flow.held():
            owner=self.owner();self.assertEqual({'performed':True},owner.cleanup(call))
            original=deepcopy(owner.store.read());before=deepcopy(h.widget.edits)
            self.assertEqual({},json.loads(h.books.path.read_text()));self.assertEqual('',h.widget.page()['search'])
            self.assertGreaterEqual(len(owner.state['intents']),4)
            self.assertTrue(all(row['call']==call for row in owner.state['intents']))
            self.assertEqual({'performed':True},self.owner().cleanup(call));self.assertEqual(before,h.widget.edits)
            self.assertEqual(original,owner.store.read());self.assertEqual('delivered',owner.state['phase'])

    def test_ignored_input_keeps_issued_responsibility_and_never_retries_after_reconstruction(self):
        h=self.h;ctx=context(h.run);self.act('bookmark-add',name=ctx['name']);self.act('directory-search',query=ctx['hidden'])
        call=self.cleanup_call();h.widget.ignore=True
        with h.flow.held():
            owner=self.owner()
            with self.assertRaises(NativeUIError):owner.cleanup(call)
            before=deepcopy(h.widget.edits);self.assertEqual('issued',owner.state['phase'])
            self.assertEqual(1,len(owner.state['intents']));h.widget.ignore=False
            with self.assertRaises(NativeUIError):self.owner().cleanup(call)
            self.assertEqual(before,h.widget.edits);self.assertIn(ctx['name'],json.loads(h.books.path.read_text()))

    def test_phase_crossing_after_durable_intent_prevents_the_normal_input(self):
        h=self.h;call=self.cleanup_call()
        with h.flow.held():
            owner=self.owner();intent=owner.intent
            def crossed(value):
                intent(value);h.harness.client.activate(uuid.uuid4().hex,'open',{})
            owner.intent=crossed;before=deepcopy(h.widget.edits)
            with self.assertRaises(NativeUIError):owner.cleanup(call)
            self.assertEqual(before,h.widget.edits);self.assertEqual(1,len(owner.state['intents']))
            self.assertEqual('issued',owner.state['phase'])

    def test_rewritten_cleanup_intent_cannot_authorize_foreign_text_or_another_root(self):
        h=self.h;ctx=context(h.run);self.act('directory-search',query=ctx['hidden']);call=self.cleanup_call()
        with h.flow.held():
            owner=self.owner();owner.cleanup(call);before=deepcopy(h.widget.edits)
            raw=owner.store.read();state=unpack(raw['payload'])[0]
            event=next(row for row in state['intents'] if row['action']=='replace');event['value']='foreign'
            owner.store.write(dict(raw,payload=pack([state])),raw)
            with self.assertRaises(NativeUIError):self.owner()
            self.assertEqual(before,h.widget.edits)


if __name__=='__main__':unittest.main()
