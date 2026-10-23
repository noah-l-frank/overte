"""Actual private-file recovery of issued passive reads; no native execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import os
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.self_tests import test_ios_tablet_web_packets as leaf_tests
from ios.self_tests import test_ios_tablet_web_source_owner as source_tests


class TabletReadRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.fixture=leaf_tests.TabletWebPacketsTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
    def lost(self,owner,reader):
        send=reader.send
        def lost(query):send(query);raise OSError('Actual send return lost after native receipt')
        reader.send=lost
        with self.assertRaises(NativeUIError):owner.capture(reader)
        return reader
    def test_read_only_old_nonce_has_separate_clock_span_and_never_becomes_fresh_or_reissues(self):
        f=self.fixture;owner=f.owner();reader=self.lost(owner,f.reader());failed=deepcopy(owner.state['pending']);count=len(f.sends)
        rebuilt=f.owner();actual=rebuilt.reconcile(reader)
        self.assertEqual(count,len(f.sends));self.assertEqual('failed',rebuilt.state['pending']['status'])
        self.assertEqual(failed['after'],rebuilt.state['pending']['after']);self.assertIsNone(rebuilt.state['pending']['resultSha256'])
        self.assertFalse(rebuilt.state['pending']['sendReturned']);self.assertEqual(failed['query']['commandId'],actual['commandId'])
        self.assertEqual('returned',rebuilt.state['pending']['readbacks'][0]['status'])
        ref=rebuilt.archive_pending();old=rebuilt.originals.read(rebuilt.originals.expand(ref));self.assertEqual('failed',old['status'])
        self.assertEqual([actual],f.owner().history())
        fresh=rebuilt.capture(f.reader());self.assertNotEqual(actual['commandId'],fresh['commandId']);self.assertEqual(count+1,len(f.sends))
    def test_literal_v1_unanswered_record_is_readable_and_only_readback_adds_v2(self):
        f=self.fixture;owner=f.owner();reader=self.lost(owner,f.reader());value=deepcopy(owner.state)
        value['tabletWebPacketsVersion']=1;value['pending']['tabletWebSourcePacketVersion']=1;value['pending'].pop('readbacks')
        owner.store.write(value,owner.saved);rebuilt=f.owner();self.assertEqual(1,rebuilt.state['tabletWebPacketsVersion'])
        rebuilt.reconcile(reader);self.assertEqual(2,rebuilt.state['pending']['tabletWebSourcePacketVersion'])
        self.assertEqual(value['pending']['after'],rebuilt.state['pending']['after']);self.assertEqual(1,len(f.sends))
    def test_old_nonce_wrong_source_birth_is_preserved_rejected_and_cannot_erase_prior_floor(self):
        f=self.fixture;owner=f.owner();owner.capture(f.reader());reader=self.lost(owner,f.reader());f.current['instance']='0'*32
        with self.assertRaises(NativeUIError):owner.reconcile(reader)
        rebuilt=f.owner();self.assertTrue(rebuilt.blocked);raw=rebuilt.state['pending']['raws'][0]
        self.assertEqual('rejected',raw['outcome']);self.assertEqual('0'*32,json.loads(rebuilt.segments.read(raw['segments']))['instance'])
        with self.assertRaises(NativeUIError):rebuilt.reconcile(reader)
        self.assertEqual(2,len(f.sends))
    def test_foreign_nonce_never_becomes_owned_raw_and_unsafe_matching_bytes_have_digest_only(self):
        f=self.fixture;owner=f.owner();reader=self.lost(owner,f.reader());original=deepcopy(f.current)
        f.current['commandId']='ios-'+'0'*32
        with self.assertRaises(NativeUIError):owner.reconcile(reader)
        self.assertEqual([],owner.state['pending']['raws']);self.assertEqual([],list(f.root.glob('*-frame-*')))
        f.current=original;f.current['unexpectedPrivateText']='must not enter host artifacts'
        with self.assertRaises(NativeUIError):owner.reconcile(reader)
        self.assertEqual([],owner.state['pending']['raws']);self.assertEqual([],list(f.root.glob('*-frame-*')))
        self.assertEqual({'bytes','sha256'},set(owner.state['pending']['unsafe'][0]));self.assertEqual(1,len(f.sends))
    def test_lost_complete_raw_flush_recovers_same_inode_without_second_read_or_query(self):
        f=self.fixture;owner=f.owner();reader=self.lost(owner,f.reader());fsync=os.fsync;hit=[False]
        def lost(fd):
            name=os.readlink('/proc/self/fd/'+str(fd))
            if not hit[0] and 'tabletweb-sources-' in name and '-frame-' in name:
                hit[0]=True;raise OSError('Actual readback raw flush return lost')
            return fsync(fd)
        with patch('os.fsync',side_effect=lost),self.assertRaises(OSError):owner.reconcile(reader)
        rebuilt=f.owner();raw=rebuilt.state['pending']['raws'][0];parts=raw['segments']['chunks']
        # Real source segments keep full actual child descriptors.
        paths=[rebuilt.segments.store.path(part) for part in parts]
        originals=[(path.stat(),path.read_bytes()) for path in paths]
        reader.original=lambda:(_ for _ in ()).throw(AssertionError('Repeated AFC read'))
        rebuilt.reconcile(reader)
        self.assertEqual(originals,[(path.stat(),path.read_bytes()) for path in paths]);self.assertEqual(1,len(f.sends))
        self.assertEqual('failed',rebuilt.state['pending']['readbacks'][0]['status'])


class TabletParentReadRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.fixture=source_tests.TabletWebSourceOwnerTests();self.fixture.setUpClass();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
    def interrupted(self):
        f=self.fixture;source=f.prepare();readers={name:f.boundary.reader(name) for name in source_tests.ORDER};reader=readers['sources'];send=reader.send
        def lost(query):send(query);raise OSError('Actual source query return lost')
        reader.send=lost
        with self.assertRaises(NativeUIError):source.capture(readers,f.boundary.native(),f.boundary.phase,lambda:deepcopy(f.frame['browser']))
        return source,reader
    def test_parent_failed_original_is_frozen_before_old_afc_read_and_cannot_be_a_fact(self):
        f=self.fixture;source,reader=self.interrupted();failed=deepcopy(source.state['pending']);counts=(len(f.boundary.calls),f.boundary.native_count)
        actual=reader.original
        def observed():
            ref=source.state['intent'];self.assertIsNotNone(ref);self.assertEqual(failed,source.originals.read(ref));return actual()
        reader.original=observed;ref=source.reconcile_unanswered(reader)
        self.assertEqual(counts,(len(f.boundary.calls),f.boundary.native_count));self.assertEqual(failed,source.originals.read(source.originals.expand(ref)))
        rebuilt=f.owner();self.assertFalse(rebuilt.blocked);self.assertEqual([],rebuilt.history());self.assertEqual(1,len(rebuilt.state['reconciled']))
        with self.assertRaises(NativeUIError):rebuilt.facts(source_tests.ORIGINS)
        historical=f.owner(historical=True)
        with self.assertRaises(NativeUIError):historical.facts_at(ref,source_tests.ORIGINS)
    def test_new_acquisition_after_recovery_is_separate_and_replays_correct_original_frame_index(self):
        f=self.fixture;source,reader=self.interrupted();failed=deepcopy(source.state['pending']);old=source.reconcile_unanswered(reader)
        # A separate actual native-clock read and later boundary time keep the
        # host model's alternating begin/end producer aligned; it is not a
        # successful acquisition or a replacement for the failed frame.
        f.boundary.native().read(0);f.boundary.epoch+=1000;f.boundary.mono+=1.
        f.boundary.frame['document']['source']['dom']['capturedEpochMs']=f.boundary.epoch
        readers={name:f.boundary.reader(name) for name in source_tests.ORDER}
        native=f.boundary.native();start=f.boundary.native_count
        native.clock_ms=lambda:f.boundary.epoch+(100 if f.boundary.native_count>=start+2 else -100)
        try:parts,row=source.capture(readers,native,f.boundary.phase,lambda:deepcopy(f.frame['browser']))
        except NativeUIError as error:
            name=source.state['pending']['components'][-1]['component'];child=source.children[name]
            raise AssertionError('Modeled fresh component '+name+' failed; raw outcomes '+str([item['outcome'] for item in child.state['pending']['raws']])) from error
        self.assertEqual(2,row['index']);self.assertEqual('returned',row['status'])
        self.assertEqual(failed,source.originals.read(source.originals.expand(old)))
        historical=f.owner(historical=True);facts,actual,frame=historical.facts_at(source.state['records'][-1],source_tests.ORIGINS)
        self.assertEqual(2,actual['index']);self.assertEqual(parts,frame);self.assertEqual(1,len(historical.history()))
        self.assertEqual(1,facts['public']['bridgeEchoes'])

    def test_missing_actual_old_receipt_cannot_be_blindly_abandoned_or_resend(self):
        f=self.fixture;source,reader=self.interrupted();reader.original=lambda:'';counts=(len(f.boundary.calls),f.boundary.native_count)
        with self.assertRaises(NativeUIError):source.reconcile_unanswered(reader)
        self.assertTrue(f.owner().blocked);self.assertEqual(counts,(len(f.boundary.calls),f.boundary.native_count))
        self.assertEqual([],source.state['records']);self.assertIsNotNone(source.state['intent'])


if __name__=='__main__':unittest.main()
