"""Real private journals and callback lifetimes; no native or device execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from unittest.mock import patch
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.native_clock_join import NativeClockAcquisition,digest
from adapters.script_feature.history import pack
from ios.adapters.emote_pointers import receipt
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_pointers import IOSEmotePointers
from ios.adapters.emote_retirement_scope import refresh
from ios.self_tests import test_ios_emote_marker_scope as fixture
from ios.self_tests.test_ios_emote_marker_owner import Domain
from ios.self_tests.emote_pointer_fixture import PointerDomain
from ios.self_tests.test_ios_emote_sources import BINDING,RUN


class PointerOwnerTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.MarkerScopeTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        self.scope=self.fixture.owner();self.domain=Domain(self.scope);self.qt=PointerDomain(self,self.scope,self.domain)
        self.owner=self.qt.owner();self.owner.capture()
    def quiet(self):
        self.scope.cleanup();refresh(self.scope,clock=lambda:self.domain.time,sleep=self.domain.sleep,pointers=self.owner)
    def test_actual_startup_and_unchanged_contact_history_cover_all_resource_quiet(self):
        self.quiet();actual=self.owner.closed(self.scope);requests=len(self.qt.boundary.requests)
        archived=IOSEmotePointers.archive(self.owner.store.read(),store=self.owner.store,root=self.scope.root,binding=BINDING,run=RUN,role='primary',lock=self.scope.lock)
        self.assertEqual(actual,archived.closed(self.scope));self.assertEqual(requests,len(self.qt.boundary.requests))
        self.assertGreaterEqual(actual['last']['packet']['clockBefore']['monotonicMs']-actual['first']['packet']['clockAfter']['monotonicMs'],3000)
    def test_release_ack_cannot_replace_actual_contact_end_and_returned_callback(self):
        self.qt.boundary.touch('touch-begin');self.scope.cleanup()
        with self.assertRaises(NativeUIError):refresh(self.scope,clock=lambda:self.domain.time,sleep=self.domain.sleep,pointers=self.owner)
        self.qt.boundary.touch('touch-end');refresh(self.scope,clock=lambda:self.domain.time,sleep=self.domain.sleep,pointers=self.owner)
        self.assertTrue(self.owner.closed(self.scope));self.assertEqual(set(),self.qt.boundary.product_contacts)
    def test_new_complete_press_end_inside_quiet_cannot_borrow_previous_null_samples(self):
        self.quiet();capture=self.scope.capture;count=[0]
        def changed(label):
            frame=capture(label);count[0]+=1
            if count[0]==2:self.qt.boundary.touch('touch-begin');self.qt.boundary.touch('touch-end')
            return frame
        with patch.object(self.scope,'capture',side_effect=changed):refresh(self.scope,clock=lambda:self.domain.time,sleep=self.domain.sleep,pointers=self.owner)
        result=self.owner.closed(self.scope)
        self.assertGreater(result['first']['packet']['source']['eventSequence'],0)
        self.assertEqual(result['first']['packet']['source']['events'],result['last']['packet']['source']['events'])
    def test_lost_passive_query_is_never_resent_and_raw_return_floors_are_preserved(self):
        owner=self.qt.owner();send=owner.pointer.send
        def lost(query):send(query);raise OSError('Lost actual Qt source return')
        with patch.object(owner.pointer,'send',side_effect=lost),self.assertRaises(NativeUIError):owner.capture()
        before=deepcopy(self.qt.boundary.requests);rebuilt=self.qt.owner();self.assertFalse(rebuilt.resolve());self.assertTrue(rebuilt.abandon())
        self.assertEqual(before,self.qt.boundary.requests);ref=rebuilt.capture()
        self.assertNotEqual(before[-1]['commandId'],rebuilt.original(ref)['query']['commandId'])
        self.assertEqual(1,len(rebuilt.state['abandoned']))
    def test_lost_local_record_return_adopts_exact_original_without_another_query(self):
        owner=self.qt.owner();write=PrivateFeatureState.write;lost=[]
        def writing(store,value,previous):
            write(store,value,previous)
            if store.path==owner.file(2).path and not lost:lost.append(True);raise OSError('Lost local Qt record return')
        with patch.object(PrivateFeatureState,'write',writing),self.assertRaises(OSError):owner.capture()
        requests=len(self.qt.boundary.requests);rebuilt=self.qt.owner();self.assertTrue(rebuilt.resolve())
        self.assertEqual(requests,len(self.qt.boundary.requests));self.assertEqual(2,len(rebuilt.state['records']))
    def test_historical_abandoned_raw_birth_cannot_be_erased_by_internally_valid_later_records(self):
        owner=self.qt.owner();send=owner.pointer.send
        def reset(query):
            send(query);self.qt.boundary.packet['source']['instance']='f'*32
        with patch.object(owner.pointer,'send',side_effect=reset),self.assertRaises(NativeUIError):owner.capture()
        owner=self.qt.owner();self.assertTrue(owner.abandon());partial=owner.abandoned(owner.state['abandoned'][0])
        self.assertEqual(1,partial['priorRecords']);self.assertIn('ffffffff',partial['raw'])
        # An independent historical fixture produces the old implementation's
        # internally continuous completed prefix, without its abandoned floor.
        # Actual packets/files/hashes remain original and are not retimed.
        window=NativeClockAcquisition(self.scope.native,epoch_ms=self.scope.epoch_ms,monotonic=lambda:self.domain.time)
        window.begin(self.scope.epoch_ms());pointer=self.qt.owner().pointer;packet=pointer.read(RUN)
        join=window.finish(dict(pointer=packet,pointerClock=dict(capturedEpochMs=packet['clockAfter']['epochMs'])),[('pointerClock','capturedEpochMs')])
        candidate=dict(iosEmotePointerReceiptVersion=1,runId=RUN,role='primary',binding=BINDING,
            query=deepcopy(self.qt.boundary.requests[-1]),packet=packet,clockJoin=join)
        receipt(candidate,BINDING,RUN,'primary',owner.original(owner.state['records'][0]))
        value=dict(iosEmotePointerOriginalVersion=1,payload=pack([candidate]));owner.file(2).write(value,None)
        owner.state['records'].append(dict(index=2,sha256=digest(value)));value=owner.envelope(owner.state)
        with self.assertRaises(NativeUIError):IOSEmotePointers.archive(value,store=owner.store,root=self.scope.root,binding=BINDING,run=RUN,role='primary',lock=self.scope.lock)
        with self.assertRaises(NativeUIError):owner.closed(self.scope)

    def test_unmatched_stale_raw_file_remains_bytes_without_becoming_this_querys_source(self):
        import json
        owner=self.qt.owner();stale=owner.original(owner.state['records'][0])['packet'];stale['source']['instance']='f'*32
        with patch.object(owner.pointer,'original',return_value=json.dumps(stale)),self.assertRaises(NativeUIError):owner.capture()
        rebuilt=self.qt.owner();rebuilt.abandon();ref=rebuilt.capture()
        self.assertEqual('b'*32,rebuilt.original(ref)['packet']['source']['instance'])
        self.assertIn('ffffffff',rebuilt.abandoned(rebuilt.state['abandoned'][0])['raw'])

    def test_pending_actual_callback_remains_owned_even_after_touch_end(self):
        self.scope.cleanup();self.qt.boundary.touch('touch-begin')
        def pending():
            with self.assertRaises(NativeUIError):refresh(self.scope,clock=lambda:self.domain.time,sleep=self.domain.sleep,pointers=self.owner)
            return False
        self.assertFalse(self.qt.boundary.touch('touch-end',handler=pending))
        refresh(self.scope,clock=lambda:self.domain.time,sleep=self.domain.sleep,pointers=self.owner)
        self.assertTrue(self.owner.closed(self.scope))

    def test_unknown_startup_fails_closed_without_process_history_reset(self):
        self.qt.boundary.started=False;self.scope.cleanup()
        with self.assertRaises(NativeUIError):refresh(self.scope,clock=lambda:self.domain.time,sleep=self.domain.sleep,pointers=self.owner)

    def test_actual_global_qt_buttons_and_worldtap_are_independent_drainage_duties(self):
        self.scope.cleanup()
        for field in ('qt_buttons','world_tap'):
            setattr(self.qt.boundary,field,1 if field=='qt_buttons' else True)
            with self.subTest(field=field),self.assertRaises(NativeUIError):refresh(self.scope,clock=lambda:self.domain.time,sleep=self.domain.sleep,pointers=self.owner)
            setattr(self.qt.boundary,field,0 if field=='qt_buttons' else False)
        refresh(self.scope,clock=lambda:self.domain.time,sleep=self.domain.sleep,pointers=self.owner)
        self.assertTrue(self.owner.closed(self.scope))


if __name__=='__main__':unittest.main()
