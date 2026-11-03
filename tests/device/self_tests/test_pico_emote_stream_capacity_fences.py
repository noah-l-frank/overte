"""Actual opt-in Cycle/Role4/capacity integration fences; no Native execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.normal_ui import NativeUIError
from adapters.pico4.emote_stream_capture import PicoEmoteStreamCapture
from adapters.script_journey.history import unpack
from self_tests.test_pico_emote_stream_capacity_cycle import StreamCapacityCycleTests,RETAINED


class StreamCapacityIntegrationFences(StreamCapacityCycleTests):
    # Explicit owning selection excludes inherited positive integration cases.
    def prepare(self,*,baseline=False):
        m=self.model
        with m.m.s.lock.held():cycle=m.create()
        if baseline:
            with cycle.held():cycle.baseline()
        return cycle

    def capture_ready(self):
        m=self.model;cycle=self.prepare(baseline=True)
        with cycle.held():
            cycle.act(m.m.input.call('open'));cycle.act(m.m.input.call('play',{'name':'Waving'}))
            capture=PicoEmoteStreamCapture(cycle,1,m.world,m.models);m.captures.append(capture)
        return cycle,capture,cycle.parent.state['steps'][1]['call']['ticket']

    def test_passive_prelock_identity_reads_no_source_and_cannot_authorize_unheld_admission(self):
        m=self.model;cycle=self.prepare();before=(deepcopy(m.m.s.calls),sum(p.getters for p in m.streams.values()))
        self.assertTrue(cycle.capacity.resource_identity());cycle.identity()
        with self.assertRaises(NativeUIError):cycle.capacity.require()
        with self.assertRaises(NativeUIError):cycle.capacity.receipt('actor',dict())
        self.assertEqual(before,(m.m.s.calls,sum(p.getters for p in m.streams.values())))
        self.assertFalse(any(producer.controls for producer in m.streams.values()));self.assertEqual([],m.renderer.commands)

    def test_actual_policy2_capacity_graph_substitution_refuses_before_any_new_getter_or_native_send(self):
        m=self.model;cycle=self.prepare(baseline=True);before=(sum(p.getters for p in m.streams.values()),
            [len(p.controls) for p in m.streams.values()],len(m.renderer.commands))
        cycle.capacity.state=deepcopy(cycle.capacity.state)
        with self.assertRaises(NativeUIError):
            with cycle.held():cycle.sample_pair()
        self.assertEqual(before,(sum(p.getters for p in m.streams.values()),[len(p.controls) for p in m.streams.values()],len(m.renderer.commands)))

    def test_real_storage_capacity_cas_completed_then_lost_ack_sends_zero_storage_and_keeps_gpu_intent(self):
        m=self.model;cycle,capture,ticket=self.capture_ready();capacity=cycle.capacity;write=capacity.file.write;lost=[]
        def unknown(value,previous):
            write(value,previous)
            if unpack(value['payload'])[0]['receipts']:
                lost.append(deepcopy(value));raise OSError('Actual integrated receipt capacity CAS return lost')
        capacity.file.write=unknown
        with self.assertRaises(NativeUIError):
            with cycle.held():capture.acquire(ticket)
        self.assertEqual(1,len(lost));self.assertEqual(lost[0],capacity.store.read());self.assertTrue(capacity.failed)
        self.assertEqual([],capacity.state['receipts']);self.assertEqual([],m.storage.commands)
        self.assertEqual(1,len(m.renderer.commands));self.assertTrue(m.storage.present);self.assertIsNotNone(m.world_store().read())
        self.assertTrue(any(row['role']=='emote-stream-storage' for row in cycle.originals.archive.state['pending']))

    def test_ignored_actual_native_receipt_removal_never_releases_allowance_or_original_owner(self):
        m=self.model;cycle,capture,ticket=self.capture_ready()
        with cycle.held():capture.acquire(ticket)
        m.inventory.ignore_remove=True;m.m.tick(500)
        with self.assertRaises(NativeUIError):
            with cycle.held():capture.complete()
        self.assertFalse(m.storage.present);self.assertIsNotNone(m.world_store().read())
        self.assertTrue(cycle.capacity.state['receipts']);self.assertTrue(all(row['phase']=='reserved' for row in cycle.capacity.state['receipts']))
        self.assertEqual((),cycle.capacity._retirements)
        self.assertTrue(all((m.scope_root/('world-render-storage-'+row['command']['commandId']+'.json')).is_file()
            for row in cycle.capacity.state['receipts']))

    def test_actual_retirement_cas_lost_reply_keeps_pending_witness_and_never_relabels_it_admitted(self):
        import gc,os,weakref
        m=self.model;cycle,capture,ticket=self.capture_ready();capacity=cycle.capacity;write=capacity.file.write;lost=[]
        with cycle.held():capture.acquire(ticket)
        def unknown(value,previous):
            write(value,previous);receipts=unpack(value['payload'])[0]['receipts']
            if receipts and all(row['phase']=='retired' for row in receipts):
                lost.append(deepcopy(value));raise OSError('Actual completed retirement capacity CAS reply lost')
        capacity.file.write=unknown;m.m.tick(500)
        with self.assertRaises(NativeUIError):
            with cycle.held():capture.complete()
        self.assertEqual(1,len(lost));self.assertTrue(capacity.failed)
        self.assertTrue(all(row['phase']=='reserved' for row in capacity.state['receipts']))
        self.assertTrue(all(row['phase']=='retired' for row in unpack(capacity.store.read()['payload'])[0]['receipts']))
        self.assertEqual((),capacity._retirements);self.assertEqual(1,len(capacity._pending_retirement))
        witness=capacity._pending_retirement[0];self.assertIs(witness.capture,capture)
        self.assertIsNone(m.world_store().read());self.assertFalse(m.storage.present)
        pointer=weakref.ref(capture);fd=capture.file.parent.fd;physical=os.fstat(fd)
        m.captures.remove(capture);del capture;gc.collect();retained=pointer()
        self.assertIsNotNone(retained);self.assertEqual(physical,os.fstat(fd));m.captures.append(retained)
        with m.m.s.lock.held():witness.require()
        witness.references=[]
        with m.m.s.lock.held(),self.assertRaises(NativeUIError):witness.require()
        counts=(sum(p.getters for p in m.streams.values()),len(m.renderer.commands),len(m.model_commands),len(m.storage.commands))
        with self.assertRaises(NativeUIError):
            with cycle.held():cycle.sample_pair()
        self.assertEqual(counts,(sum(p.getters for p in m.streams.values()),len(m.renderer.commands),len(m.model_commands),len(m.storage.commands)))


class StreamCapacityRequiredTests(StreamCapacityCycleTests):
    def setUp(self):
        from self_tests.pico_emote_stream_capture_fixture import StreamCaptureModel
        self.model=StreamCaptureModel();self.addCleanup(self.finalize)
        print('Retained original POLICY1 rejection fixture roots:',*[str(p) for p in self.model.roots],flush=True)

    def test_policy1_without_native_file_capacity_cannot_construct_capture3_or_send_gpu(self):
        m=self.model
        with m.m.s.lock.held():cycle=m.create()
        with cycle.held():
            cycle.baseline();cycle.act(m.m.input.call('open'));cycle.act(m.m.input.call('play',{'name':'Waving'}))
            counts=(sum(p.getters for p in m.streams.values()),len(m.renderer.commands),len(m.model_commands))
            with self.assertRaises(NativeUIError):PicoEmoteStreamCapture(cycle,1,m.world,m.models)
            self.assertEqual(counts,(sum(p.getters for p in m.streams.values()),len(m.renderer.commands),len(m.model_commands)))
            cycle.act(m.m.input.call('cancel'));cycle.act(m.m.input.call('close'))
            from self_tests.pico_emote_stream_fixture import RUN
            m.m.s.journal.activate(RUN,'f'*32,'cleanup');cycle.cleanup(sleep=m.m.sleep)
        for producer in m.streams.values():producer.event_loop_turn()
        with cycle.held():self.assertTrue(cycle.drain()['sourceDrained'])


class StreamCapacityConstructionTests(StreamCapacityIntegrationFences):
    def test_actual_policy2_can_construct_capture3_on_same_original_budget_without_gpu_request(self):
        cycle,capture,ticket=self.capture_ready();m=self.model
        self.assertIs(cycle.capacity.archive,cycle.originals.archive);self.assertEqual('ready',capture.state['phase'])
        self.assertIsNone(capture.previous);self.assertEqual([],m.renderer.commands);self.assertEqual([],m.model_commands)
        with cycle.held():self.finish(cycle)
