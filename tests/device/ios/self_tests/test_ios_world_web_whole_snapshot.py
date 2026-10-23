"""Whole Snapshot2 preserves each actual child original and legacy boundary."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
import uuid

from adapters.normal_ui import NativeUIError
from ios.adapters import world_web_snapshot as legacy,world_web_whole_snapshot as source
from ios.self_tests.world_web_snapshot_fixture import SnapshotNative,packed
from ios.self_tests.world_web_whole_snapshot_fixture import WholeSnapshotNative


class WorldWebWholeSnapshotTests(unittest.TestCase):
    def query(self,native):
        return dict(schemaVersion=1,commandId='ios-'+uuid.uuid4().hex,action=source.ACTION,runId=native.sdk.run,fixtureUrl=native.fixture_url)
    def packet(self,native):
        query=self.query(native);native.send(query);value=deepcopy(native.last);source.validate(value,query,native.sdk.pid);return value,query
    def changed(self,value,mutate):
        body,_parts=source.body(value);mutate(body);result=deepcopy(value);result['payload']=packed(body);return result
    def test_exact_twelve_actual_getters_and_commands_have_independent_native_brackets(self):
        native=WholeSnapshotNative();value,query=self.packet(native);body,parts=source.body(value)
        self.assertEqual(2,value['iosWorldWebSnapshotVersion']);self.assertEqual(set(source.ACTIONS),set(body['queries']))
        self.assertEqual(['ledgerBefore','world','work','geometry','keys','pointer','entities','ledgerAfter','surfaces','closures','emissions'],[row['name'] for row in body['calls']])
        self.assertIsNone(parts['document']);self.assertTrue(parts['surfaces']['source']['surfaces'][0]['cached'])
        self.assertEqual(0,parts['emissions']['callSequence']);self.assertEqual([],parts['emissions']['calls'])
        for row in body['calls']:self.assertEqual(body['queries'][row['name']],row['command'])
        with self.assertRaises(NativeUIError):legacy.validate(value,query,native.sdk.pid)
    def test_live_reader_accepts_two_and_refuses_actual_legacy_one_before_last(self):
        native=WholeSnapshotNative();reader=source.IOSWorldWebWholeSnapshot(native.send,native.raw,native.sdk.tick,lambda:True,native.sdk.pid,monotonic=lambda:native.sdk.time,sleep=native.sdk.sleep)
        value=reader.read(native.sdk.run,native.fixture_url);self.assertEqual(2,value['iosWorldWebSnapshotVersion'])
        old=SnapshotNative()
        # An intentionally misrouted transport returns the actual legacy
        # getter bytes unchanged, including its genuine version and nonce.
        def legacy_routed(query):old.send(dict(query,action=legacy.ACTION))
        reader=source.IOSWorldWebWholeSnapshot(legacy_routed,old.raw,old.sdk.tick,lambda:True,old.sdk.pid,monotonic=lambda:old.sdk.time,sleep=old.sdk.sleep)
        with self.assertRaises(NativeUIError):reader.read(old.sdk.run,old.fixture_url)
        self.assertIsNone(reader.last);self.assertEqual(1,len(old.commands))
    def test_missing_or_foreign_actual_child_is_never_a_ready_batch(self):
        native=WholeSnapshotNative();first,_query=self.packet(native);second,query=self.packet(native);a,_=source.body(first)
        for mutate in (lambda body:body['queries'].pop('emissions'),lambda body:body['originals'].pop('surfaces'),
                lambda body:body['calls'][-2].update(resultJSON=a['calls'][-2]['resultJSON'])):
            with self.subTest(mutate=mutate),self.assertRaises(NativeUIError):source.validate(self.changed(second,mutate),query,native.sdk.pid)
    def test_actual_pending_dom_retains_inner_nonce_start_and_native_callback(self):
        native=WholeSnapshotNative(document=True,pending_polls=1,held_callback=True);query=self.query(native);native.send(query)
        pending=deepcopy(native.last);source.validate(pending,query,native.sdk.pid);native.last=native.read(query);ready=deepcopy(native.last)
        source.validate(ready,query,native.sdk.pid);source.continued(ready,pending)
        self.assertTrue(native.callback_pending);self.assertEqual(1,native.dom_issued)
        old,_=source.body(pending);current,_=source.body(ready);self.assertEqual(old['queries']['document'],current['queries']['document'])
        reset=self.changed(ready,lambda body:body['queries']['document'].update(commandId='ios-'+uuid.uuid4().hex))
        with self.assertRaises(NativeUIError):source.validate(reset,query,native.sdk.pid)
    def test_returned_parts_do_not_alias_parent_or_selected_originals(self):
        native=WholeSnapshotNative();value,_query=self.packet(native);expected=deepcopy(value);body,parts=source.body(value)
        body['queries'].clear();parts['surfaces']['source']['surfaces'].clear()
        self.assertEqual(expected,value);self.assertTrue(source.selected(value,['surfaces'])['surfaces']['source']['surfaces'])


if __name__=='__main__':unittest.main()
