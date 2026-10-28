"""Passive originals/counterexamples: no daemon, device or authenticated RPC."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import asyncio
from copy import deepcopy
from pathlib import Path
import tempfile,unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import lifecycle_touch_resources as source,lifecycle_touch_transport as transport
from ios.adapters import lifecycle_touch_resource_owner as owners
from ios.adapters.touch_lease import TouchLeaseError,TouchLeasePending
from ios.self_tests.lifecycle_touch_resources_fixture import Fixture


class LifecycleTouchResourcesTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.root=Path(tempfile.mkdtemp(prefix='lifecycle-touch-resources-'));self.root.chmod(0o700)
        print('retained resource root',self.root,flush=True);self.f=Fixture(self.root)
    async def asyncTearDown(self):await self.f.close()
    async def test_actual_resources_and_worker_are_originals_but_close_returns_do_not_mint_retirement(self):
        f=self.f;await f.begin();first=f.owner.capture();self.assertTrue(first['worker']['workerRunning'])
        self.assertEqual({'rsd','receiver','drain','display','hid'},{row['kind'] for row in first['source']['resources']})
        self.assertTrue(all(fd.fileno()>=0 for fd in f.receiver.sockets))
        status=await f.owner.release_worker();self.assertTrue(status['contextExitReturned']);last=f.owner.capture()
        self.assertTrue(all(fd.fileno()==-1 for fd in f.receiver.sockets));self.assertTrue(last['source']['workerDone'])
        self.assertEqual([0xC2,0x02],f.hid.reports);self.assertEqual(f.display.starts,f.display.stops)
        self.assertTrue(any(row['edge']=='receiver-close-returned' for row in last['source']['events']))
        self.assertTrue(any(row['edge']=='source-finally-body-tail-observed' for row in last['source']['events']))
        self.assertTrue(any(row['alive'] for row in last['source']['resources'])) # Real wrappers remain retained.
        for key in source.UNAVAILABLE:self.assertFalse(last['source'][key])
        with self.assertRaises(transport.TouchTransportUnavailable):f.owner.ensure_retired()
        self.assertFalse(transport.metadata()['nativeTouchSupport'])
    async def test_unknown_original_down_keeps_same_task_and_fds_then_only_one_up_follows(self):
        f=self.f;f.hid.down_gate.clear()
        with self.assertRaises(TouchLeasePending):await f.begin(.6)
        worker=f.lease.worker;before=f.owner.capture();self.assertTrue(before['worker']['hostResponsibility'])
        with self.assertRaises(TouchLeasePending):await f.owner.release_worker()
        self.assertIs(worker,f.lease.worker);self.assertFalse(worker.cancelled());self.assertEqual([0xC2],f.hid.reports)
        self.assertTrue(all(fd.fileno()>=0 for fd in f.receiver.sockets))
        f.hid.down_gate.set();await worker;last=f.owner.capture();self.assertTrue(last['worker']['contextExitReturned'])
        self.assertEqual([0xC2,0x02],f.hid.reports);self.assertFalse(last['source']['sdkResourceRetirementAvailable'])
    async def test_failed_start_still_records_only_actual_stop_attempt_and_closes_local_receiver(self):
        f=self.f;f.display.fail_start=True
        with self.assertRaises(TouchLeaseError):await f.begin()
        await f.lease.worker;value=f.owner.capture();edges={row['edge'] for row in value['source']['events']}
        self.assertIn('stream-start-entered',edges);self.assertNotIn('stream-start-returned',edges)
        self.assertNotIn('hid-entered',edges);self.assertIn('stream-stop-returned',edges)
        self.assertEqual([],f.hid.reports);self.assertEqual(f.display.starts,f.display.stops)
        self.assertTrue(all(fd.fileno()==-1 for fd in f.receiver.sockets));self.assertFalse(value['source']['authenticatedTransportAvailable'])
    async def test_failed_stop_or_drain_cannot_erase_actual_receiver_close_or_create_clean_sdk_end(self):
        f=self.f;await f.begin();f.display.fail_stop=True
        with self.assertRaises(TouchLeasePending):await f.owner.release_worker()
        value=f.owner.capture();edges={row['edge'] for row in value['source']['events']}
        self.assertIn('stream-stop-entered',edges);self.assertNotIn('stream-stop-returned',edges);self.assertIn('receiver-close-returned',edges)
        self.assertTrue(all(fd.fileno()==-1 for fd in f.receiver.sockets));self.assertTrue(value['worker']['hostResponsibility'])
        self.assertFalse(value['source']['nativeStreamAbsenceAvailable'])
    async def test_metadata_failure_cannot_skip_existing_sdk_stop_drain_or_descriptor_close(self):
        f=self.f;await f.begin()
        with patch.object(source.TouchResourceObservation,'edge',side_effect=RuntimeError('Declared metadata failure')):
            await f.owner.release_worker()
        value=f.owner.capture();self.assertFalse(value['source']['complete'])
        self.assertEqual(f.display.starts,f.display.stops);self.assertTrue(all(fd.fileno()==-1 for fd in f.receiver.sockets))
        with self.assertRaises(transport.TouchTransportUnavailable):f.owner.ensure_retired()
    async def test_archived_admission_cannot_recreate_factory_worker_or_authenticated_transport(self):
        f=self.f;await f.begin();f.owner.capture();saved=f.restore();before=(list(f.hid.reports),list(f.display.starts))
        with self.assertRaises(NativeUIError):saved.make_lease(f.lease_store,f.rsd,'fd00::1',check=lambda:True)
        with self.assertRaises(TouchLeasePending):saved.capture()
        with self.assertRaises(TouchLeasePending):await saved.release_worker()
        with self.assertRaises(transport.TouchTransportUnavailable):saved.ensure_retired()
        self.assertEqual(before,(f.hid.reports,f.display.starts))
    async def test_lost_committed_resource_admission_does_not_open_or_replay_context(self):
        f=self.f;write=f.owner.store.write
        def lost(value,previous):write(value,previous);raise OSError('Declared lost owner commit')
        with patch.object(f.owner.store,'write',side_effect=lost),self.assertRaises(TouchLeaseError):await f.begin()
        await f.lease.worker;self.assertEqual([],f.display.starts);self.assertEqual([],f.hid.reports)
        restored=f.restore()
        with self.assertRaises(NativeUIError):restored.make_lease(f.lease_store,f.rsd,'fd00::1',check=lambda:True)
        self.assertEqual('factory-issued',restored.state['phase'])
    async def test_known_event_resource_identity_or_failure_rewrite_and_expected_endpoint_fields_are_refused(self):
        f=self.f;await f.begin();value=f.owner.capture()['source']
        for fault in ('event','identity','address','healthy','version'):
            before=deepcopy(value);after=deepcopy(value)
            if fault=='event':after['events'][0]['edge']='receiver-close-returned'
            elif fault=='identity':after['resources'][0]['id']='e'*32
            elif fault=='address':after['endpoint']='fd00::2'
            elif fault=='healthy':before['complete']=False;after['complete']=True
            else:after['iosLifecycleTouchResourcesVersion']=True
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.validate(after,before)
    async def test_source_capture_on_foreign_loop_and_replaced_actual_worker_cannot_borrow_admission(self):
        f=self.f;await f.begin();actual=f.lease.worker;f.lease.worker=None
        with self.assertRaises(NativeUIError):f.owner.capture()
        f.lease.worker=actual
        async def foreign():return f.owner._source.snapshot()
        with self.assertRaises(NativeUIError):await asyncio.to_thread(lambda:asyncio.run(foreign()))
        async def foreign_release():return await f.owner.release_worker()
        with self.assertRaises(NativeUIError):await asyncio.to_thread(lambda:asyncio.run(foreign_release()))
        await f.owner.release_worker();self.assertEqual([0xC2,0x02],f.hid.reports)

    async def test_invalid_lease_store_is_refused_before_constructor_guard_or_journal_write(self):
        f=self.f;owner=f.restore();self.assertIsNone(owner.previous);self.assertIsNone(owner._factory)
        before={path.name:path.read_bytes() for path in self.root.iterdir() if path.is_file()};checks=[]
        owner.check=lambda:checks.append(True) or True
        other=Path(tempfile.mkdtemp(prefix='lifecycle-touch-resource-other-scope-'));other.chmod(0o700)
        invalid=(owner.store,PrivateFeatureState(owner.store.path),
            PrivateFeatureState(self.root/'ios-lifecycle-other-owner.json'),
            PrivateFeatureState(self.root/('ios-lifecycle-touch-lease-'+'e'*32+'.json')),
            PrivateFeatureState(other/f.lease_store.path.name),None)
        for store in invalid:
            with self.subTest(path=None if store is None else str(store.path)), \
                    patch.object(owners,'TouchLease',side_effect=AssertionError('Invalid path constructed TouchLease')), \
                    patch.object(PrivateFeatureState,'write',side_effect=AssertionError('Invalid path wrote any WAL')), \
                    self.assertRaises(NativeUIError):owner.make_lease(store,f.rsd,'fd00::1',check=lambda:True)
        self.assertEqual([],checks);self.assertEqual(before,{path.name:path.read_bytes() for path in self.root.iterdir() if path.is_file()})
        self.assertEqual([],list(other.iterdir()));self.assertEqual([],f.display.starts);self.assertEqual([],f.hid.reports)
        self.assertIsNone(owner._factory);self.assertIsNone(owner._lease)

    async def test_pending_stop_retains_original_worker_and_descriptors_until_that_same_await_settles(self):
        f=self.f;await f.begin();f.display.stop_gate.clear();worker=f.lease.worker
        release=asyncio.create_task(f.owner.release_worker())
        try:
            await asyncio.wait_for(f.display.stop_started.wait(),1)
            pending=f.owner.capture();edges={row['edge'] for row in pending['source']['events']}
            self.assertIs(worker,f.lease.worker);self.assertFalse(worker.done());self.assertFalse(worker.cancelled())
            self.assertFalse(release.done());self.assertEqual([0xC2,0x02],f.hid.reports)
            self.assertEqual(1,len(f.display.starts));self.assertEqual(f.display.starts,f.display.stops)
            self.assertIn('stream-stop-entered',edges);self.assertNotIn('stream-stop-returned',edges)
            self.assertNotIn('receiver-close-entered',edges);self.assertFalse(pending['worker']['contextExitReturned'])
            self.assertTrue(pending['worker']['hostResponsibility']);self.assertTrue(pending['worker']['workerRunning'])
            self.assertTrue(all(fd.fileno()>=0 for fd in f.receiver.sockets))
        finally:
            f.display.stop_gate.set();await release
        closed=f.owner.capture();self.assertIs(worker,f.lease.worker);self.assertTrue(worker.done())
        self.assertTrue(closed['worker']['contextExitReturned']);self.assertEqual([0xC2,0x02],f.hid.reports)
        self.assertEqual(1,len(f.display.stops));self.assertTrue(all(fd.fileno()==-1 for fd in f.receiver.sockets))
        for key in source.UNAVAILABLE:self.assertFalse(closed['source'][key])

    async def test_actual_failed_drain_cannot_skip_receiver_close_or_create_retirement(self):
        f=self.f;await f.begin();drain=f.owner._source._refs['drain']()
        self.assertIsInstance(drain,asyncio.Task);self.assertFalse(drain.done())
        f.receiver.fail=True;f.receiver.pending.set()
        done,_pending=await asyncio.wait({drain},timeout=1);self.assertEqual({drain},done)
        with self.assertRaises(TouchLeasePending):await f.owner.release_worker()
        value=f.owner.capture();edges={row['edge'] for row in value['source']['events']}
        self.assertTrue(drain.done());self.assertFalse(drain.cancelled())
        self.assertIn('drain-cancel-entered',edges);self.assertNotIn('drain-await-settled',edges)
        self.assertIn('receiver-close-returned',edges);self.assertEqual([0xC2,0x02],f.hid.reports)
        self.assertIn('source-finally-body-tail-observed',edges) # Also reached during failed-drain unwind.
        self.assertEqual(f.display.starts,f.display.stops);self.assertTrue(all(fd.fileno()==-1 for fd in f.receiver.sockets))
        self.assertTrue(value['worker']['hostResponsibility']);self.assertFalse(value['worker']['contextExitReturned'])
        for key in source.UNAVAILABLE:self.assertFalse(value['source'][key])

    async def test_cleanup_keeps_exact_original_lease_worker_factory_binding_and_run_guards(self):
        f=self.f;await f.begin();original=(f.owner._lease,f.owner._factory,f.lease.worker,deepcopy(f.owner.binding),f.owner.run)
        journal=f.owner.store.path.read_bytes();retained=f.owner._retained
        for fault in ('retained','lease','factory','worker','binding','run'):
            with self.subTest(fault=fault):
                if fault=='retained':f.owner._retained=object()
                elif fault=='lease':f.owner._lease=lambda:None
                elif fault=='factory':f.owner._factory=lambda:None
                elif fault=='worker':f.lease.worker=None
                elif fault=='binding':f.owner.binding['sessionId']='foreign-session'
                else:f.owner.run='e'*32
                try:
                    with self.assertRaises(NativeUIError):await f.owner.release_worker()
                    self.assertEqual([0xC2],f.hid.reports);self.assertEqual([],f.display.stops)
                finally:
                    f.owner._retained=retained
                    f.owner._lease,f.owner._factory,f.lease.worker=original[:3]
                    f.owner.binding=deepcopy(original[3]);f.owner.run=original[4]
        await f.owner.release_worker();self.assertEqual([0xC2,0x02],f.hid.reports)
        self.assertEqual(journal,f.owner.store.path.read_bytes());self.assertEqual(f.display.starts,f.display.stops)
