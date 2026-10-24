"""Real paired file census; product measurements are explicit journal models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
import time
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_rooted_inventory import IOSEmoteRootedInventory
from ios.adapters.emote_terminal_journal import IOSEmoteTerminalJournal
from ios.self_tests import test_ios_emote_terminal_journal as journal_fixture


class RootedInventoryTests(unittest.TestCase):
    def setUp(self):
        self.fixture=journal_fixture.TerminalJournalTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.f=self.fixture;self.journal=IOSEmoteTerminalJournal(self.f.window)

    def test_unknown_initial_or_later_carrier_is_never_admitted_by_its_name(self):
        inventory=IOSEmoteRootedInventory(self.journal,set())
        store=PrivateFeatureState(self.f.roles['actor'].store.path.with_name('ios-emote-actor-unknown.json'))
        store.write(dict(unresolved=True),None)
        with self.assertRaises(NativeUIError):inventory.guard()
        with self.assertRaises(NativeUIError):IOSEmoteRootedInventory(self.journal,set())
        self.assertEqual(dict(unresolved=True),store.read())

    def test_same_inode_rewrite_with_restored_bytes_and_mtime_blocks_reuse(self):
        store=PrivateFeatureState(self.f.roles['primary'].store.path.with_name('ios-emote-primary-guard-test.json'))
        value=dict(inventoryContinuityOnly=1);store.write(value,None)
        inventory=IOSEmoteRootedInventory(self.journal,{store.path})
        before=store.path.stat();raw=store.path.read_bytes();time.sleep(.002)
        store.path.write_bytes(raw.replace(b':1',b':2'));store.path.write_bytes(raw)
        os.utime(store.path,ns=(before.st_atime_ns,before.st_mtime_ns))
        self.assertEqual(raw,store.path.read_bytes())
        with self.assertRaises(NativeUIError):inventory.guard()

    def test_only_actual_typed_journal_outputs_can_appear_during_inspect_and_seal(self):
        inventory=IOSEmoteRootedInventory(self.journal,set());self.journal.check=inventory.guard
        self.journal.inspect(self.f.refs)
        result=self.journal.seal(self.f.description,self.f.samples,publisher_store=self.f.publisher)
        self.assertEqual(self.f.proof['seal'],result['seal']);inventory.guard()
        self.assertEqual({self.journal.store.path,self.journal.originals.path(self.journal.originals.expand(self.journal.state['record']))},inventory.owned())

    def test_unknown_terminal_original_is_not_a_namespace_wide_exemption(self):
        inventory=IOSEmoteRootedInventory(self.journal,set())
        path=self.f.artifacts/('emote-terminal-frame-inputs-'+self.f.description['runId']+'-primary-0002-'+'f'*64+'.json')
        store=PrivateFeatureState(path);store.write(dict(unowned=True),None)
        with self.assertRaises(NativeUIError):inventory.guard()
        self.assertEqual(dict(unowned=True),store.read())


if __name__=='__main__':unittest.main()
