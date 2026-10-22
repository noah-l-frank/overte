"""Native boundaries are models; HTTP resource identities/bytes are original."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import world_web_source as source,world_web_dom as dom,world_web_measurements as measure
from ios.self_tests.world_web_source_fixture import OriginalSources,RUN,URL


class WorldWebSourceTests(unittest.TestCase):
    def test_actual_response_header_dom_metadata_and_separately_read_server_receipt_join(self):
        for resource in ('reference.html','recovery.html'):
            f=OriginalSources(resource);document=f.document();ledger=f.ledger()
            value=measure.current_document(ledger,document,f.browser.snapshot(RUN),f.origins)
            self.assertEqual(1,value['documentLoads']);self.assertEqual(f.view['httpStatus'],value['response']['status'])
            self.assertIn(f.view['responseId'].encode(),f.body)
    def test_true_native_mouseup_and_same_actual_element_click_are_needed_for_attempt(self):
        f=OriginalSources();f.pointer();document=f.document();ledger=f.ledger()
        actual=measure.attempts(ledger,document);self.assertEqual(1,len(actual));self.assertFalse(actual[0]['click']['trusted'])
        for fault in ('missing-native','pending-callback','wrong-point','different-element','cooperative-trust'):
            native=deepcopy(ledger);current=deepcopy(document)
            if fault=='missing-native':native['events']=native['events'][:6];native['eventSequence']=6
            elif fault=='pending-callback':native['events']=native['events'][:-2];native['eventSequence']-=2
            elif fault=='wrong-point':native['events'][6]['detail']['x']=20
            elif fault=='different-element':current['source']['dom']['events'][0]['target']['birth']+=50
            else:current['source']['dom']['events'][1]['trusted']=True
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):measure.attempts(native,current)
    def test_native_owner_death_cannot_retire_a_held_real_completion(self):
        f=OriginalSources();entry=f.pointer(returned=False);f.event('owner-destroyed',{})
        self.assertEqual([entry['sequence']],source.pending(f.ledger()))
        f.event('callback-enter',dict(entry=entry['sequence'],result=dict(error=False,result=False)))
        self.assertEqual([entry['sequence']],source.pending(f.ledger()))
        f.event('callback-return',dict(entry=entry['sequence']));self.assertEqual([],source.pending(f.ledger()))
    def test_native_document_loads_are_unique_completed_documents_never_polls_or_duplicate_callbacks(self):
        f=OriginalSources();before=source.completed_documents(f.ledger());self.assertEqual(1,len(before))
        f.event('native-finished',{});f.event('document-verified',{})
        self.assertEqual(before,source.completed_documents(f.ledger()))
        for _ in range(4):self.assertEqual(1,len(source.completed_documents(f.ledger())))
    def test_missing_finish_header_status_source_pin_and_host_receipt_cannot_qualify_current_document(self):
        f=OriginalSources();document=f.document();ledger=f.ledger();browser=f.browser.snapshot(RUN)
        for fault in ('finish','header','status','pin','receipt','origin'):
            n,d,b,origins=deepcopy(ledger),deepcopy(document),deepcopy(browser),deepcopy(f.origins)
            if fault=='finish':n['events']=[r for r in n['events'] if r['kind']!='native-finished']
            elif fault=='header':d['source']['nativeView']['responseId']='f'*32
            elif fault=='status':d['source']['nativeView']['httpStatus']=404;d['source']['nativeView']['httpErrorStatus']=404
            elif fault=='pin':d['source']['nativeView']['observerSha256']='f'*64
            elif fault=='receipt':b['responses'][0]['responseId']='f'*32
            else:origins['primary']=origins['foreign']
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):measure.current_document(n,d,b,origins)
    def test_original_prefix_clock_pid_and_callback_identity_cannot_change(self):
        f=OriginalSources();old=f.ledger();fresh=f.ledger()
        for fault in ('prefix','clock','pid','incomplete','boolean','foreign-root'):
            value=deepcopy(fresh)
            if fault=='prefix':value['events'][0]['eventId']='f'*32
            elif fault=='clock':value['clockBefore']['monotonicMs']=old['clockAfter']['monotonicMs']-1
            elif fault=='pid':value['processId']=43
            elif fault=='incomplete':value['complete']=False
            elif fault=='boolean':value['eventSequence']=True
            else:value['events'][0]['identity']['sourceUrl']='http://foreign.invalid/elsewhere'
            query=dict(schemaVersion=1,action=source.ACTION,commandId=value['commandId'],runId=RUN,fixtureUrl=URL)
            if fault=='incomplete':source.validate(value,query,42,previous=old);continue
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):source.validate(value,query,42,previous=old)
    def test_closed_command_cannot_supply_status_text_script_reset_or_requested_origin(self):
        query=dict(schemaVersion=1,action=source.ACTION,commandId='ios-'+'f'*32,runId=RUN,fixtureUrl=URL)
        for field in ('status','text','script','reset','origin'):
            with self.subTest(field=field),self.assertRaises(NativeUIError):source.command(query|{field:True})
    def test_actual_read_transcript_is_copied_and_unknown_delivery_never_replays(self):
        f=OriginalSources();sent=[];carrier={}
        def send(query):sent.append(deepcopy(query));carrier['raw']=json.dumps(f.ledger(query))
        reader=source.IOSWorldWebSource(send,lambda:carrier['raw'],f.clock,lambda:True,42,monotonic=lambda:f.epoch/1000,sleep=lambda _n:None)
        actual=reader.read(RUN,URL);actual['events'][0]['identity']['sourceIdentity']='mutated outward copy'
        self.assertEqual('actual-native-owner',reader.last['events'][0]['identity']['sourceIdentity'])
        self.assertEqual(1,len(sent))
        def lost(query):sent.append(deepcopy(query));raise OSError('Lost original native request return')
        reader.send=lost
        with self.assertRaises(NativeUIError):reader.read(RUN,URL)
        self.assertEqual(2,len(sent))


if __name__=='__main__':unittest.main()
