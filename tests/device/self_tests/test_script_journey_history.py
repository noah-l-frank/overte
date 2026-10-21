"""Cross-invocation provenance counterexamples; synthetic sources, no devices."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import os
import subprocess
import tempfile
import threading
import sys
import unittest
from unittest.mock import patch
import zlib

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tests/device'))

from self_tests import test_script_journey_measurements as fixtures
import adapters.script_journey.history as history
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_journey.lock import ScriptSourceLock
from self_tests.test_normal_script_file_manager import BINDING
from self_tests.test_native_script_observation import ENTITY
from self_tests.test_native_script_membership import membership_source
from self_tests.test_native_script_loads import history as load_history, event


class ScriptHistoryTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.ScriptMeasurementTests('test_live_reader_reacquires_all_original_sources_and_preserves_original_lifecycle')
        self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.store = PrivateFeatureState(self.f.root.parent / 'history.json')

    def reader(self):
        def fresh(old):
            return type(old)(old.send, old.original, old.clock_ms, old.guard, old.pid,
                             monotonic=old.monotonic, sleep=old.sleep)
        return self.f.reader(execution=fresh(self.f.execution_reader), ui=fresh(self.f.ui_reader),
                             lifecycle=fresh(self.f.lifecycle_reader))

    def owner(self, **changes):
        args = dict(store=self.store, binding=BINDING, run=fixtures.RUN, role='primary',
                    directory=self.f.directory, fixture_url=fixtures.FIXTURE)
        return history.ScriptHistory(**(args | changes))

    def durable(self):
        return history.DurableScriptMeasurements(self.reader(), self.owner())

    def acquire(self, reader=None):
        return (reader or self.durable()).read(fixtures.TICKET, 19000)

    def edit_frames(self, mutation):
        original = self.store.read(); value = deepcopy(original)
        frames = history.unpack(value['transcript']); mutation(frames)
        value['transcript'] = history.pack(frames)
        self.store.write(value, original)

    def test_restore_sends_nothing_and_next_read_acquires_four_new_originals(self):
        first_reader = self.durable(); first = self.acquire(first_reader)
        one = self.store.read()
        before = (len(self.f.execution_source.commands), len(self.f.ui_source.commands), len(self.f.lifecycle_source.commands))
        second_reader = self.durable()
        self.assertEqual(before, (len(self.f.execution_source.commands), len(self.f.ui_source.commands), len(self.f.lifecycle_source.commands)))
        self.assertEqual(2, second_reader.reader.execution.sequence)
        self.assertEqual(first, self.acquire(second_reader))
        two = self.store.read()
        self.assertEqual((2, 4), (one['revision'], two['revision']))
        frames = history.unpack(two['transcript'])
        self.assertEqual(2, len(frames))
        self.assertNotEqual(frames[0]['execution']['requestId'], frames[1]['execution']['requestId'])
        self.assertEqual((20000, 20000), tuple(frame['epochMs'] for frame in frames))
        self.assertNotIn('state', frames[0]); self.assertEqual([], self.f.ui_source.input_requests)
        recorded=history.canonical(history.unpack(two['transcript']))
        first['state']['effects'] = 999
        self.assertEqual(recorded,history.canonical(history.unpack(self.store.read()['transcript'])))

    def test_reconstruction_cannot_return_a_cached_success_when_fresh_source_is_ignored(self):
        self.acquire(); saved = self.store.read()
        self.f.execution_source.ignore = True
        with self.assertRaises(NativeUIError): self.acquire()
        pending = self.store.read()
        self.assertEqual('reading', pending['phase'])
        self.assertEqual(saved['transcript'], pending['transcript'])
        before = len(self.f.execution_source.commands)
        with self.assertRaises(NativeUIError): self.durable()
        self.assertEqual(before, len(self.f.execution_source.commands))

    def test_same_object_and_new_object_both_refuse_an_interrupted_partial_acquisition(self):
        reader = self.durable(); self.f.ui_source.ignore_result = True
        with self.assertRaises(NativeUIError): self.acquire(reader)
        calls = len(self.f.execution_source.commands)
        with self.assertRaises(NativeUIError): self.acquire(reader)
        with self.assertRaises(NativeUIError): self.durable()
        self.assertEqual(calls, len(self.f.execution_source.commands))
        self.assertEqual('reading', self.store.read()['phase'])

    def test_failed_pending_persistence_never_sends_a_source_request(self):
        reader = self.durable(); calls = len(self.f.execution_source.commands)
        with patch.object(self.store, 'write', side_effect=OSError('simulated private storage failure')):
            with self.assertRaises(NativeUIError): self.acquire(reader)
        self.assertEqual(calls, len(self.f.execution_source.commands)); self.assertIsNone(self.store.read())

    def test_lost_pending_write_return_preserves_uncertainty_without_source_dispatch(self):
        reader = self.durable(); original = self.store.write
        def lost(value, previous):
            original(value, previous); raise OSError('simulated lost return')
        calls = len(self.f.execution_source.commands)
        with patch.object(self.store, 'write', side_effect=lost):
            with self.assertRaises(NativeUIError): self.acquire(reader)
        self.assertEqual(calls, len(self.f.execution_source.commands))
        self.assertEqual('reading', self.store.read()['phase'])
        with self.assertRaises(NativeUIError): self.durable()

    def test_lost_finish_return_keeps_accepted_prefix_and_requires_another_fresh_read(self):
        reader = self.durable(); original = self.store.write
        def lost(value, previous):
            original(value, previous)
            if value['phase'] == 'ready': raise OSError('simulated lost return')
        with patch.object(self.store, 'write', side_effect=lost):
            with self.assertRaises(NativeUIError): self.acquire(reader)
        self.assertEqual('ready', self.store.read()['phase'])
        self.assertEqual(1, len(history.unpack(self.store.read()['transcript'])))
        before = len(self.f.execution_source.commands)
        self.acquire()
        self.assertEqual(before + 1, len(self.f.execution_source.commands))
        self.assertEqual(2, len(history.unpack(self.store.read()['transcript'])))

    def test_missing_finish_write_retains_pending_history_instead_of_forgetting_acquisition(self):
        reader = self.durable(); original = self.store.write
        def reject(value, previous):
            if value['phase'] == 'ready': raise OSError('simulated full storage')
            original(value, previous)
        with patch.object(self.store, 'write', side_effect=reject):
            with self.assertRaises(NativeUIError): self.acquire(reader)
        self.assertEqual('reading', self.store.read()['phase'])
        with self.assertRaises(NativeUIError): self.durable()

    def test_old_instance_cannot_overwrite_another_invocations_accepted_history(self):
        old, current = self.durable(), self.durable()
        self.acquire(current); actual = self.store.read()
        calls = len(self.f.execution_source.commands)
        with self.assertRaises(NativeUIError): self.acquire(old)
        self.assertEqual(actual, self.store.read())
        self.assertEqual(calls, len(self.f.execution_source.commands))

    def test_target_run_role_origin_directory_and_typed_context_are_pinned(self):
        self.acquire()
        for changes in (dict(run='c' * 32), dict(role='actor'), dict(directory='file:///foreign/private'),
                        dict(fixture_url=fixtures.FIXTURE.replace('12345','54321')),
                        dict(binding=BINDING | {'generation': True}),
                        dict(binding=BINDING | {'processIdentity': '31:replacement-start'}),
                        dict(binding=BINDING | {'artifactSha256': 'f' * 64})):
            with self.subTest(changes=list(changes)), self.assertRaises(NativeUIError): self.owner(**changes)

    def test_role_separation_preserves_primary_transcript_and_reacquires_actor_sources(self):
        self.acquire(); primary = self.store.read()
        actor_store = PrivateFeatureState(self.f.root.parent / 'actor-history.json')
        actor = history.DurableScriptMeasurements(self.reader(), self.owner(store=actor_store, role='actor'))
        self.acquire(actor)
        self.assertEqual(primary, self.store.read())
        self.assertEqual('actor', actor_store.read()['role'])
        self.assertNotEqual(history.unpack(primary['transcript'])[0]['execution']['requestId'],
                            history.unpack(actor_store.read()['transcript'])[0]['execution']['requestId'])

    def test_loaded_module_and_callback_history_cannot_be_rewritten_after_reconstruction(self):
        self.acquire()
        self.f.execution_source.engine['required']['modules'][0]['loaded'] = False
        with self.assertRaises(NativeUIError): self.acquire()
        self.assertEqual('reading', self.store.read()['phase'])

    def test_original_load_callback_prefix_survives_reconstruction(self):
        original = self.f.execution_source.mutate
        changed = [False]
        def observed(packet):
            original(packet)
            value = event()
            if changed[0]: value['status'] = 'ConnectionRefused'
            load_history(packet, [value])
        self.f.execution_source.mutate = observed
        self.acquire(); changed[0] = True
        with self.assertRaises(NativeUIError): self.acquire()

    def test_retired_engine_known_manager_and_effect_cannot_return_after_a_new_cli_object(self):
        original = self.f.execution_source.mutate
        phase = [0]; service_rows = deepcopy(self.f.service['scripts'])
        def observed(packet):
            original(packet)
            if phase[0] == 1:
                packet['source']['engines'] = []
                packet['source']['effects'].update(entities=[], absentIds=[ENTITY])
            membership_source(packet, revision=phase[0] + 1)
        self.f.execution_source.mutate = observed
        self.acquire(); phase[0] = 1; self.f.service['scripts'] = []
        self.assertEqual([], self.acquire()['state']['running'])
        restored = self.durable()
        self.assertIn('a' * 32, restored.reader.execution.retired)
        self.assertIn('a' * 32, restored.reader.execution.retired_managers)
        self.assertIn(ENTITY, restored.reader.execution.absent_effects)
        phase[0] = 2; self.f.service['scripts'] = service_rows
        with self.assertRaises(NativeUIError): self.acquire(restored)

    def test_original_lifecycle_counters_cannot_reset_after_reconstruction(self):
        self.acquire()
        old_lifecycle = self.f.lifecycle_source.mutate
        self.f.lifecycle_source.mutate = lambda packet: (old_lifecycle(packet), packet['lifecycle'].update(activations=0))
        with self.assertRaises(NativeUIError): self.acquire()

    def test_original_ui_generation_cannot_reset_after_reconstruction(self):
        self.acquire(); self.f.ui_source.generation = 'f' * 32
        with self.assertRaises(NativeUIError): self.acquire()
        self.assertEqual('reading', self.store.read()['phase'])

    def test_original_native_execution_cursor_cannot_restart_after_reconstruction(self):
        self.acquire(); self.f.execution_source.sequence = 0
        with self.assertRaises(NativeUIError): self.acquire()
        self.assertEqual('reading', self.store.read()['phase'])

    def test_service_source_cannot_reappear_under_a_new_instance(self):
        self.acquire(); self.f.service['instance'] = 'd' * 32
        with self.assertRaises(NativeUIError): self.acquire()

    def test_fresh_but_rewound_service_epoch_cannot_erase_prior_original_time(self):
        self.acquire(); self.f.service['sampleEpochMs'] = 19999
        with self.assertRaises(NativeUIError): self.acquire()
        self.assertEqual('reading', self.store.read()['phase'])

    def test_tampered_historical_replayed_cursor_is_rejected_before_any_live_request(self):
        self.acquire(); self.acquire()
        self.edit_frames(lambda frames: frames[1]['service'].update(sampleSequence=frames[0]['service']['sampleSequence']))
        calls = len(self.f.execution_source.commands)
        with self.assertRaises(NativeUIError): self.durable()
        self.assertEqual(calls, len(self.f.execution_source.commands))

    def test_reused_original_query_identity_is_rejected_even_with_advancing_cursors(self):
        self.acquire(); self.acquire(); original = self.store.read()
        calls = len(self.f.execution_source.commands)
        for source,field in (('execution','requestId'),('ui','commandId'),('lifecycle','requestId')):
            with self.subTest(source=source):
                self.store.write(original,self.store.read())
                self.edit_frames(lambda frames:frames[1][source].update({field:frames[0][source][field]}))
                with self.assertRaises(NativeUIError):self.durable()
                self.assertEqual(calls,len(self.f.execution_source.commands))

    def test_history_restore_is_atomic_for_execution_reader_when_later_frame_is_invalid(self):
        self.acquire(); self.acquire(); reader = self.reader().execution
        frames = [frame['execution'] for frame in history.unpack(self.store.read()['transcript'])]
        frames[-1]['source']['engines'][0]['required']['modules'][0]['loaded'] = False
        with self.assertRaises(NativeUIError): reader.restore_history(frames)
        self.assertIsNone(reader.instance); self.assertEqual({}, reader.engines)
        self.assertEqual(0, reader.sequence)

    def test_history_restore_refuses_a_reader_that_already_accepted_live_observations(self):
        self.acquire(); reader = self.reader(); reader.execution.read(0)
        with self.assertRaises(NativeUIError): history.DurableScriptMeasurements(reader, self.owner())

    def test_contended_source_channel_never_dispatches_or_rewrites_the_transcript(self):
        reader = self.durable(); reader.source_lock.timeout = 0.05
        calls = len(self.f.execution_source.commands)
        with ScriptSourceLock(reader.source_lock.path).held():
            with self.assertRaises(NativeUIError): self.acquire(reader)
        self.assertIsNone(self.store.read())
        self.assertEqual(calls,len(self.f.execution_source.commands))

    def test_exact_frame_limit_fails_before_another_request_and_keeps_original_prefix(self):
        self.acquire(); calls = len(self.f.execution_source.commands); original = self.store.read()
        with patch.object(history, 'MAX_FRAMES', 1):
            with self.assertRaises(NativeUIError): self.acquire()
        self.assertEqual(calls, len(self.f.execution_source.commands)); self.assertEqual(original, self.store.read())

    def test_whole_deadline_includes_private_pending_write(self):
        reader = self.durable(); original = self.store.write
        def late(value, previous):
            original(value, previous); self.f.clock = 21
        calls = len(self.f.execution_source.commands)
        with patch.object(self.store, 'write', side_effect=late):
            with self.assertRaises(NativeUIError): self.acquire(reader)
        self.assertEqual(calls, len(self.f.execution_source.commands))
        self.assertEqual('reading', self.store.read()['phase'])


class SourceLockTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'script-sources.lock'
        self.lock = ScriptSourceLock(self.path, timeout=0.1)

    def test_explicit_same_instance_can_nest_without_releasing_outer_os_ownership(self):
        with self.lock.held():
            self.lock.assert_held()
            with self.lock.held():self.lock.assert_held()
            self.lock.assert_held()
            with self.assertRaises(NativeUIError):
                with ScriptSourceLock(self.path,timeout=0.01).held():self.fail('outer ownership released')
        with self.assertRaises(NativeUIError):self.lock.assert_held()

    def test_unheld_lock_cannot_authorize_direct_locked_acquisition(self):
        with self.assertRaises(NativeUIError):self.lock.assert_held()
        self.assertFalse(self.path.exists())

    def test_another_thread_cannot_reuse_the_same_instances_owner_token(self):
        outcomes=[]
        def other_thread():
            try:
                with self.lock.held():outcomes.append('unexpected overlap')
            except NativeUIError:outcomes.append('refused')
        with self.lock.held():
            other=threading.Thread(target=other_thread);other.start();other.join(timeout=2)
            self.assertFalse(other.is_alive());self.assertEqual(['refused'],outcomes)
            self.lock.assert_held()

    def test_separate_process_cannot_overlap_original_source_acquisition(self):
        code = """import sys
