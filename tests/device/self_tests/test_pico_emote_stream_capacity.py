"""Real original Parent/CAS/range capacity; no Policy2/Qt/native qualification."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc
import hashlib
import os
import unittest
import uuid
import weakref
from unittest.mock import patch

from adapters.chat_journey.archive_file import signature
from adapters.normal_ui import NativeUIError
from adapters.pico4 import emote_stream_capacity as capacity_module
from adapters.pico4.emote_stream_capacity import PicoEmoteStreamCapacity,descriptor
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.script_journey.history import MAX_RAW,MAX_FRAMES
from self_tests.pico_emote_capacity_fixture import CapacityModel,CapacityRenderer
from adapters.graphics_journey.originals import GraphicsOriginals
from adapters.script_journey.history import canonical,unpack

RETAINED=[]


class StreamCapacityTests(unittest.TestCase):
    def setUp(self):
        self.model=CapacityModel();self.addCleanup(self.finalize)
        print('Retained actual capacity component roots:',*[str(p) for p in self.model.roots],flush=True)

    def finalize(self):
        def inventory():return {str(path):dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),physical=signature(path.stat()))
            for root in self.model.roots for path in root.rglob('*') if path.is_file()}
        before=inventory();self.model.close();after=inventory();self.assertEqual(before,after)
        RETAINED.append(dict(roots=[str(p) for p in self.model.roots],files=after,originalModelCloseCalled=True))

    def active(self):
        m=self.model
        with m.m.s.lock.held():m.prepare();m.baseline()
        return m.capacity

    def request(self):return dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='feature-world-render-storage',
        requestId=uuid.uuid4().hex,operation='inspect')

    def test_fixed_native_file_slots_and_receipts_charge_the_one_actual_aggregate(self):
        m=self.model;capacity=self.active();original=tuple(m.parent.state[key] for key in ('started','epochMs','hostEpochMs'))
        with m.m.s.lock.held():
            before=capacity.extra_bill();request=self.request();capacity.receipt('actor',request);after=capacity.extra_bill()
            self.assertEqual(1,after['parts']-before['parts']);self.assertEqual(100000,after['storedBytes']-before['storedBytes'])
            self.assertEqual(2*(3*262144+1024)+3*65536,before['storedBytes'])
            self.assertEqual(descriptor(),capacity.limits());self.assertEqual(request,capacity.state['receipts'][0]['command'])
            self.assertEqual('reserved',capacity.state['receipts'][0]['phase'])
            with self.assertRaises(NativeUIError):capacity.receipt('actor',request)
        self.assertEqual(original,tuple(m.parent.state[key] for key in ('started','epochMs','hostEpochMs')))
        self.assertFalse(any(producer.controls or producer.getters for producer in m.streams.values()))

    def test_selection_after_original_source_acquisition_refuses_without_new_source(self):
        m=self.model
        with m.m.s.lock.held():
            m.prepare();m.baseline();calls=deepcopy(m.m.s.calls)
            with self.assertRaises(NativeUIError):PicoEmoteStreamCapacity(m.parent,m.roles)
        self.assertEqual(calls,m.m.s.calls)

    def test_callback_or_equal_bytes_graph_replacement_refuses_before_native_io(self):
        m=self.model;capacity=self.active()
        with m.m.s.lock.held():
            capacity.aggregate_bill=lambda:dict(parts=0,storedBytes=0,decodedBytes=0)
            with self.assertRaises(NativeUIError):capacity.receipt('actor',self.request())
        self.assertEqual([],m.storage.commands);self.assertEqual([],m.renderer.commands)

    def test_equal_bytes_state_graph_replacement_cannot_be_resealed(self):
        m=self.model;capacity=self.active()
        with m.m.s.lock.held():
            capacity.state=deepcopy(capacity.state)
            with self.assertRaises(NativeUIError):capacity.receipt('actor',self.request())
        self.assertEqual([],m.storage.commands);self.assertEqual([],m.renderer.commands)

    def test_actual_completed_capacity_cas_lost_reply_retains_original_owner_and_zero_send(self):
        m=self.model;capacity=self.active();write=capacity.file.write;lost=[]
        def unknown(value,previous):write(value,previous);lost.append(value);raise OSError('Actual capacity CAS reply lost')
        capacity.file.write=unknown
        with m.m.s.lock.held(),self.assertRaises(OSError):capacity.receipt('actor',self.request())
        self.assertEqual(1,len(lost));self.assertEqual(lost[0],capacity.store.read());self.assertTrue(capacity.failed)
        self.assertIn(capacity,capacity_module.OWNED);self.assertIn(capacity,capacity_module.UNRESOLVED)
        node=os.fstat(capacity.file.parent.fd)
        gc.collect();self.assertEqual(node,os.fstat(capacity.file.parent.fd));self.assertEqual([],m.storage.commands)
        with m.m.s.lock.held(),self.assertRaises(NativeUIError):capacity.receipt('actor',self.request())

    def test_global_bytes_refusal_preserves_an_already_issued_exact_raw_return(self):
        m=self.model;capacity=self.active();wire=os.urandom(131072)+b'\0'
        with m.m.s.lock.held():
            token=m.archive.reserve('actor',dict(actualIssuedRead='capacity-before-loss'),len(wire))
            current=m.bill();raw=m.archive.bill();pending=sum(row['limit']+row['sideBytes'] for row in m.archive.state['pending'])
            remaining=MAX_RAW-current['decodedBytes']-raw['decodedBytes']-pending-3*65536
            m.external['decodedBytes']=remaining-99999
            with self.assertRaises(NativeUIError):capacity.receipt('actor',self.request())
            self.assertTrue(capacity.admission_stopped);self.assertEqual([],capacity.state['receipts'])
            reference=m.archive.retain(token,wire);self.assertEqual(wire,m.archive.literal(reference))
        self.assertEqual([],m.storage.commands);self.assertFalse(m.archive.failed)

    def test_global_part_refusal_sends_zero_and_does_not_reset_an_allowance(self):
        m=self.model;capacity=self.active()
        with m.m.s.lock.held():
            m.external['parts']=MAX_FRAMES-m.bill()['parts']-m.archive.bill()['parts']
            with self.assertRaises(NativeUIError):capacity.receipt('actor',self.request())
            self.assertEqual([],capacity.state['receipts']);self.assertTrue(capacity.admission_stopped)
            with self.assertRaises(NativeUIError):capacity.receipt('actor',self.request())
        self.assertEqual([],m.storage.commands)

    def test_original_parent_expiry_blocks_capacity_without_starting_another_budget(self):
        m=self.model;capacity=self.active();clocks=deepcopy(capacity.state['originalClocks']);m.m.tick(120000)
        with m.m.s.lock.held(),self.assertRaises(NativeUIError):capacity.receipt('actor',self.request())
        self.assertEqual(clocks,capacity.state['originalClocks']);self.assertEqual([],m.storage.commands)

    def test_partial_constructor_actual_fd_is_strongly_retained_before_unwind(self):
        m=self.model;original=LifecycleProcessFile.__init__;seen=[]
        def lose(owner,store):
            original(owner,store)
            if '.child-stream-capacity.json' in str(store.path):seen.append(owner.parent.fd);raise OSError('Actual admitted directory ctor return lost')
        with m.m.s.lock.held(),patch.object(LifecycleProcessFile,'__init__',lose),self.assertRaises(OSError):m.prepare()
        retained=capacity_module.OWNED[-1];reference=weakref.ref(retained);node=os.fstat(seen[0])
        self.assertIn(retained,capacity_module.UNRESOLVED);del retained;gc.collect()
        self.assertIsNotNone(reference());self.assertEqual(node,os.fstat(seen[0]));m.capacity=reference()
        self.assertEqual([],m.storage.commands);self.assertFalse(any(p.controls or p.getters for p in m.streams.values()))


class StreamPNGCapacityTests(StreamCapacityTests):
    # Explicit method selectors below exclude inherited capacity tests.
    def emitted(self,*,large=False):
        m=self.model;capacity=self.active()
        if large:m.renderer=CapacityRenderer(m.streams['actor'].epoch,m.m.tick,m.scope_root,2048,2048)
        request=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='feature-world-render-observe')
        m.renderer.intents.append(request);m.renderer.send(request)
        return capacity,m.renderer.sample

    def saved(self):
        m=self.model;capacity,packet=self.emitted()
        with m.m.s.lock.held():capacity.png('actor',packet)
        binding=dict(capacity.roles)['actor']['binding'];key=hashlib.sha256(canonical(binding)).hexdigest()[:16]
        root=m.parent.source.artifact_root/('emote-remote-images-'+m.parent.source.run+'-'+key+'-1');root.mkdir(mode=0o700)
        images=GraphicsOriginals(root,binding,m.parent.source.run,'actor',0,capacity.guard,lambda value:True,monotonic=lambda:m.m.s.clock)
        with m.m.s.lock.held():value=images.write(uuid.uuid4().hex,packet,m.renderer.raw)
        return capacity,packet,images,value

    def test_actual_png_larger_than_compound_limit_refuses_before_first_storage_chunk(self):
        m=self.model;capacity,packet=self.emitted(large=True)
        self.assertGreater(len(m.renderer.raw),MAX_RAW);self.assertLess(len(m.renderer.raw),33554432)
        self.assertEqual(len(m.renderer.raw),packet['source']['image']['bytes'])
        with m.m.s.lock.held(),self.assertRaises(NativeUIError):capacity.png('actor',packet)
        self.assertEqual([],capacity.state['pngs']);self.assertEqual([],m.storage.commands)
        self.assertEqual(1,len(m.renderer.commands));self.assertTrue(capacity.admission_stopped)

    def test_future_png_copy_transfers_only_to_actual_original_file_with_same_full_stamp(self):
        m=self.model;capacity,packet,images,value=self.saved()
        with m.m.s.lock.held():
            before=capacity.extra_bill();capacity.png_accounted('actor',images,value);after=capacity.extra_bill()
            self.assertEqual(value['bytes'],before['storedBytes']-after['storedBytes'])
            row=capacity.state['pngs'][0];self.assertEqual('accounted',row['phase'])
            self.assertEqual(signature((images.root/value['name']).stat()),row['fileProof']['physical'])
            self.assertEqual(hashlib.sha256(m.renderer.raw).hexdigest(),row['fileProof']['sha256']);capacity.require()
        self.assertEqual([],m.storage.commands)

    def test_actual_equal_bytes_foreign_png_inode_refuses_without_freeing_more_allowance(self):
        m=self.model;capacity,packet,images,value=self.saved()
        with m.m.s.lock.held():capacity.png_accounted('actor',images,value)
        path=images.root/value['name'];original=path.with_name('retained-original-png.png');path.rename(original)
        path.write_bytes(m.renderer.raw);path.chmod(0o600)
        with m.m.s.lock.held(),self.assertRaises(NativeUIError):capacity.ready()
        self.assertEqual([],m.storage.commands);self.assertEqual('accounted',capacity.state['pngs'][0]['phase'])
        self.assertNotEqual(value['file']['inode'],path.stat().st_ino)

    def test_actual_png_capacity_cas_lost_reply_keeps_constructed_file_owner_strong(self):
        m=self.model;capacity,packet,images,value=self.saved();write=capacity.file.write
        def lost(candidate,previous):
            write(candidate,previous)
            if unpack(candidate['payload'])[0]['pngs'][0]['phase']=='accounted':raise OSError('Actual PNG conservation CAS lost')
        capacity.file.write=lost
        with m.m.s.lock.held(),self.assertRaises(OSError):capacity.png_accounted('actor',images,value)
        self.assertTrue(capacity.failed);self.assertEqual('reserved',capacity.state['pngs'][0]['phase'])
        self.assertEqual(1,len(capacity._pending_png));owner=capacity._pending_png[0];node=os.fstat(owner.file.fd)
        gc.collect();owner.file.require(owner.file.fd);self.assertEqual(node,os.fstat(owner.file.fd))
        self.assertEqual('accounted',unpack(capacity.store.read()['payload'])[0]['pngs'][0]['phase'])
        self.assertEqual([],m.storage.commands)

    def test_generic_commit_cannot_clear_or_reduce_actual_native_receipt_reservation(self):
        m=self.model;capacity=self.active()
        with m.m.s.lock.held():
            capacity.receipt('actor',self.request());original=deepcopy(capacity.state)
            with self.assertRaises(NativeUIError):capacity._commit('receipt',receipts=[])
            self.assertEqual(original,capacity.state);self.assertEqual([],m.storage.commands)


if __name__=='__main__':unittest.main()
