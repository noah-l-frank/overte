"""Execute the real passive Host reader over explicitly modeled native frames.

Native/Qt/JNI/Java producers are seams here. No compiler or device is invoked.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path[:0] = [str(ROOT), str(ROOT/'tests/device'), str(HERE)]
from adapters.normal_ui import NativeUIError
from adapters.script_journey.lock import ScriptSourceLock
from adapters.pico4.world_current_consumption import PicoWorldCurrentConsumption, command, validate, encoding
from test_world_current_input_reader import CurrentBoundary, RUN, URL, OWNER


class TraceBoundary:
    """The native packet producer is an explicit model, never a product proof."""
    def __init__(self, focus):
        self.focus = focus
        self.calls, self.retained, self.frames = [], [], []
        self.sequence = 0
        self.raw = ''
        self.arm_call = None
        self.terminal = False
        self.reason = None
        self.source = PicoWorldCurrentConsumption(focus.current, self.send, lambda: self.raw, self.retained.append)

    def send(self, call):
        self.calls.append(deepcopy(call))
        self.sequence += 1
        if call['operation'] == 'arm-current-consumption':
            self.arm_call = deepcopy(call)
        original = self.focus.current.last
        authority = self.focus.pair()['native']
        snapshot = dict(native=authority, finish=deepcopy(original['source']['originalFinish']))
        source = dict(attemptReference=dict(nonce=self.arm_call['commandId'], itemInstance=authority['itemInstance'],
                          sourceInstance=original['instance']),
                      focusReference={k: original[k] for k in ('commandId', 'instance', 'sequence')},
                      nativeBefore=deepcopy(snapshot), nativeAfter=deepcopy(snapshot),
                      lifetime=dict(itemAlive=True, contextAlive=True, windowAlive=True, receiverAlive=True,
                                    activeAttempt=not self.terminal and self.reason is None),
                      frame=None, availableFrames=len(self.frames), terminal=self.terminal)
        if call['operation'] == 'observe-current-consumption' and call['afterSequence'] < len(self.frames):
            source['frame'] = deepcopy(self.frames[call['afterSequence']])
        if self.reason:
            source['reason'] = self.reason
        self.raw = json.dumps(dict(picoWorldCurrentConsumptionVersion=1, commandId=call['commandId'], runId=RUN,
                    ownerToken=OWNER, instance='e'*32, sequence=self.sequence, processId=self.focus.pid,
                    requestedEpochMs=self.focus.epoch, capturedEpochMs=self.focus.epoch,
                    requestedMonotonicMs=self.focus.native_mono, capturedMonotonicMs=self.focus.native_mono,
                    status='unavailable' if self.reason else 'ready', source=source))

    def frame(self, kind, raw, *, origin='vr-key', event='7'*32):
        self.frames.append(dict(sequence=len(self.frames)+1, eventId=event, kind=kind, origin=origin,
                                epochMs=self.focus.epoch, monotonicMs=self.focus.native_mono,
                                raw=json.dumps(raw, ensure_ascii=True)))

    def keys(self):
        authority = self.focus.pair()['native']; target = authority['sourceIdentity'][len('web-entity:'):]
        return dict(keyboardObject='8'*32, keyEntity='00000000-0000-0000-0000-000000000009', keyType=0,
                    eventType='press', key=65, modifiers=0, textUtf16Hex='0061', requestedEntity=target)

    def jni(self, text='{"text":"a"}'):
        authority = self.focus.pair()['native']
        return dict({k: authority[k] for k in ('handle', 'creation', 'grant', 'page', 'url', 'sourceIdentity')},
                    commandUtf16Hex=text.encode('utf-16-be').hex(), commandUtf8Hex=text.encode('utf-8').hex())


class CurrentConsumptionReaderTests(unittest.TestCase):
    def setUp(self):
        # Preserve the exact source/raw failures; do not cold-adopt an old root.
        self.root = Path(tempfile.mkdtemp(prefix='pico-current-consumption-reader-'))
        self.root.chmod(0o700)
        print('Retained modeled trace originals:', self.root, flush=True)
        self.lock = ScriptSourceLock(self.root/'sources.lock')
        self.focus = CurrentBoundary(self.lock)
        self.focus.focused = True
        self.focus.current.read(RUN, URL, OWNER, 'observe-current-focus', 'text')
        self.boundary = TraceBoundary(self.focus)
        self.source = self.boundary.source

    def tearDown(self):
        (self.root/'originals.json').write_text(json.dumps(dict(calls=self.boundary.calls,
            retained=self.boundary.retained, frames=self.boundary.frames), indent=2))

    def test_same_owner_trace_retains_dispatch_release_truth_and_no_dom_verdict(self):
        arm = self.source.arm()
        self.assertIsNone(arm['source']['frame'])
        self.boundary.frame('keyboard-event', self.boundary.keys())
        command_raw = self.boundary.jni()
        self.boundary.frame('jni-command', command_raw)
        target = self.boundary.keys()['requestedEntity']
        self.boundary.frame('application-target', dict(eventType='press', requestedEntity=target,
            focusedBefore=target, handlerMatchesWindow=True, focusItemMatches=True, handled=True, focusedAfter=target))
        java_raw = {k: command_raw[k] for k in ('handle', 'grant', 'page', 'url', 'commandUtf16Hex', 'commandUtf8Hex')}
        self.boundary.frame('java-entry', dict(java_raw, isMainThread=False,
            capturedEpochMs=self.focus.epoch, capturedElapsedMs=self.focus.java_mono))
        self.boundary.frame('java-consume', dict(java_raw, before=self.focus.pair()['java'], after=self.focus.pair()['java']))
        # The real Keyboard generates release synchronously; it is not a DOM edit.
        release = dict(self.boundary.keys(), eventType='release')
        self.boundary.frame('keyboard-event', release, event='9'*32)
        self.boundary.frame('application-target', dict(eventType='release', requestedEntity=target,
            focusedBefore=target, handlerMatchesWindow=True, focusItemMatches=True, handled=False, focusedAfter=target), event='9'*32)
        self.boundary.terminal = True
        for cursor in range(7):
            packet = self.source.observe(cursor)
            self.assertEqual(cursor+1, packet['source']['frame']['sequence'])
            self.assertNotIn('featureSucceeded', packet)
            self.assertNotIn('domEffect', packet)
        self.assertFalse(packet['source']['frame']['raw'] == '{}')
        self.assertFalse(json.loads(packet['source']['frame']['raw'])['handled'])
        self.assertEqual(8, len(self.boundary.calls))
        self.assertEqual(16, len(self.boundary.retained))
        self.assertTrue(all(row['kind'] == ('request' if i % 2 == 0 else 'raw') for i, row in enumerate(self.boundary.retained)))
        original = self.source.original(); original['request']['ownerToken'] = '0'*32
        self.assertEqual(OWNER, self.source.original()['request']['ownerToken'])
        self.assertIsNone(self.source.observe(7)['source']['frame'])

    def test_unicode_encoding_is_exact_standard_utf8_not_modified_utf8(self):
        text = '{"text":"é😀"}'
        raw = self.boundary.jni(text)
        encoding(raw)
        modified = dict(raw, commandUtf8Hex=raw['commandUtf8Hex'].replace('f09f9880', 'eda0bdedb880'))
        with self.assertRaises(NativeUIError): encoding(modified)
        for replacement in ('3f', 'efbfbd'):
            malformed = dict(commandUtf16Hex='d800', commandUtf8Hex=replacement)
            with self.assertRaises(NativeUIError): encoding(malformed)
            encoding(malformed, unavailable=True)
        self.source.arm()
        self.boundary.frame('jni-command', raw, origin='qt-ime')
        packet = self.source.observe(0)
        self.assertEqual('qt-ime', packet['source']['frame']['origin'])
        self.assertEqual(text, bytes.fromhex(json.loads(packet['source']['frame']['raw'])['commandUtf8Hex']).decode())

    def test_native_key_and_separate_ime_raw_are_actual_data_not_consumption_verdict(self):
        self.source.arm()
        editor = deepcopy(self.focus.current.last['source']['nativeEditor'])
        key = dict(authority=self.focus.pair()['native'], editor=editor, eventType='key-press', key=65,
                   modifiers=0, textUtf16Hex='0061', commitUtf16Hex=None, preeditUtf16Hex=None,
                   replacementStart=None, replacementLength=None, attributes=[], accepted=False)
        self.boundary.frame('native-input', key)
        packet = self.source.observe(0)
        self.assertFalse(json.loads(packet['source']['frame']['raw'])['accepted'])
        ime = dict(key, eventType='ime', key=None, modifiers=None, textUtf16Hex=None,
                   commitUtf16Hex='00e9d83dde00', preeditUtf16Hex='', replacementStart=-1,
                   replacementLength=0, attributes=[dict(type=1, start=0, length=2)], accepted=True)
        self.boundary.frame('native-input', ime, origin='qt-ime', event='a'*32)
        packet = self.source.observe(1)
        self.assertEqual('qt-ime', packet['source']['frame']['origin'])
        self.assertEqual('00e9d83dde00', json.loads(packet['source']['frame']['raw'])['commitUtf16Hex'])
        self.boundary.frame('native-input', dict(ime, commitUtf16Hex='d800'), origin='qt-ime', event='b'*32)
        with self.assertRaises(NativeUIError): self.source.observe(2)
        with self.assertRaises(NativeUIError): self.source.original()

    def test_closed_commands_reject_bool_alias_unknown_fields_and_reused_nonce(self):
        self.source.arm(); call = deepcopy(self.boundary.calls[0])
        variants = [dict(call, extra=True), dict(call, schemaVersion=True), dict(call, focusNonce=call['commandId']),
                    dict(call, operation='commit-current-text')]
        observe = dict(call, operation='observe-current-consumption', attemptNonce=call['commandId'], afterSequence=0)
        observe.pop('focusNonce'); observe['commandId'] = '4'*32
        variants += [dict(observe, afterSequence=True), dict(observe, afterSequence=17), dict(observe, afterSequence=1.0)]
        for invalid in variants:
            with self.subTest(invalid=invalid), self.assertRaises((NativeUIError, ValueError)): command(invalid)
        self.assertEqual(1, len(self.boundary.calls))

    def test_foreign_or_malformed_raw_is_retained_before_refusal_without_new_arm(self):
        for fault in ('malformed', 'foreign', 'grant'):
            with self.subTest(fault=fault):
                boundary = TraceBoundary(self.focus); source = boundary.source; source.arm()
                boundary.frame('keyboard-event', boundary.keys())
                send = boundary.send
                def corrupt(call):
                    send(call)
                    if fault == 'malformed': boundary.raw = '{'
                    else:
                        packet = json.loads(boundary.raw)
                        if fault == 'foreign': packet['ownerToken'] = '0'*32
                        else: packet['source']['nativeAfter']['native']['grant'] += 1
                        boundary.raw = json.dumps(packet)
                source.send = corrupt
                with self.assertRaises((NativeUIError, ValueError)): source.observe(0)
                self.assertEqual(boundary.raw, boundary.retained[-1]['raw'])
                self.assertTrue(source.failed)
                with self.assertRaises(NativeUIError): source.arm()
                with self.assertRaises(NativeUIError): source.observe(0)
                self.assertEqual(2, len(boundary.calls))
                (self.root/(fault+'.json')).write_text(json.dumps(boundary.retained))

    def test_real_outer_exit_and_frozen_native_clock_do_not_renew_query(self):
        self.source.arm(); self.boundary.frame('keyboard-event', self.boundary.keys())
        held = self.lock.held
        @contextmanager
        def delayed_exit():
            with held(): yield
            self.assertIsNone(self.lock._owner)
            self.focus.elapsed += 2
        with patch.object(self.lock, 'held', delayed_exit), self.assertRaises(NativeUIError):
            self.source.observe(0)
        self.assertTrue(self.source.failed)
        self.assertEqual(2, len(self.boundary.calls))

    def test_original_skew_and_host_age_combine_and_correlate_work_counts(self):
        self.source.arm(); self.boundary.frame('keyboard-event', self.boundary.keys())
        original = self.source._correlate
        def slow(*args):
            original(*args); self.focus.elapsed += 2
        with patch.object(self.source, '_correlate', slow), self.assertRaises(NativeUIError): self.source.observe(0)
        self.assertEqual(0, self.source.cursor)
        self.assertEqual(2, len(self.boundary.calls))

    def test_original_query_clock_skew_plus_real_outer_exit_host_cost_refuses(self):
        self.source.arm(); self.boundary.frame('keyboard-event', self.boundary.keys())
        send = self.source.send
        def earlier(call):
            self.focus.epoch -= 200
            try: send(call)
            finally: self.focus.epoch += 200
        self.source.send = earlier
        held = self.lock.held
        @contextmanager
        def delayed_exit():
            with held(): yield
            self.focus.elapsed += 1.4
        with patch.object(self.lock, 'held', delayed_exit), self.assertRaises(NativeUIError): self.source.observe(0)
        self.assertEqual(0, self.source.cursor)
        self.assertEqual(2, len(self.boundary.calls))

    def test_same_nonce_pending_polls_are_bounded_original_reads_without_resend(self):
        self.source.arm()
        send = self.source.send
        def pending(call):
            send(call)
            packet = json.loads(self.boundary.raw); packet.update(status='pending', source={})
            self.boundary.raw = json.dumps(packet)
        self.source.send = pending
        with self.assertRaises(NativeUIError): self.source.observe(0)
        rows = self.boundary.retained[3:]
        self.assertEqual(31, len(rows))
        self.assertTrue(all(row['raw'] == rows[0]['raw'] and row['request'] == rows[0]['request'] for row in rows))
        self.assertEqual(2, len(self.boundary.calls))
        self.assertTrue(self.source.failed)

    def test_stale_focus_or_held_source_lock_refuses_before_transport(self):
        self.focus.elapsed += 2
        with self.assertRaises(NativeUIError): self.source.arm()
        self.assertEqual([], self.boundary.calls)
        self.focus.elapsed -= 2
        with self.lock.held():
            with self.assertRaises(NativeUIError): self.source.arm()
        self.assertEqual([], self.boundary.calls)

    def test_delayed_durable_request_lock_or_guard_refuses_before_first_send(self):
        elapsed = self.focus.elapsed
        for fault in ('retention', 'lock', 'guard', 'clock'):
            with self.subTest(fault=fault):
                self.focus.elapsed = elapsed
                boundary = TraceBoundary(self.focus); source = boundary.source
                held = self.lock.held
                @contextmanager
                def admission():
                    with held():
                        if fault == 'lock': self.focus.elapsed += 2
                        yield
                if fault == 'retention':
                    def durable(row):
                        boundary.retained.append(deepcopy(row)); self.focus.elapsed += 2
                    source.retain = durable
                if fault == 'guard':
                    guards = []
                    def lifetime():
                        guards.append(True)
                        if len(guards) == 2: self.focus.elapsed += 2
                        return True
                    source.guard = lifetime
                if fault == 'clock':
                    original_clock=source.clock_ms; delayed=[]
                    def slow_epoch():
                        if self.lock._owner is not None and not delayed:
                            delayed.append(True);self.focus.elapsed += 2
                        return original_clock()
                    source.clock_ms=slow_epoch
                with patch.object(self.lock, 'held', admission), self.assertRaises(NativeUIError): source.arm()
                self.assertTrue(source.issued and source.failed)
                self.assertEqual([], boundary.calls)
                self.assertEqual(['request'], [row['kind'] for row in boundary.retained])
                with self.assertRaises(NativeUIError): source.arm()

    def test_cumulative_host_age_is_fixed_at_arm_even_with_frozen_source_clocks(self):
        self.source.arm()
        for i in range(6): self.boundary.frame('keyboard-event', self.boundary.keys(), event=f'{i+1:032x}')
        for cursor in range(5):
            self.focus.elapsed += 1
            self.source.observe(cursor)
        self.focus.elapsed += .01
        with self.assertRaises(NativeUIError): self.source.observe(5)
        self.assertEqual(5, self.source.cursor)

    def test_lost_send_return_is_never_retried_and_raw_request_remains_owned(self):
        send = self.source.send
        def lost(call): send(call); raise RuntimeError('lost original send return')
        self.source.send = lost
        with self.assertRaises(RuntimeError): self.source.arm()
        self.assertTrue(self.source.issued and self.source.failed)
        self.assertEqual('request', self.boundary.retained[0]['kind'])
        with self.assertRaises(NativeUIError): self.source.arm()
        self.assertEqual(1, len(self.boundary.calls))

    def test_unavailable_encoding_retains_literal_raw_and_false_weak_is_not_retirement(self):
        self.source.arm(); self.boundary.reason = 'encoding-unavailable'
        self.boundary.frame('jni-command', dict(self.boundary.jni(), commandUtf16Hex='d800', commandUtf8Hex='3f'))
        with self.assertRaises(NativeUIError): self.source.observe(0)
        packet = json.loads(self.boundary.retained[-1]['raw'])
        self.assertEqual('d800', json.loads(packet['source']['frame']['raw'])['commandUtf16Hex'])
        self.assertTrue(packet['source']['lifetime']['receiverAlive'])
        self.assertNotIn('retired', packet['source'])

    def test_wrong_frame_cursor_event_join_scope_or_global_sequence_refuses(self):
        for fault in ('cursor', 'event', 'origin', 'sequence'):
            with self.subTest(fault=fault):
                boundary = TraceBoundary(self.focus); source = boundary.source; source.arm()
                boundary.frame('jni-command', boundary.jni()); source.observe(0)
                java = {k: boundary.jni()[k] for k in ('handle', 'grant', 'page', 'url', 'commandUtf16Hex', 'commandUtf8Hex')}
                boundary.frame('java-entry', dict(java, isMainThread=False, capturedEpochMs=self.focus.epoch,
                               capturedElapsedMs=self.focus.java_mono), event='0'*32 if fault == 'event' else '7'*32,
                               origin='qt-key' if fault == 'origin' else 'vr-key')
                send = source.send
                def corrupt(call):
                    send(call)
                    packet = json.loads(boundary.raw)
                    if fault == 'cursor': packet['source']['frame']['sequence'] = 1
                    if fault == 'sequence': packet['sequence'] = 2
                    boundary.raw = json.dumps(packet)
                source.send = corrupt
                with self.assertRaises(NativeUIError): source.observe(1)
                self.assertEqual(1, source.cursor)
                self.assertEqual(3, len(boundary.calls))
                (self.root/(fault+'-join.json')).write_text(json.dumps(boundary.retained))

    def test_old_java_original_cannot_borrow_fresh_native_collection_clock(self):
        self.source.arm()
        raw = self.boundary.jni()
        self.boundary.frame('jni-command', raw); self.source.observe(0)
        java = {k: raw[k] for k in ('handle', 'grant', 'page', 'url', 'commandUtf16Hex', 'commandUtf8Hex')}
        self.boundary.frame('java-entry', dict(java, isMainThread=False,
            capturedEpochMs=self.focus.epoch-2000, capturedElapsedMs=self.focus.java_mono))
        with self.assertRaises(NativeUIError): self.source.observe(1)
        packet = json.loads(self.boundary.retained[-1]['raw'])
        self.assertEqual(self.focus.epoch, packet['source']['frame']['epochMs'])
        self.assertEqual(self.focus.epoch-2000, json.loads(packet['source']['frame']['raw'])['capturedEpochMs'])
        self.assertEqual(1, self.source.cursor)

    def test_full_original_probe_dispatcher_keeps_native_packets_and_missing_source_empty(self):
        result = subprocess.run(['node', str(HERE/'world-current-consumption-probe-test.js')],
                                cwd=ROOT, check=True, text=True, capture_output=True, timeout=10)
        self.assertIn('World consumption probe', result.stdout)


if __name__ == '__main__':
    unittest.main()
