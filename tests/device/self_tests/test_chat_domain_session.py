"""Actual-domain join validation on synthetic native protocol boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from self_tests import test_chat_journey_samples as samples_seams
from self_tests.test_native_chat_observation import Boundary,RUN


def session(value,*,instance='1'*32):
    value['chatVersion']=2
    value['source']['session']=dict(domainSessionVersion=1,instance=instance,revision=2,connected=True,
        domainSha256='4'*64,connectionBirth='2'*32,connectedEpochMs=19000,mixerActive=value['source']['mixerPresent'])


def ownership(value,*,opened='',retired=''):
    session(value);value['chatVersion']=3
    value['source'].update(openedCommandId=opened,retiredCommandId=retired)


class DomainSessionTests(unittest.TestCase):
    def test_v3_actual_open_and_retirement_ids_survive_passive_queries(self):
        boundary=Boundary()
        def original(value):
            opened=next((row['commandId'] for row in boundary.commands if row['operation']=='observe'),'')
            retired=next((row['commandId'] for row in boundary.commands if row['operation']=='retire'),'')
            ownership(value,opened=opened,retired=retired)
        boundary.mutate=original;reader=boundary.reader();initial=reader.perform(RUN,'inspect')
        self.assertEqual('',initial['source']['openedCommandId'])
        opened=reader.perform(RUN,'observe');first=opened['commandId']
        self.assertEqual(first,opened['source']['openedCommandId'])
        self.assertEqual(first,reader.perform(RUN,'inspect')['source']['openedCommandId'])
        retired=reader.perform(RUN,'retire');self.assertEqual(first,retired['source']['openedCommandId'])
        self.assertEqual(retired['commandId'],retired['source']['retiredCommandId'])
        final=reader.perform(RUN,'inspect');self.assertEqual(retired['source'],final['source'])

    def test_v3_never_accepts_missing_foreign_or_rewritten_original_mutation_ids(self):
        for fault in ('missing','empty-open','fake-retired','changed-open','version-regression'):
            boundary=Boundary()
            boundary.mutate=lambda value:ownership(value,opened=next((row['commandId'] for row in boundary.commands if row['operation']=='observe'),''))
            reader=boundary.reader();reader.perform(RUN,'observe');original=boundary.mutate
            def corrupt(value):
                original(value)
                if fault=='missing':value['source'].pop('openedCommandId')
                elif fault=='empty-open':value['source']['openedCommandId']=''
                elif fault=='fake-retired':value['source']['retiredCommandId']='f'*32
                elif fault=='changed-open':value['source']['openedCommandId']='f'*32
                else:
                    value['chatVersion']=2;value['source'].pop('openedCommandId');value['source'].pop('retiredCommandId')
            boundary.mutate=corrupt
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.perform(RUN,'inspect')

    def test_v2_native_source_preserves_domain_birth_revision_and_actual_mixer_activity(self):
        boundary=Boundary();boundary.present=True;boundary.opened=19000;boundary.mutate=session
        reader=boundary.reader();first=reader.perform(RUN,'inspect')
        self.assertTrue(first['source']['session']['mixerActive'])
        boundary.mixer=False;absent=reader.perform(RUN,'inspect')
        self.assertFalse(absent['source']['session']['mixerActive'])
        self.assertEqual(first['source']['session']['domainSha256'],absent['source']['session']['domainSha256'])
        boundary.mutate=lambda value:None
        with self.assertRaises(NativeUIError):reader.perform(RUN,'inspect')

    def test_mixed_legacy_peer_cannot_supply_missing_actual_domain_join(self):
        h=samples_seams.ChatSamplesTests();h.setUp();self.addCleanup(h.doCleanups);h.primary.mutate=session
        with self.assertRaises(NativeUIError):h.samples.read('b'*32,20000)

    def test_malformed_ambiguous_foreign_domain_fields_are_not_native_session_evidence(self):
        for fault in ('extra','bool-revision','null-birth','future-connect','inactive-absent','null-domain','wrong-schema'):
            boundary=Boundary();boundary.present=True;boundary.opened=19000
            def mutate(value):
                session(value);native=value['source']['session']
                if fault=='extra':native['requestedDomain']='hifi://requested.invalid'
                elif fault=='bool-revision':native['revision']=True
                elif fault=='null-birth':native['connectionBirth']=''
                elif fault=='future-connect':native['connectedEpochMs']=20001
                elif fault=='inactive-absent':value['source'].update(mixerPresent=False,mixerSha256='')
                elif fault=='null-domain':native['domainSha256']=''
                else:native['domainSessionVersion']=True
            boundary.mutate=mutate
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):boundary.reader().perform(RUN,'inspect')

    def sources(self):
        h=samples_seams.ChatSamplesTests();h.setUp();self.addCleanup(h.doCleanups)
        h.primary.mutate=session;original=h.peer.mutate
        def peer(value):original(value);session(value,instance='3'*32)
        h.peer.mutate=peer;return h

    def test_both_independent_clients_keep_original_domain_while_only_mixer_disappears(self):
        h=self.sources();h.samples.read('b'*32,20000);first=deepcopy(h.samples.frames[-1])
        h.primary.mixer=h.peer.mixer=False;observed=h.samples.read('c'*32,20000)
        self.assertFalse(observed['state']['mixerConnected'])
        for key in ('primary','peer'):
            old=first[key]['source']['session'];current=h.samples.frames[-1][key]['source']['session']
            self.assertTrue(current['connected'])
            self.assertEqual({k:v for k,v in old.items() if k!='mixerActive'},{k:v for k,v in current.items() if k!='mixerActive'})

    def test_foreign_domain_same_domain_reconnect_and_hidden_a_b_a_revision_fail_the_whole_join(self):
        for fault in ('foreign-peer-domain','reconnect','same-domain-a-b-a','disconnected','inactive-mixer'):
            h=self.sources();h.samples.read('b'*32,20000)
            original=h.peer.mutate
            def mutate(value):
                original(value);native=value['source']['session']
                if fault=='foreign-peer-domain':native['domainSha256']='5'*64;native['revision']+=1
                elif fault=='reconnect':native.update(revision=4,connectionBirth='6'*32,connectedEpochMs=20000)
                elif fault=='same-domain-a-b-a':native['revision']+=2
                elif fault=='disconnected':native.update(revision=3,connected=False,connectionBirth='',connectedEpochMs=0)
                else:native['mixerActive']=False
            h.peer.mutate=mutate
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):h.samples.read('c'*32,20000)
            self.assertEqual('reading',h.store.read()['phase'])


if __name__=='__main__':unittest.main()
