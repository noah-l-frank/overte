"""Real generated app/reference/DOM flow and independent native countercases."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import tablet_web_echoes as source,tablet_web_source as native,web_script_emissions as emissions
from ios.self_tests.tablet_web_echo_fixture import fixture


class TabletWebEchoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.value,cls.js=fixture();cls.foreign,_=fixture(bridge=False);cls.untrusted,_=fixture(trusted=False)

    def test_actual_trusted_dom_contact_native_caller_and_page_receive_complete_the_whole_chain(self):
        before=deepcopy(self.value);result=source.chain(**self.value)
        self.assertEqual(before,self.value);self.assertEqual((1,1,1),tuple(len(result[key]) for key in ('attempts','accepted','echoes')))
        touch=self.value['touches']['dispatches'][-1];click=result['attempts'][0]['click']
        self.assertLess(touch['finally']['epochMs'],click['capturedEpochMs'])
        self.assertEqual(self.js['reply'],result['echoes'][0]['received']['message'])
        self.assertEqual(self.value['emitter']['calls'][0],result['echoes'][0]['accepted']['call'])
        # Actual IOSBrowserTrace records entry BEFORE SinkScope, not equal.
        self.assertLess(result['echoes'][0]['accepted']['pageReply']['clock']['epochMs'],self.value['emitter']['sinks'][-1]['entered']['epochMs'])

    def test_foreign_trusted_attempt_has_no_manufactured_bridge_or_echo_and_synthetic_click_cannot_qualify(self):
        result=source.chain(**self.foreign);self.assertEqual((1,0,0),tuple(len(result[key]) for key in ('attempts','accepted','echoes')))
        with self.assertRaises(NativeUIError):source.chain(**self.untrusted)

    def test_native_delivery_without_actual_script_reply_is_not_a_consumed_vm_message(self):
        value=deepcopy(self.value);value['document']['source']['dom']['echoes']=[]
        ledger=value['ledger'];removed={row['sequence'] for row in ledger['events'] if row['kind'] in ('script-event-slot','page-reply')}
        ledger['events']=[row for row in ledger['events'] if row['sequence'] not in removed and row['detail'].get('entry') not in removed]
        value['emitter'].update(calls=[],objects=[],sinks=[],callSequence=0,sinkSequence=0)
        result=source.chain(**value)
        self.assertEqual((1,1,0,0),tuple(len(result[key]) for key in ('attempts','delivered','accepted','echoes')))

    def test_unfinished_or_unobserved_native_document_cannot_borrow_ready_dom(self):
        for kind in ('document-began','dom-observer-installed','main-response','native-finished','document-verified'):
            value=deepcopy(self.value);value['ledger']['events']=[row for row in value['ledger']['events'] if row['kind']!=kind]
            with self.subTest(kind=kind),self.assertRaises(NativeUIError):source.chain(**value)

    def test_same_payload_outgoing_ack_wrong_native_caller_or_different_page_cannot_create_receive(self):
        for fault in ('no-contact','outsider','pending-dispatch','wrong-view','wrong-nonce','subframe','missing-native-call','caller','nested','bytes','sink-clock','different-call','missing-page','duplicate-call','missing-echo','receive-before-source','unmatched-echo','active-contact'):
            value=deepcopy(self.value);ledger=value['ledger'];emitter=value['emitter'];touch=value['touches'];document=value['document'];body=document['source']['dom']
            if fault=='no-contact':touch.update(contacts=[],dispatches=[],dispatchSequence=0,targets=[])
            elif fault=='outsider':
                touch['targets']=[];touch['contacts'][0]['source']=None
                for dispatch in touch['dispatches']:dispatch['phases'][0]['source']=None
            elif fault=='pending-dispatch':touch['dispatches'][-1].update(returned=None,**{'finally':None});touch['pendingDispatches']=[2]
            elif fault=='wrong-view':touch['targets'][0]['identity']['creation']+=1
            elif fault=='wrong-nonce':next(row for row in ledger['events'] if row['kind']=='native-envelope')['detail']['documentNonce']='0'*36
            elif fault=='subframe':next(row for row in ledger['events'] if row['kind']=='native-envelope')['detail']['mainFrame']=False
            elif fault=='missing-native-call':emitter['sinks'][-1]['call']=None
            elif fault=='caller':emitter['calls'][0]['caller']=None
            elif fault=='nested':emitter['calls'][0]['caller']['emitStack']['frames'].append(deepcopy(emitter['calls'][0]['caller']['emitStack']['frames'][-1]))
            elif fault=='bytes':emitter['calls'][0]['caller']['emitStack']['frames'][0]['compiled']['sha256']='0'*64
            elif fault=='sink-clock':emitter['sinks'][-1]['entered']['epochMs']-=1000
            elif fault=='different-call':emitter['sinks'][0]['call']=None
            elif fault=='missing-page':
                page=next(row for row in ledger['events'] if row['kind']=='page-reply');ledger['events']=[row for row in ledger['events'] if row is not page and row['detail'].get('entry')!=page['sequence']]
            elif fault=='duplicate-call':
                duplicate=deepcopy(emitter['sinks'][-1]);duplicate.update(id='5'*32,sequence=3);emitter['sinks'].append(duplicate);emitter['sinkSequence']=3
            elif fault=='missing-echo':body['echoes']=[]
            elif fault=='receive-before-source':body['echoes'][0]['receivedEpochMs']=self.js['page']-1
            elif fault=='unmatched-echo':body['echoes'][0]['sequence']=2;body['echoes'][0]['message']=body['echoes'][0]['message'].replace('"sequence":1','"sequence":2')
            else:touch['contacts'][0].update(active=True,phase=0,ended=None);touch['dispatches']=touch['dispatches'][:1];touch['dispatchSequence']=1
            if fault=='missing-echo':
                # No actual DOM receipt means accepted-without-echo, even when
                # the real native outgoing API call and page slot completed.
                result=source.chain(**value);self.assertEqual((1,0),(len(result['accepted']),len(result['echoes'])))
            else:
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.chain(**value)

    def test_native_source_order_is_bracketed_not_equal_or_a_dom_synchronous_return_interval(self):
        value=deepcopy(self.value);source.chain(**value)
        # A same-shaped SinkScope outside its actual trace Signal bracket is
        # insufficient even with an independently valid caller and payload.
        sink=value['emitter']['sinks'][-1];page=next(row for row in value['ledger']['events'] if row['kind']=='page-reply')
        sink['entered']['epochMs']=page['clock']['epochMs']-1
        emissions.original(value['emitter']);native.original(value['ledger'])
        with self.assertRaises(NativeUIError):source.chain(**value)


if __name__=='__main__':unittest.main()
