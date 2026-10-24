"""Public browser facts come only from retained original native/DOM/VM joins."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import world_web_history as history
from ios.self_tests import test_ios_world_web_echoes as echo_fixture
from ios.self_tests.world_web_source_fixture import OriginalSources


def frames():
    ledger,document,work,ownership,directory,entity,source=echo_fixture.originals(include_source=True)
    server=source.browser.snapshot(ledger['runId'])
    return [dict(ledger=ledger,document=document,work=work,browser=server)],dict(ownership=ownership,directory=directory,entity=entity,
        origins=dict(primary='http://127.0.0.1:43210',foreign='http://127.0.0.1:43211'))


class WorldWebHistoryTests(unittest.TestCase):
    def test_public_state_uses_actual_current_editor_document_and_retained_independent_receipts(self):
        originals,kwargs=frames();result=history.derive(originals,**kwargs)
        self.assertEqual([1,1,1,1],[result['public'][key] for key in ('attemptedMessages','bridgeMessages','bridgeEchoes','documentLoads')])
        self.assertEqual('reference',result['public']['page']);self.assertTrue(result['public']['open'])

    def test_close_keeps_original_counters_while_actual_view_teardown_removes_page(self):
        originals,kwargs=frames();last=deepcopy(originals[-1]);ledger=last['ledger'];before=ledger['clockBefore']
        identity=deepcopy(ledger['events'][-1]['identity']);ordinal=ledger['eventSequence']+1
        ledger['events'].append(dict(sequence=ordinal,eventId='2'*32,kind='view-teardown',identity=identity,
            clock=dict(epochMs=before['epochMs'],monotonicMs=before['monotonicMs']),detail={}))
        ledger.update(eventSequence=ordinal,sequence=ledger['sequence']+1,commandId='ios-'+'2'*32)
        ledger['clockBefore']={k:v+2 for k,v in ledger['clockBefore'].items()};ledger['clockAfter']={k:v+2 for k,v in ledger['clockAfter'].items()}
        last['work'].update(sequence=last['work']['sequence']+1,requestId='ios-'+'3'*32)
        for key in ('clockBefore','clockAfter'):last['work'][key]={k:v+2 for k,v in last['work'][key].items()}
        last['document']=None;originals.append(last);result=history.derive(originals,**kwargs)['public']
        self.assertFalse(result['open']);self.assertEqual('none',result['page']);self.assertEqual(0,result['httpStatus'])
        self.assertEqual([1,1,1,1],[result[key] for key in ('attemptedMessages','bridgeMessages','bridgeEchoes','documentLoads')])

    def test_native_source_rollover_stale_dom_and_missing_actual_receipt_do_not_create_public_state(self):
        for fault in ('missingResponse','nativeIdentity','unknownDocument','oldDOM'):
            originals,kwargs=frames();last=originals[-1]
            if fault=='missingResponse':last['browser']['responses']=[];last['browser']['sequence']=0
            elif fault=='nativeIdentity':last['document']['source']['nativeView']['nonce']='00000000-0000-4000-8000-000000000009'
            elif fault=='unknownDocument':last['ledger']['events']=[row for row in last['ledger']['events'] if row['kind']!='document-verified']
            else:
                second=deepcopy(last);second['document']['source']['dom']['sequence']+=1;second['document']['source']['dom']['events'][0]['target']['id']='text';originals.append(second)
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):history.derive(originals,**kwargs)


if __name__=='__main__':unittest.main()
