"""Role-owned process quiet proof on real private files and synthetic OS replies."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack, unpack
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.process_retirement import IOSProcessRetirement
from ios.self_tests.test_ios_retired_process import Boundary, SOURCE, BUNDLE

RUN = 'a'*32
BINDING = dict(sourceRevision='b'*40, artifactSha256='c'*64, processIdentity='42',
               sessionId='owned-session', generation=1, targetFingerprint='d'*64)


class ProcessRetirementTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name); self.lock = ScriptSourceLock(self.root/'script-feature-sources.lock')
        self.os = Boundary()
    def owner(self, role='primary'):
        return IOSProcessRetirement(PrivateFeatureState(self.root/('ios-graphics-'+role+'-0-process-retirement.json')),
            self.os.reader(), BINDING, RUN, role, 0, self.lock)
    def finish(self, owner):
        self.assertFalse(owner.advance()); self.os.clock += 1.6; self.assertFalse(owner.advance())
        self.os.clock += 1.6; self.assertTrue(owner.advance()); return owner.current()
    def archived(self, owner, *, records=None):
        return IOSProcessRetirement.archive(owner.previous, path=owner.store.path, binding=BINDING, source=SOURCE,
            bundle=BUNDLE, run=RUN, role=owner.role, stage=0, records=records)

    def test_new_numeric_pid_reads_span_both_node_clocks_and_both_controller_clocks(self):
        with self.lock.held():
            owner = self.owner(); last = self.finish(owner); window = owner.state['windows'][-1]
            self.assertGreaterEqual(window['elapsedMs'], 3000); self.assertEqual(3, len(window['samples']))
            rows = [owner.load(r) for r in owner.state['records']]
            self.assertEqual(last['original'], self.os.original)
            self.assertGreater(rows[0]['original']['clockBefore']['epochMs']-rows[0]['acquisition']['hostBeforeEpochMs'], 86399000)
            self.assertEqual('observed', last['mode']); self.assertTrue(self.archived(owner)['windows'][-1]['complete'])
            self.assertTrue(all(set(q) == {'bundleId', 'commandId'} for q in self.os.queries))

    def test_actor_reconstruction_requires_its_own_queries_and_owns_its_own_window(self):
        with self.lock.held():
            primary = self.owner(); self.finish(primary); actor = self.owner('actor')
            self.assertFalse(actor.advance()); a = actor.current(); p = primary.current()
            self.assertNotEqual(a['original']['commandId'], p['original']['commandId'])
            self.assertNotEqual(actor.store.path, primary.store.path)
            self.assertGreater(a['original']['sequence'], p['original']['sequence'])
            self.assertFalse(actor.state['windows'][-1]['complete']); self.assertEqual(1, len(actor.state['records']))

    def test_numeric_presence_or_new_bundle_resets_quiet_instead_of_becoming_an_empty_success(self):
        for states, pids, running in (([0, 0], [0, 0], [True, True]), ([4, 4], [43, 43], [False, False])):
            with self.subTest(states=states), self.lock.held():
                owner = self.owner(); self.os.states, self.os.pids, self.os.running = [1, 1], [0, 0], [False, False]
                owner.advance(); self.os.clock += 2
                self.os.states, self.os.pids, self.os.running = states, pids, running
                self.assertFalse(owner.advance()); self.assertIsNone(owner.state['windows'][-1]['start'])
                self.os.states, self.os.pids, self.os.running = [1, 1], [0, 0], [False, False]
                owner.advance(); self.os.clock += 1.6; owner.advance(); self.os.clock += 1.6
                self.assertTrue(owner.advance()); self.assertGreaterEqual(owner.state['windows'][-1]['start'], 2)

    def test_lost_passive_read_is_explicitly_abandoned_and_cannot_bridge_the_quiet_interval(self):
        with self.lock.held():
            owner = self.owner(); owner.advance(); self.os.clock += 2
            with patch.object(owner.reader, 'send', side_effect=OSError('Synthetic lost original OS read')), self.assertRaises(NativeUIError):owner.advance()
            self.assertIsNotNone(owner.state['pending']); self.os.clock += 1
            recovered = self.owner(); self.assertFalse(recovered.advance())
            rows = [recovered.load(r) for r in recovered.state['records']]
            self.assertEqual(['observed', 'abandoned', 'observed'], [r['mode'] for r in rows])
            self.assertEqual(2, recovered.state['windows'][-1]['start']); self.assertEqual(0, recovered.state['windows'][-1]['elapsedMs'])
            self.assertEqual(2, len(self.os.queries))

    def test_lost_committed_record_return_adopts_original_then_still_performs_new_acquisition(self):
        with self.lock.held():
            owner = self.owner(); original = owner.store_record
            def lost(row):
                original(row); raise OSError('Synthetic lost committed OS record return')
            with patch.object(owner, 'store_record', side_effect=lost), self.assertRaises(OSError):owner.advance()
            self.assertEqual(1, len(self.os.queries)); packet = deepcopy(self.os.original)
            recovered = self.owner(); self.assertFalse(recovered.advance())
            rows = [recovered.load(r) for r in recovered.state['records']]
            self.assertEqual(packet, rows[0]['original']); self.assertNotEqual(packet['commandId'], rows[1]['original']['commandId'])
            self.assertEqual(2, len(self.os.queries)); self.assertIsNone(recovered.state['pending'])

    def test_reconstruction_restores_counter_nonce_and_exact_original_anchor_floors(self):
        with self.lock.held():
            owner = self.owner(); owner.advance(); packet = deepcopy(self.os.original)
            self.os.mutate = lambda value:value.update(sequence=packet['sequence'])
            recovered = self.owner()
            with self.assertRaises(NativeUIError):recovered.advance()
            self.assertEqual(packet, recovered.reader.last); self.assertIsNotNone(recovered.state['pending'])
            self.assertEqual(1, len(recovered.state['records']))

    def test_stale_complete_window_does_not_create_current_facts_or_skip_a_fresh_read(self):
        with self.lock.held():
            owner = self.owner(); last = self.finish(owner); self.os.clock += 2
            with self.assertRaises(NativeUIError):owner.current()
            self.assertTrue(self.archived(owner)['windows'][-1]['complete'])
            self.os.running = [True, True]; self.assertFalse(owner.advance())
            self.assertEqual(4, len(self.os.queries)); self.assertFalse(owner.state['windows'][-1]['complete'])
            self.assertEqual(last['original']['anchor'], owner.current()['original']['anchor'])

    def test_aged_attempt_starts_a_new_window_and_preserves_original_completed_history(self):
        with self.lock.held():
            owner = self.owner(); self.finish(owner); first = deepcopy(owner.state['windows'][0]); self.os.clock += 20
            recovered = self.owner(); self.assertFalse(recovered.advance())
            self.assertEqual(first, recovered.state['windows'][0]); self.assertEqual(2, len(recovered.state['windows']))
            self.assertEqual([4], recovered.state['windows'][-1]['samples'])

    def test_frozen_node_clock_cannot_receive_controller_elapsed_time_as_quiet_credit(self):
        with self.lock.held():
            owner = self.owner(); owner.advance(); last = deepcopy(self.os.original['clockAfter'])
            self.os.mutate = lambda value:value.update(clockBefore=deepcopy(last), clockAfter=deepcopy(last))
            self.os.clock += 2; self.assertFalse(owner.advance()); self.os.clock += 2; self.assertFalse(owner.advance())
            self.assertEqual(0, owner.state['windows'][-1]['elapsedMs'])

    def test_metadata_intent_failure_and_lost_scope_prevent_all_new_os_queries(self):
        with self.lock.held():
            owner = self.owner()
            with patch.object(owner.store, 'write', side_effect=OSError('Synthetic failed durable intent')), self.assertRaises(OSError):owner.advance()
            self.assertEqual([], self.os.queries)
            self.os.good = False
            with self.assertRaises(NativeUIError):self.owner()
            self.assertEqual([], self.os.queries)

    def test_changed_original_receipts_or_foreign_role_and_missing_archives_are_rejected(self):
        with self.lock.held():
            owner = self.owner(); self.finish(owner)
            records = {r['ordinal']:owner.record_store(r['ordinal']).read() for r in owner.state['records']}
            self.assertTrue(self.archived(owner, records=records)['windows'][-1]['complete'])
            changed = deepcopy(records); changed[1]['role'] = 'actor'
            with self.assertRaises(NativeUIError):self.archived(owner, records=changed)
            with self.assertRaises(NativeUIError):self.archived(owner, records={})
            changed = deepcopy(owner.previous); state = unpack(changed['payload'])[0]
            state['windows'][-1]['elapsedMs'] += 1; changed['payload'] = pack([state])
            with self.assertRaises(NativeUIError):owner.decode(changed)
            for ref in owner.state['records']:owner.record_store(ref['ordinal']).discard(records[ref['ordinal']])
            self.assertTrue(self.archived(owner, records=records)['windows'][-1]['complete'])
            with self.assertRaises(NativeUIError):self.archived(owner)


if __name__ == '__main__':unittest.main()
