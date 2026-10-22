"""Active coordinator uses real normal input codecs and original observations.

Only Qt/native/SDK physical producers are modeled; HTTP, JS/QML processing,
private files, input receipts, image owners and validators are real.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
import uuid
from adapters.normal_ui import NativeUIError
from feature_journeys.fixtures import context
from ios.self_tests.navigation_feature_observer_fixture import Whole


class NavigationFeaturePlacesTests(unittest.TestCase):
    def setUp(self):
        self.h=Whole(self);self.h.flow.prepare();self.sequence=0
        self.observe();self.h.open_directory();self.observe()
    def observe(self):
        value=self.h.flow.observe_active(self.sequence);self.sequence=value['sequence'];return value
    def act(self,verb,**inputs):
        h=self.h;ticket=uuid.uuid4().hex;h.harness.client.activate(ticket,verb,inputs);h.gpu.marker=ticket
        value=dict(contractVersion=16,runId=h.run,ticket=ticket,verb=verb,inputs=inputs,fixtureUrl=h.fixture.fixture_url)
        self.assertEqual({'performed':True},h.flow.act(value));return value
    def test_normal_cancel_save_rename_and_search_derive_from_new_sources_and_unchanged_first_open(self):
        h=self.h;ctx=context(h.run);original=h.books.path.read_bytes()
        with h.flow.held():directory=deepcopy(h.flow.directory(h.observer(),h.flow.admission()))
        for verb,name,expected in (('bookmark-add-cancel',ctx['name'],''),('bookmark-add',ctx['name'],ctx['name']),
                ('bookmark-rename-cancel',ctx['renamed'],ctx['name']),('bookmark-rename',ctx['renamed'],ctx['renamed'])):
            self.act(verb,name=name);measured=self.observe()
            self.assertEqual(expected,measured['state']['bookmarkName']);self.assertEqual(bool(expected),measured['state']['bookmark'])
            if not expected:self.assertEqual(original,h.books.path.read_bytes())
        self.assertEqual({ctx['renamed']:h.flow_fixture.b.current},json.loads(h.books.path.read_text()))
        for query,visible in ((ctx['hidden'],[]),(ctx['name'],[ctx['destination']])):
            self.act('directory-search',query=query);measured=self.observe()
            self.assertEqual(query,measured['state']['searchQuery']);self.assertEqual(visible,measured['state']['searchResults'])
        with h.flow.held():self.assertEqual(directory,h.flow.directory(h.observer(),h.flow.admission()))
        self.assertGreater(len(h.widget.edits),20)
    def test_ignored_normal_tab_input_stays_owned_without_saved_file_or_second_delivery(self):
        h=self.h;h.widget.ignore=True;original=h.books.path.read_bytes();ctx=context(h.run)
        ticket=uuid.uuid4().hex;h.harness.client.activate(ticket,'bookmark-add',dict(name=ctx['name']))
        call=dict(contractVersion=16,runId=h.run,ticket=ticket,verb='bookmark-add',inputs=dict(name=ctx['name']),fixtureUrl=h.fixture.fixture_url)
        with self.assertRaises(NativeUIError):h.flow.act(call)
        before=deepcopy(h.widget.edits);self.assertEqual(1,len(before));self.assertEqual(original,h.books.path.read_bytes())
        h.widget.ignore=False
        with self.assertRaises(NativeUIError):h.flow_fixture.flow().act(call)
        self.assertEqual(before,h.widget.edits);self.assertEqual(original,h.books.path.read_bytes())


if __name__=='__main__':unittest.main()
