"""Real cold BoundAdapter constructors; explicit Native/SDK host models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import os
import subprocess
import unittest
from unittest.mock import patch

from adapters.chat_journey.archive_file import signature
from adapters.normal_ui import NativeUIError
from adapters.pico4.emote_stream_capture import PicoEmoteStreamCapture
from adapters.pico4.emote_stream_factory import FILES
from adapters.pico4.probe_originals import same_callable
from self_tests.pico_emote_stream_fixture import RUN
from self_tests.pico_emote_stream_factory_fixture import FactoryModel

RETAINED=[]


class StreamFactoryTests(unittest.TestCase):
    def setUp(self):
        self.model=FactoryModel();self.addCleanup(self.finalize)
        print('Retained canonical factory model originals:',*[str(root) for root in self.model.roots],flush=True)

    def finalize(self):
        def inventory():return {str(path):dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),physical=signature(path.stat()))
            for root in self.model.roots for path in root.rglob('*') if path.is_file()}
        before=inventory();self.model.close();after=inventory();self.assertEqual(before,after)
        self.assertTrue(all(root.is_dir() for root in self.model.roots))
        RETAINED.append(dict(roots=[str(root) for root in self.model.roots],files=after,originalModelCloseCalled=True))

    def prepared(self):
        m=self.model
        with m.m.s.lock.held():cycle=m.create()
        with cycle.held():
            cycle.baseline();cycle.act(m.m.input.call('open'));cycle.act(m.m.input.call('play',{'name':'Waving'}))
            capture,factory=m.factory_capture(cycle)
        return cycle,capture,factory,cycle.parent.state['steps'][1]['call']['ticket']

    def test_actual_private_factory_constructs_on_same_parent_before_any_runtime_source_or_gpu(self):
        cycle,capture,factory,ticket=self.prepared();m=self.model
        self.assertIs(type(capture),PicoEmoteStreamCapture);self.assertIs(capture.cycle,cycle)
        self.assertIs(factory.capture,capture);self.assertIs(factory.archive,cycle.originals.archive)
        self.assertIs(factory.source,cycle.streams['actor']);self.assertEqual([],m.runtime_calls)
        self.assertEqual([],m.native_commands);self.assertEqual([],m.normal_inputs)
        with cycle.held():self.assertTrue(factory.guard())

    def test_actual_initial_marker_noise_nul_wire_retained_before_cold_constructor_parser_or_gpu(self):
        m=self.model;noise=b'\xff'+os.urandom(262142)+b'\0'
        m.runtime_corrupt=lambda kind,raw:noise if kind=='control-marker' else raw
        cycle,capture,factory,ticket=self.prepared()
        with cycle.held(),self.assertRaises(NativeUIError):capture.acquire(ticket)
        self.assertEqual(1,len(m.runtime_calls));self.assertEqual('control-marker',m.runtime_calls[0]['kind'])
        self.assertTrue(factory.failed);self.assertEqual([],m.native_commands);self.assertEqual([],m.normal_inputs)
        archive=cycle.originals.archive
        records=[row for page in archive.pages.values() for row in page['receipts'] if row is not None
            and row['role']=='emote-stream-runtime']
        self.assertEqual(1,len(records));record=records[0]
        with cycle.held():wire=archive.literal(dict(audioRawRangeVersion=1,scopeSha256=archive.scope_sha,
            read=record['read'],sha256=record['sha256']))
        self.assertEqual(m.runtime_calls[0]['wire'],wire);self.assertIn(noise,wire)
        self.assertEqual(capture._component_started,factory.calls[0][3])

    def runtime_originals(self,cycle):
        archive=cycle.originals.archive
        records=[row for page in archive.pages.values() for row in page['receipts'] if row is not None
            and row['role']=='emote-stream-runtime']
        with cycle.held():
            originals=[archive.literal(dict(audioRawRangeVersion=1,scopeSha256=archive.scope_sha,
                read=row['read'],sha256=row['sha256'])) for row in records]
        return records,originals

    def test_actual_first_ui_original_is_hooked_before_picoscriptio_constructor_parser(self):
        m=self.model;noise=b'\xff'+os.urandom(1023)+b'\0'
        m.runtime_corrupt=lambda kind,raw:noise if kind=='ui-observation' else raw
        cycle,capture,factory,ticket=self.prepared()
        with cycle.held(),self.assertRaises(NativeUIError):capture.acquire(ticket)
        self.assertEqual(['control-marker','probe','ui-observation'],[row['kind'] for row in m.runtime_calls])
        records,raw=self.runtime_originals(cycle);self.assertEqual(3,len(records))
        self.assertEqual(m.runtime_calls[-1]['wire'],raw[-1]);self.assertIn(noise,raw[-1])
        self.assertTrue(factory.failed);self.assertEqual([],m.native_commands);self.assertEqual([],m.normal_inputs)

    def test_actual_issued_initial_wire_after_original_expiry_is_retained_before_guard_without_new_getter(self):
        m=self.model;returned=[]
        def late(wire):returned.append(wire);m.m.tick(5000);return wire
        m.runtime_after_wire=late;cycle,capture,factory,ticket=self.prepared()
        with cycle.held(),self.assertRaises(NativeUIError):capture.acquire(ticket)
        records,raw=self.runtime_originals(cycle);self.assertEqual(1,len(records));self.assertEqual(returned,raw)
        before=len(m.runtime_calls)
        with self.assertRaises(NativeUIError):factory.original_reader('actor-model','org.overte.pico',FILES['probe'])
        self.assertEqual(before,len(m.runtime_calls));self.assertEqual([],m.native_commands)
        self.assertEqual(capture._component_started,factory.calls[0][3])

    def test_actual_partial_initial_sdk_timeout_bytes_are_original_and_never_retried(self):
        m=self.model;returned=[]
        def partial(wire):
            returned.append(wire[:173]);raise subprocess.TimeoutExpired('declared fixed-file SDK',5,output=wire[:173])
        m.runtime_after_wire=partial;cycle,capture,factory,ticket=self.prepared()
        with cycle.held(),self.assertRaises(NativeUIError):capture.acquire(ticket)
        records,raw=self.runtime_originals(cycle);self.assertEqual(1,len(records));self.assertEqual(returned,raw)
        self.assertTrue(factory.failed);self.assertEqual([],m.native_commands);self.assertEqual(1,len(m.runtime_calls))

    def first_callback_reentry(self,kind):
        cycle,capture,factory,ticket=self.prepared();m=self.model;claims=[]
        def reenter():
            claim=factory.active;self.assertIsNotNone(claim);self.assertIs(claim,factory.calls[-1]);claims.append(claim)
            self.assertEqual([],m.runtime_calls)
            with self.assertRaises(NativeUIError):factory.original_reader('actor-model','org.overte.pico',FILES['probe'])
            self.assertIs(factory.active,claim) # Rejected nested call never clears the outer ownership.
            self.assertEqual([],m.runtime_calls)
        def arm():setattr(m,kind,reenter)
        m.before_runtime_process=arm
        with cycle.held(),self.assertRaises(NativeUIError):capture.acquire(ticket)
        self.assertEqual(1,len(claims));self.assertIs(claims[0],factory.calls[0])
        self.assertEqual(capture._component_started,claims[0][3]);self.assertTrue(factory.failed)
        self.assertEqual([],m.runtime_calls);self.assertEqual([],m.native_commands)
        self.assertEqual([],m.normal_inputs)

    def test_first_clock_callback_reentry_is_refused_before_getter_and_keeps_original_outer_claim(self):
        self.first_callback_reentry('first_clock')

    def test_first_original_native_guard_reentry_is_refused_before_getter_and_keeps_original_outer_claim(self):
        self.first_callback_reentry('first_guard')

    def test_foreign_target_and_callback_swaps_refuse_before_runtime_getter_or_gpu(self):
        cycle,capture,factory,ticket=self.prepared();m=self.model
        with cycle.held():
            with self.assertRaises(ValueError):m.adapter._emote_stream_capture('foreign-model','actor-model',cycle,2)
            with self.assertRaises(NativeUIError):factory.controlled_original('foreign-model','org.overte.pico',FILES['probe'])
            factory.original_reader=lambda *args,**options:None
            with self.assertRaises(NativeUIError):factory.guard()
        self.assertEqual([],m.runtime_calls);self.assertEqual([],m.native_commands);self.assertEqual([],m.normal_inputs)

    def test_actual_admitted_reader_clock_substitution_refuses_before_any_further_sdk_or_gpu(self):
        cycle,capture,factory,ticket=self.prepared();m=self.model;admitted=[];original=factory.bind_producer
        def admit_then_substitute(reader):
            original(reader)
            self.assertTrue(same_callable(reader.monotonic,factory.source.monotonic))
            if not admitted:
                admitted.append((m.process_calls,len(m.runtime_calls),len(m.native_commands)))
                reader.monotonic=lambda:1e12
        with patch.object(factory,'bind_producer',side_effect=admit_then_substitute),cycle.held(),self.assertRaises(NativeUIError):
            capture.acquire(ticket)
        self.assertEqual(1,len(admitted));self.assertEqual(admitted[0],
            (m.process_calls,len(m.runtime_calls),len(m.native_commands)))
        self.assertEqual([],m.native_commands);self.assertEqual([],m.normal_inputs)

    def test_expiry_in_original_cold_process_query_stops_before_initial_file_getter_without_new_clock(self):
        cycle,capture,factory,ticket=self.prepared();m=self.model;expired=[]
        def expire():m.m.tick(5000);expired.append(m.process_calls)
        m.before_runtime_process=expire
        with cycle.held(),self.assertRaises(NativeUIError):capture.acquire(ticket)
        self.assertEqual([m.process_calls],expired);self.assertEqual([],m.runtime_calls)
        self.assertEqual([],m.native_commands);self.assertEqual([],m.normal_inputs)
        self.assertEqual(capture._component_started,factory.calls[0][3])

    def test_actual_canonical_factory_capture_complete_normal_cancel_close_quiet_and_original_drain(self):
        cycle,capture,factory,ticket=self.prepared();m=self.model
        anchors=tuple(cycle.parent.state[key] for key in ('started','epochMs','hostEpochMs'))
        with cycle.held():waiting=capture.acquire(ticket)
        self.assertTrue(factory.producers)
        self.assertTrue(all(same_callable(reader.monotonic,factory.source.monotonic)
            for reader,clock,original,wrapped in factory.producers))
        self.assertTrue(waiting['awaitingAutonomousNativeSample']);m.m.tick(500)
        with cycle.held():
            frame=capture.complete();original,raw=capture.original()
            self.assertEqual(frame,original);self.assertEqual(m.renderer.raw,raw)
            self.assertLess(frame['avatarBefore']['sampleSequence'],frame['avatarAfter']['sampleSequence'])
            cycle.act(m.m.input.call('cancel'));cycle.act(m.m.input.call('close'))
            m.m.s.journal.activate(RUN,'f'*32,'cleanup');quiet=cycle.cleanup(sleep=m.m.sleep)
            self.assertGreaterEqual(quiet['originalParentNativeQuiet']['nativeQuiet']['window']['elapsedMs'],3000)
        for producer in m.streams.values():producer.event_loop_turn()
        with cycle.held():
            result=cycle.drain();self.assertTrue(result['sourceDrained'])
            self.assertFalse(result['wholeFeatureComplete'] or result['stereoQualified'] or result['independentActorQualified'])
        self.assertEqual(anchors,tuple(cycle.parent.state[key] for key in ('started','epochMs','hostEpochMs')))
        self.assertTrue(factory.references);self.assertEqual([],m.normal_inputs)
