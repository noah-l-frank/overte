"""Combined query reservation creates no acquired fact or input replay."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
from adapters.normal_ui import NativeUIError
from ios.self_tests.snapshot_combined_journey_domain import CombinedJourneyDomain
from ios.self_tests.snapshot_journey_files_domain import SnapshotJourneyFilesDomain,REAL_TIME


class PreparedQuietDomain(CombinedJourneyDomain):
    def __init__(self,case):
        self.prefix_filter_calls=[];super().__init__(case)
    def post(self,request,timeout):
        query=json.loads(request.data);result=super().post(request,timeout)
        # This simpler domain routes through post(), unlike the upload domain's
        # file_post hook. Filter the actual producer before original AFC reads.
        if query['action']=='snapshot-files' and query['operation']=='list':
            packet=deepcopy(self.ctx.files.value);assert packet['commandId']==query['commandId'] and packet['prefix']==query['prefix']
            original_names=[row['name'] for row in packet['files']]
            packet['files']=[row for row in packet['files'] if row['name'].startswith(query['prefix']+'-')]
            self.prefix_filter_calls.append(dict(commandId=query['commandId'],prefix=query['prefix'],before=original_names,after=[row['name'] for row in packet['files']]))
            self.ctx.files.value=packet
        return result


class SnapshotPreparedQuietTests(unittest.TestCase):
    def captured(self,*,combined=True):
        d=PreparedQuietDomain(self) if combined else SnapshotJourneyFilesDomain(self);d.complete_pending()
        with d.capture_owner() as capture:capture.capture('c'*32)
        return d
    def cleaning(self,capture):capture.state['phase']='cleaning';capture.save()
    def all_prepared(self,capture):
        result=[capture.prepare_observation('journey-quiet-1-'+mode,'manifest',mode=mode) for mode in ('animated','still-png')]
        return result+[capture.prepare_observation('journey-quiet-1-'+kind,kind) for kind in ('filework','owned')]
    def query_count(self,d,nonce):return sum(query.get('commandId')==nonce for query in d.commands)
    def test_four_reserves_have_no_fact_and_each_actual_dispatch_has_its_new_clock_floor(self):
        d=self.captured()
        with d.capture_owner() as capture:
            self.cleaning(capture);commands=deepcopy(d.commands);prepared=self.all_prepared(capture)
            self.assertEqual(commands,d.commands)
            for token in prepared:
                self.assertEqual('reserved',token.child.state['phase']);self.assertIsNone(token.child.state['started']);self.assertIsNone(token.child.state['proof'])
            # This is before any group original is born. Sleeping cannot age an
            # uncreated original; each send must sample its actual new floor.
            d.sleep(1.6);floor=REAL_TIME()*1000
            for token in prepared:
                nonce=token.child.state['query']['commandId'];child=capture.observe_prepared(token)
                self.assertGreaterEqual(child.state['started']['hostBeforeEpochMs'],int(floor));self.assertEqual(1,self.query_count(d,nonce))
                self.assertIsNotNone(child.state['proof'])
                if token.slot['kind']=='manifest':
                    frame=child.historical();calls=[row for row in d.prefix_filter_calls if row['commandId']==nonce];self.assertEqual(1,len(calls))
                    names=[row['name'] for row in frame['packet']['files']];self.assertEqual(calls[0]['after'],names)
                    self.assertTrue(all(name.startswith(frame['query']['prefix']+'-') for name in names))
                    if frame['query']['prefix'].endswith('-animated'):self.assertTrue(calls[0]['before']);self.assertEqual([],names)
    def test_partial_reserved_group_cold_reopens_same_nonces_before_any_request(self):
        d=self.captured()
        with d.capture_owner() as capture:
            self.cleaning(capture);commands=deepcopy(d.commands)
            first=[capture.prepare_observation('journey-quiet-1-'+mode,'manifest',mode=mode) for mode in ('animated','still-png')]
            nonces=[token.child.state['query']['commandId'] for token in first]
        with d.capture_owner() as resumed:
            prepared=self.all_prepared(resumed);self.assertEqual(nonces,[token.child.state['query']['commandId'] for token in prepared[:2]])
            self.assertEqual(commands,d.commands)
            for token in prepared:self.assertEqual('reserved',token.child.state['phase']);self.assertIsNone(token.child.state['started'])
            actual=resumed.observe_prepared(prepared[0]);self.assertEqual(nonces[0],actual.state['query']['commandId']);self.assertEqual(1,self.query_count(d,nonces[0]))
    def test_expired_issued_original_cannot_be_resent_or_given_another_clock(self):
        d=self.captured()
        with d.capture_owner() as capture:
            self.cleaning(capture);token=capture.prepare_observation('journey-quiet-1-animated','manifest',mode='animated')
            token.child.send(capture.epoch_ms());nonce=token.child.state['query']['commandId'];started=deepcopy(token.child.state['started'])
        d.sleep(1.6)
        with d.capture_owner() as resumed:
            token=resumed.prepare_observation('journey-quiet-1-animated','manifest',mode='animated')
            self.assertEqual(nonce,token.child.state['query']['commandId']);self.assertEqual('issued',token.child.state['phase'])
            with self.assertRaises(NativeUIError):resumed.observe_prepared(token)
            self.assertEqual(started,token.child.state['started']);self.assertEqual(1,self.query_count(d,nonce))
    def test_saved_original_stays_historical_after_cold_reopen_and_never_reissues(self):
        d=self.captured()
        with d.capture_owner() as capture:
            self.cleaning(capture);token=capture.prepare_observation('journey-quiet-1-animated','manifest',mode='animated');child=capture.observe_prepared(token)
            frame=deepcopy(child.historical());nonce=child.state['query']['commandId'];path=child.files().path(child.state['storage'])
            pin=(path.stat().st_ino,path.read_bytes())
        d.sleep(1.6)
        with d.capture_owner() as resumed:
            token=resumed.prepare_observation('journey-quiet-1-animated','manifest',mode='animated');child=resumed.observe_prepared(token)
            self.assertEqual(frame,child.historical());self.assertEqual(nonce,child.state['query']['commandId']);self.assertEqual(1,self.query_count(d,nonce))
        self.assertEqual(pin,(path.stat().st_ino,path.read_bytes()))
    def test_mutated_prepared_child_header_blocks_before_any_source_request(self):
        d=self.captured()
        with d.capture_owner() as capture:
            self.cleaning(capture);token=capture.prepare_observation('journey-quiet-1-animated','manifest',mode='animated');commands=deepcopy(d.commands)
            token.child.state['query']['commandId']='ios-'+'b'*32
            with self.assertRaises(NativeUIError):capture.observe_prepared(token)
            self.assertEqual(commands,d.commands)
    def test_separate_profile_cannot_prepare_a_combined_group(self):
        d=self.captured(combined=False)
        with d.capture_owner() as capture:
            self.cleaning(capture);commands=deepcopy(d.commands)
            with self.assertRaises(NativeUIError):capture.prepare_observation('journey-quiet-1-animated','manifest',mode='animated')
            self.assertEqual(commands,d.commands)


if __name__=='__main__':unittest.main()