from adapters.script_journey.lock import ScriptSourceLock
from adapters.normal_ui import NativeUIError
try:
    with ScriptSourceLock(sys.argv[1],timeout=0.05).held():
        print('unexpected overlap')
        sys.exit(2)
except NativeUIError:
    print('source remains exclusively owned')
"""
        env = dict(os.environ, PYTHONPATH=str(ROOT/'tests/device'), PYTHONDONTWRITEBYTECODE='1')
        with self.lock.held():
            result = subprocess.run([sys.executable,'-c',code,str(self.path)],env=env,capture_output=True,
                                    text=True,timeout=3,check=False)
            self.assertEqual(0,result.returncode,result.stderr)
            self.assertEqual('source remains exclusively owned',result.stdout.strip())
        before = self.path.stat().st_ino
        with ScriptSourceLock(self.path).held():
            self.assertEqual(before,self.path.stat().st_ino)
        self.assertTrue(self.path.exists())

    def test_symlink_shared_wrong_mode_or_nonempty_lock_fails_closed(self):
        target = self.path.with_name('foreign'); target.write_bytes(b'')
        self.path.symlink_to(target)
        with self.assertRaises(NativeUIError):
            with self.lock.held(): self.fail('unsafe lock admitted')
        self.path.unlink(); self.path.write_bytes(b'private metadata')
        self.path.chmod(0o600)
        with self.assertRaises(NativeUIError):
            with self.lock.held(): self.fail('nonempty lock admitted')
        self.path.write_bytes(b''); self.path.chmod(0o644)
        with self.assertRaises(NativeUIError):
            with self.lock.held(): self.fail('public lock admitted')
        self.path.chmod(0o600); os.link(self.path,self.path.with_name('shared'))
        with self.assertRaises(NativeUIError):
            with self.lock.held(): self.fail('shared lock admitted')

    def test_replacing_the_lock_inode_is_detected_before_a_source_result_can_return(self):
        with self.assertRaises(NativeUIError):
            with self.lock.held():
                self.path.rename(self.path.with_name('old-owned-lock'))
                self.path.write_bytes(b''); self.path.chmod(0o600)

    def test_exception_releases_os_ownership_without_unlinking_the_lock(self):
        with self.assertRaises(NativeUIError):
            with self.lock.held(): raise ValueError('simulated source failure')
        before = self.path.stat().st_ino
        with self.lock.held(): pass
        self.assertEqual(before,self.path.stat().st_ino)



class TranscriptEncodingTests(unittest.TestCase):
    def encoded(self, raw):
        return dict(encoding='zlib-base64-json', bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                    data=base64.b64encode(zlib.compress(raw)).decode())

    def test_bounded_metadata_compresses_without_increasing_the_existing_private_store_limit(self):
        frames = [dict(original='actual repeated source metadata ' * 1000, sequence=i) for i in range(100)]
        encoded = history.pack(frames)
        self.assertGreater(encoded['bytes'], 65536)
        self.assertLess(len(history.canonical(encoded)), 65536)
        self.assertEqual(frames, history.unpack(encoded))

    def test_digest_size_encoding_boolean_and_unknown_field_corruption_are_rejected(self):
        original = history.pack([])
        for changes in (dict(bytes=True), dict(bytes=1), dict(bytes=3), dict(sha256='0' * 64),
                        dict(encoding='raw'), dict(data=original['data'] + '\n'), dict(extra=True)):
            with self.subTest(changes=changes), self.assertRaises((ValueError, RuntimeError)):
                history.unpack(original | changes)

    def test_duplicate_keys_nonfinite_values_noncanonical_json_and_wrong_root_are_rejected(self):
        for raw in (b'[{"a":1,"a":2}]', b'[NaN]', b'[Infinity]', b'[1, 2]', b'{}', b'[1e999]'):
            with self.subTest(raw=raw), self.assertRaises((ValueError, RuntimeError)):
                history.unpack(self.encoded(raw))

    def test_trailing_stream_and_truncated_stream_are_rejected(self):
        original = history.pack([]); compressed = base64.b64decode(original['data'])
        for raw in (compressed + zlib.compress(b'[]'), compressed + b'extra', compressed[:-1]):
            value = original | dict(data=base64.b64encode(raw).decode())
            with self.subTest(size=len(raw)), self.assertRaises((ValueError, RuntimeError)):
                history.unpack(value)

    def test_decompression_is_bounded_by_declared_size_and_global_limit(self):
        raw = b'[' + b'0,' * 100000 + b'0]'
        value = self.encoded(raw)
        with self.assertRaises((ValueError, RuntimeError)): history.unpack(value | dict(bytes=2))
        with patch.object(history, 'MAX_RAW', 1024):
            with self.assertRaises((ValueError, RuntimeError)): history.unpack(value)
            with self.assertRaises((ValueError, RuntimeError)): history.pack([raw.decode()])

    def test_incompressible_source_capacity_fails_closed_instead_of_dropping_old_frames(self):
        raw = random.Random(17).randbytes(70000).hex()
        with self.assertRaises((ValueError, RuntimeError)): history.pack([raw])


if __name__ == '__main__':
    unittest.main()
