"""Ordinary new-process Places actions keep original bookmark ownership."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
import uuid
from adapters.normal_ui import NativeUIError
from feature_journeys.fixtures import context
from ios.self_tests import test_ios_navigation_feature_transfer as transfer
from ios.self_tests.navigation_feature_next_ui_fixture import NextUI


class NavigationAfterRestartTests(unittest.TestCase):
    setUp=transfer.NavigationFeatureTransferTests.setUp
    action=transfer.NavigationFeatureTransferTests.action
    ready=transfer.NavigationFeatureTransferTests.ready
    restart_call=transfer.NavigationFeatureTransferTests.restart_call
    install=transfer.NavigationFeatureTransferTests.install

    def test_normal_new_page_deletes_actual_persisted_bookmark_and_closes_only_its_new_root(self):
        self.ready();h=self.h;self.install();h.flow.act(self.restart_call());ui=NextUI(self.new,self)
        sequence=h.flow.state['observerOffsets']['primary'];before=h.flow.observe_active(sequence);sequence=before['sequence']
        def act(verb,**inputs):
            nonlocal sequence
            ticket=uuid.uuid4().hex;h.harness.client.activate(ticket,verb,inputs);self.new.gpu.marker=ticket
            call=dict(contractVersion=16,runId=h.run,ticket=ticket,verb=verb,inputs=inputs,fixtureUrl=h.fixture.fixture_url)
            self.assertEqual({'performed':True},h.flow.act(call))
            value=h.flow.observe_active(sequence);sequence=value['sequence'];return value
        value=act('open');self.assertTrue(value['state']['panel'])
        self.assertEqual(context(h.run)['renamed'],value['state']['bookmarkName'])
        old_root=h.model.pages[0]['rootId'];new_root=self.new.model.pages[0]['rootId'];self.assertNotEqual(old_root,new_root)
        value=act('bookmark-delete',name=context(h.run)['renamed'])
        self.assertFalse(value['state']['bookmark']);self.assertEqual({},json.loads(self.new.books.path.read_text()))
        value=act('close');self.assertFalse(value['state']['panel']);self.assertEqual(['app.stop','app.launch'],h.lifecycle.calls)
        self.assertGreater(len(ui.widget.edits),0)

    def test_ignored_new_native_tab_keeps_persistence_and_never_replays_the_unknown_delete(self):
        self.ready();h=self.h;self.install();h.flow.act(self.restart_call());ui=NextUI(self.new,self)
        offset=h.flow.state['observerOffsets']['primary'];h.flow.observe_active(offset)
        ticket=uuid.uuid4().hex;h.harness.client.activate(ticket,'open',{});self.new.gpu.marker=ticket
        h.flow.act(dict(contractVersion=16,runId=h.run,ticket=ticket,verb='open',inputs={},fixtureUrl=h.fixture.fixture_url))
        value=h.flow.observe_active(offset+1);ui.widget.ignore=True;original=self.new.books.path.read_bytes()
        ticket=uuid.uuid4().hex;inputs=dict(name=context(h.run)['renamed']);h.harness.client.activate(ticket,'bookmark-delete',inputs)
        call=dict(contractVersion=16,runId=h.run,ticket=ticket,verb='bookmark-delete',inputs=inputs,fixtureUrl=h.fixture.fixture_url)
        with self.assertRaises(NativeUIError):h.flow.act(call)
        edits=deepcopy(ui.widget.edits);self.assertEqual(original,self.new.books.path.read_bytes());ui.widget.ignore=False
        with self.assertRaises(NativeUIError):h.flow_fixture.flow().act(call)
        self.assertEqual(edits,ui.widget.edits);self.assertEqual(original,self.new.books.path.read_bytes())
        self.assertEqual(['app.stop','app.launch'],h.lifecycle.calls)


if __name__=='__main__':unittest.main()
