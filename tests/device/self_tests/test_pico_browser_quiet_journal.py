"""Original quiet-frame storage, migration and retained interruption boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from adapters.chat_journey.source_chunks import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.browser_quiet_journal import PicoBrowserQuietJournal
from self_tests import test_pico_tablet_web_feature as seams


class PicoBrowserQuietJournalTests(unittest.TestCase):
    def setUp(self):
        self.fixture=seams.PicoTabletWebFeatureTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.original=self.fixture.window();self.flow=self.fixture.flow();self.lock=self.flow.lock
        with self.lock.held():self.owner=self.flow.owner()
        self.store=PrivateFeatureState(self.fixture.root/'original-quiet.json')
    def journal(self,reference=None):
        return PicoBrowserQuietJournal(self.store,self.lock,seams.RUN,seams.URL,self.owner['ownerToken'],self.owner['binding'],reference)
    def test_original_legacy_read_has_no_write_or_query_and_explicit_migration_keeps_every_complete_frame(self):
        with self.lock.held():
            count=len(self.fixture.original.commands);journal=self.journal(self.original)
            self.assertIsNone(self.store.read());self.assertEqual(count,len(self.fixture.original.commands))
            journal.migrate();reference=journal.reference();self.assertEqual(self.original,journal.value)
            self.assertEqual(31,len(journal.chunks.identities));cold=self.journal(reference)
            self.assertEqual(self.original,cold.value);self.assertEqual(count,len(self.fixture.original.commands))
    def test_pending_read_and_missing_parent_cannot_adopt_retained_original_chunks(self):
        with self.lock.held():
            journal=self.journal(self.original);journal.migrate();reference=journal.reference();child=journal.chunks.store(0);raw=child.path.read_bytes()
            journal.begin()
            with self.assertRaises((ValueError,RuntimeError)):self.journal(reference)
            self.store.path.unlink()
            with self.assertRaises((ValueError,RuntimeError)):self.journal()
            self.assertEqual(raw,child.path.read_bytes())
    def test_same_bytes_replaced_chunk_or_changed_cached_original_never_qualifies(self):
        with self.lock.held():
            journal=self.journal(self.original);journal.migrate();child=journal.chunks.store(0)
            replacement=child.path.with_name('replacement');replacement.write_bytes(child.path.read_bytes());replacement.chmod(0o600);replacement.replace(child.path)
            with self.assertRaises((ValueError,RuntimeError)):journal.reference()
            # A cold reader may inspect the originally admitted manifest; a
            # live reader cannot replace its actual original inode silently.
            cold=self.journal(dict(browserQuietReferenceVersion=1,sha256=digest(self.store.read())))
            cold.value['frames'][0]['host']+=.001
            with self.assertRaises((ValueError,RuntimeError)):cold.reference()
