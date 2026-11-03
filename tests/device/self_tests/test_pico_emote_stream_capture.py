"""Source4→original render/PNG/retirement composition; declared native models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
from copy import deepcopy
import json
import os

from adapters.normal_ui import NativeUIError
from adapters.pico4.emote_stream_draws import remote_draws
from adapters.pico4.emote_model_draws import FILE as MODEL_FILE
from adapters.script_journey.history import unpack
import unittest

from adapters.chat_journey.archive_file import signature
from adapters.pico4.emote_stream_capture import PicoEmoteStreamCapture,OWNED,UNRESOLVED
from adapters.pico4.emote_stream_model_raw import PicoEmoteStreamModelRaw
from adapters.pico4.emote_stream_world_raw import PicoEmoteStreamWorldRaw
from self_tests.pico_emote_stream_capacity_cycle_fixture import CapacityCycleModel as StreamCaptureModel
from self_tests.pico_emote_stream_fixture import RUN

RETAINED=[]


class StreamCaptureBase(unittest.TestCase):
    def setUp(self):
        self.model=StreamCaptureModel();self.addCleanup(self.finalize)
        print('Retained actual Source4 render/storage/source model roots:',*[str(root) for root in self.model.roots],flush=True)

    def finalize(self):
        def inventory():return {str(path):dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),physical=signature(path.stat()))
            for root in self.model.roots for path in root.rglob('*') if path.is_file()}
        before=inventory();self.model.close();after=inventory();self.assertEqual(before,after)
        self.assertTrue(all(root.is_dir() for root in self.model.roots));RETAINED.append(dict(roots=[str(root) for root in self.model.roots],files=after))

    def prepared(self,*,models=None):
        m=self.model
        with m.m.s.lock.held():cycle=m.create()
        with cycle.held():
            cycle.baseline();cycle.act(m.m.input.call('open'));cycle.act(m.m.input.call('play',{'name':'Waving'}))
            capture=PicoEmoteStreamCapture(cycle,1,m.world,m.models if models is None else models);m.captures.append(capture)
        return cycle,capture,cycle.parent.state['steps'][1]['call']['ticket']


class StreamCaptureTests(StreamCaptureBase):
    def test_same_parent_passive_sample_ids_bracket_actual_stereo_png_and_original_retirement(self):
        m=self.model
        with m.m.s.lock.held():cycle=m.create()
        with cycle.held():
            cycle.baseline();cycle.act(m.m.input.call('open'));played=cycle.act(m.m.input.call('play',{'name':'Waving'}))
            anchors=tuple(cycle.parent.state[key] for key in ('started','epochMs','hostEpochMs'))
            capture=PicoEmoteStreamCapture(cycle,1,m.world,m.models);m.captures.append(capture)
            ticket=cycle.parent.state['steps'][1]['call']['ticket'];waiting=capture.acquire(ticket)
            self.assertTrue(waiting['awaitingAutonomousNativeSample']);self.assertFalse(waiting['wholeFeatureComplete'] or waiting['stereoQualified'])
            self.assertEqual('awaiting-after',capture.state['phase']);self.assertTrue(m.storage.present)
            self.assertIsNotNone(m.world_store().read());started=capture.state['started']
        # No SourceLock is held while the autonomous modeled GUI clock emits.
        m.m.tick(500)
        with cycle.held():
            frame=capture.complete();original,raw=capture.original()
            self.assertEqual(frame,original);self.assertEqual(m.renderer.raw,raw)
            self.assertLess(frame['avatarBefore']['sampleSequence'],frame['avatarAfter']['sampleSequence'])
            self.assertNotIn('requestId',frame['avatarBefore']);self.assertNotIn('requestId',frame['avatarAfter'])
            self.assertEqual(started,capture.state['started']);self.assertIsNone(m.world_store().read())
            self.assertFalse(m.storage.present);self.assertTrue(all(not row['exists'] for row in capture.state['inventory']['source']['receipts']))
            self.assertEqual(1,len(m.renderer.commands));self.assertEqual(1,len(m.model_commands))
            self.assertEqual(['left','right'],[use['eye'] for use in frame['draws']['source']['modelTrace']['models'][0]['cameraUses']])
            # Pure replay counters retain the original positive graph. Neither
            # a repeated passive sample nor a missing used-eye row is accepted.
            before_counts=(len(m.renderer.commands),len(m.model_commands),sum(p.getters for p in m.streams.values()))
            repeated=deepcopy(frame);repeated['avatarAfter']=deepcopy(repeated['avatarBefore'])
            with self.assertRaises(NativeUIError):remote_draws(repeated['primary'],repeated['avatarBefore'],repeated['avatarAfter'],
                repeated['capture'],repeated['draws'],capture.pid,capture.source.clock_ms())
            missing_eye=deepcopy(frame);missing_eye['draws']['source']['modelTrace']['models'][0]['cameraUses'].pop()
            with self.assertRaises(NativeUIError):remote_draws(missing_eye['primary'],missing_eye['avatarBefore'],missing_eye['avatarAfter'],
                missing_eye['capture'],missing_eye['draws'],capture.pid,capture.source.clock_ms())
            self.assertEqual(before_counts,(len(m.renderer.commands),len(m.model_commands),sum(p.getters for p in m.streams.values())))
            self.assertEqual(anchors,tuple(cycle.parent.state[key] for key in ('started','epochMs','hostEpochMs')))
            cycle.act(m.m.input.call('cancel'));cycle.act(m.m.input.call('close'))
            m.m.s.journal.activate(RUN,'f'*32,'cleanup');quiet=cycle.cleanup(sleep=m.m.sleep)
            self.assertGreaterEqual(quiet['originalParentNativeQuiet']['nativeQuiet']['window']['elapsedMs'],3000)
        for producer in m.streams.values():producer.event_loop_turn()
        with cycle.held():
            result=cycle.drain();self.assertTrue(result['sourceDrained'])
            self.assertFalse(result['wholeFeatureComplete'] or result['stereoQualified'] or result['independentActorQualified'])
            self.assertEqual(['arm','stop','drain'],[request['operation'] for request in m.streams['actor'].controls])


class StreamCaptureFenceTests(StreamCaptureBase):
    def test_equal_bytes_memory_graph_replacement_refuses_before_new_source_or_gpu(self):
        cycle,capture,ticket=self.prepared();m=self.model
        counts=(sum(p.getters for p in m.streams.values()),len(m.renderer.commands),len(m.model_commands))
        capture.state=deepcopy(capture.state)
        with cycle.held(),self.assertRaises(NativeUIError):capture.acquire(ticket)
        self.assertEqual(counts,(sum(p.getters for p in m.streams.values()),len(m.renderer.commands),len(m.model_commands)))
        self.assertIsNone(capture.store.read())

    def test_mutated_component_clock_cannot_be_admitted_by_remember(self):
        cycle,capture,ticket=self.prepared();m=self.model
        capture.state['started']=m.m.s.clock+100
        with cycle.held(),self.assertRaises(NativeUIError):capture.remember('failure','caller-candidate')
        self.assertIsNone(capture.store.read());self.assertEqual([],m.renderer.commands)

    def test_factory_replacement_refuses_before_any_source_or_gpu(self):
        cycle,capture,ticket=self.prepared();m=self.model
        counts=sum(p.getters for p in m.streams.values());capture.world=lambda:None
        with cycle.held(),self.assertRaises(NativeUIError):capture.acquire(ticket)
        self.assertEqual(counts,sum(p.getters for p in m.streams.values()));self.assertEqual([],m.renderer.commands)

    def test_actual_completed_intent_cas_lost_ack_is_sticky_and_sends_zero_gpu(self):
        cycle,capture,ticket=self.prepared();m=self.model;write=capture.file.write;lost=[]
        def write_then_lose(value,previous):
            write(value,previous)
            if unpack(value['payload'])[0]['captureIntent'] is not None:
                lost.append(deepcopy(value));raise OSError('Actual completed capture intent CAS return lost')
        capture.file.write=write_then_lose
        with cycle.held(),self.assertRaises(NativeUIError):capture.acquire(ticket)
        self.assertEqual(1,len(lost));self.assertTrue(capture.failed)
        self.assertEqual(lost[0],capture.store.read());self.assertIsNotNone(unpack(capture.store.read()['payload'])[0]['captureIntent'])
        self.assertEqual([],m.renderer.commands);self.assertEqual([],m.model_commands)
        with cycle.held(),self.assertRaises(NativeUIError):capture.acquire(ticket)
        self.assertEqual([],m.renderer.commands)

    def test_original_five_second_expiry_before_complete_sends_zero_new_queries(self):
        cycle,capture,ticket=self.prepared();m=self.model
        with cycle.held():capture.acquire(ticket)
        started=capture.state['started'];counts=(sum(p.getters for p in m.streams.values()),len(m.renderer.commands),
            len(m.model_commands),len(m.storage.commands))
        m.m.tick(5000)
        with cycle.held(),self.assertRaises(NativeUIError):capture.complete()
        self.assertEqual(started,capture.state['started']);self.assertEqual(counts,(sum(p.getters for p in m.streams.values()),
            len(m.renderer.commands),len(m.model_commands),len(m.storage.commands)))
        self.assertTrue(m.storage.present);self.assertIsNotNone(m.world_store().read())
        self.assertEqual('awaiting-after',capture.state['phase'])

    def test_actual_near_cap_noise_and_nul_model_wire_retained_before_parser(self):
        m=self.model;noise=os.urandom(262143)+b'\0'
        def models():
            reader=m.models();send=reader.send
            def malformed(request):
                send(request);path=m.streams['actor'].sample.parent/MODEL_FILE
                path.write_bytes(noise);path.chmod(0o600)
            reader.send=malformed;return reader
        cycle,capture,ticket=self.prepared(models=models)
        with cycle.held(),self.assertRaises(NativeUIError):capture.acquire(ticket)
        archive=cycle.originals.archive
        records=[row for page in archive.pages.values() for row in page['receipts'] if row is not None
            and row['role']=='emote-stream-model' and row['command'].get('wireRead')]
        self.assertEqual(1,len(records));record=records[0]
        with cycle.held():
            wire=archive.literal(dict(audioRawRangeVersion=1,scopeSha256=archive.scope_sha,read=record['read'],sha256=record['sha256']))
        self.assertIn(noise,wire);self.assertEqual(1,len(m.model_commands));self.assertEqual(1,len(m.renderer.commands))
        self.assertTrue(m.storage.present);self.assertIsNotNone(m.world_store().read())
        self.assertIsNone(capture.state['draws'])


class StreamWorldWireTests(StreamCaptureBase):
    def wire_records(self,cycle):
        archive=cycle.originals.archive
        return archive,[row for page in archive.pages.values() for row in page['receipts'] if row is not None
            and row['role']=='emote-stream-world' and row['command'].get('wireNonce')]

    def original_wire(self,cycle,archive,record):
        with cycle.held():return archive.literal(dict(audioRawRangeVersion=1,scopeSha256=archive.scope_sha,
            read=record['read'],sha256=record['sha256']))

    def test_actual_world_invalid_utf8_near_cap_and_nul_retained_before_decode(self):
        from adapters.world_render_evidence import FILE as WORLD_FILE
        m=self.model;noise=os.urandom(262143)+b'\0';send=m.renderer.send
        def malformed(command):
            send(command);path=m.scope_root/WORLD_FILE;path.write_bytes(noise);path.chmod(0o600)
        m.renderer.send=malformed
        cycle,capture,ticket=self.prepared()
        with cycle.held(),self.assertRaises(NativeUIError):capture.acquire(ticket)
        archive,records=self.wire_records(cycle);self.assertEqual(1,len(records))
        self.assertIn(noise,self.original_wire(cycle,archive,records[0]));self.assertEqual(1,len(m.renderer.commands))
        self.assertEqual([],m.model_commands);self.assertTrue(m.storage.present);self.assertIsNotNone(m.world_store().read())
        self.assertIsNone(capture.state['capture']);self.assertIn(capture,UNRESOLVED)

    def test_actual_issued_world_wire_return_after_expiry_is_retained_without_new_query(self):
        m=self.model;returned=[]
        def expire(wire):returned.append(wire);m.m.tick(5000);return wire
        m.world_wire_fault=expire
        cycle,capture,ticket=self.prepared()
        with cycle.held(),self.assertRaises(NativeUIError):capture.acquire(ticket)
        archive,records=self.wire_records(cycle);self.assertEqual(1,len(returned));self.assertEqual(1,len(records))
        self.assertEqual(returned[0],self.original_wire(cycle,archive,records[0]))
        self.assertEqual(1,len(m.renderer.commands));self.assertEqual([],m.model_commands)
        self.assertIsNone(capture.state['capture']);self.assertTrue(m.storage.present);self.assertIsNotNone(m.world_store().read())

    def test_actual_world_partial_timeout_prefix_is_retained_and_never_retried(self):
        import subprocess
        m=self.model;returned=[]
        def timeout(wire):
            returned.append(wire[:113]);raise subprocess.TimeoutExpired('actual fixed-file modeled transport',5,output=wire[:113])
        m.world_wire_fault=timeout
        cycle,capture,ticket=self.prepared()
        with cycle.held(),self.assertRaises(NativeUIError):capture.acquire(ticket)
        archive,records=self.wire_records(cycle);self.assertEqual(1,len(returned));self.assertEqual(1,len(records))
        self.assertEqual(returned[0],self.original_wire(cycle,archive,records[0]))
        self.assertEqual(1,len(m.renderer.commands));self.assertEqual([],m.model_commands)
        self.assertIsNone(capture.state['capture']);self.assertTrue(m.storage.present);self.assertIsNotNone(m.world_store().read())


class StreamRawIdentityTests(StreamCaptureBase):
    def test_model_raw_callback_and_clock_replacement_refuse_before_send(self):
        cycle,capture,ticket=self.prepared();m=self.model
        with cycle.held():
            for field in ('send','clock','native_guard'):
                raw=PicoEmoteStreamModelRaw(capture,m.models())
                setattr(raw,field,lambda *args:True)
                with self.assertRaises(NativeUIError):raw.guard()
        self.assertEqual([],m.model_commands);self.assertEqual([],m.renderer.commands)

    def test_world_raw_saved_getter_and_mutable_catalog_replacement_refuse_before_send(self):
        cycle,capture,ticket=self.prepared();m=self.model
        with cycle.held():
            raw=PicoEmoteStreamWorldRaw(capture);selected=m.world().capture;raw.bind(selected,'world',262144)
            raw.bindings[0]['get']=lambda:None
            with self.assertRaises(NativeUIError):selected.original()
            raw2=PicoEmoteStreamWorldRaw(capture);selected2=m.world().capture;raw2.bind(selected2,'world',262144)
            raw2.configs=tuple(list(raw2.configs))
            # Force a different tuple even when an implementation interns a
            # one-element tuple construction.
            raw2.configs=(*raw2.configs,)
            self.assertIsNot(raw2.configs,raw2._configs)
            with self.assertRaises(NativeUIError):selected2.original()
        self.assertEqual([],m.renderer.commands);self.assertEqual([],m.model_commands)

    def test_actual_owner_stays_strong_after_unknown_intent_and_traceback_loss(self):
        cycle,capture,ticket=self.prepared();m=self.model;write=capture.file.write
        def lose(value,previous):
            write(value,previous)
            if unpack(value['payload'])[0]['captureIntent'] is not None:raise OSError('Actual intent CAS lost')
        capture.file.write=lose
        with cycle.held(),self.assertRaises(NativeUIError):capture.acquire(ticket)
        import gc,os,weakref
        reference=weakref.ref(capture);fd=capture.file.parent.fd;physical=os.fstat(fd)
        m.captures.remove(capture);del capture;gc.collect()
        retained=reference();self.assertIsNotNone(retained);self.assertIn(retained,OWNED);self.assertIn(retained,UNRESOLVED)
        self.assertEqual(physical,os.fstat(fd));self.assertEqual([],m.renderer.commands)
        m.captures.append(retained)


if __name__=='__main__':unittest.main()
