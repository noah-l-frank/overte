"""Actual staged echo source joins modeled native/DOM delivery boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import world_web_echoes as echoes
from ios.self_tests.world_web_source_fixture import OriginalSources,RUN,URL,TICKET
from ios.self_tests import test_ios_world_web_work as vm


def originals(*,include_source=False):
    source=OriginalSources();source.identity['sourceIdentity']='web-entity:'+vm.ENTITY;source.view['sourceIdentity']=source.identity['sourceIdentity']
    # Actual document-origin metadata belongs to this native modeled owner at
    # construction. No previously admitted original is rewritten here.
    for event in source.events:event['identity']['sourceIdentity']=source.identity['sourceIdentity']
    source.pointer();executed=vm.execute()['events'][:-3];workers=vm.packet(executed)
    message=executed[1]['payload']['message'];response=executed[2]['payload']['message']
    envelope=source.event('native-envelope',dict(envelope=json.dumps(dict(type=6,object='eventBridge',method='emitWebEvent',args=[message])),
        documentNonce=source.identity['nonce'],frame=source.url,mainFrame=True))
    delivery=source.event('script-delivery',dict(message=message));source.event('signal-return',dict(entry=delivery['sequence']))
    source.event('signal-return',dict(entry=envelope['sequence']))
    worker=workers['source']['workers'][0];worker['manager']['assignedEpochMs']=99000;worker['code']['submittedEpochMs']=99001
    for index,event in enumerate(worker['events']):
        epoch=99999 if index==0 else source.clock();event.update(invokedEpochMs=epoch,capturedEpochMs=epoch)
    slot=source.event('script-event-slot',dict(message=response,active=True));page=source.event('page-reply',dict(message=response))
    source.event('signal-return',dict(entry=page['sequence']));source.event('signal-return',dict(entry=slot['sequence']))
    received=source.clock();observed=source.clock();document=source.document()
    document['source']['dom']['echoes']=[dict(sequence=1,surface='world',message=response,receivedEpochMs=received,observedEpochMs=observed)]
    workers.update(clockBefore=dict(epochMs=source.clock(),monotonicMs=100),clockAfter=dict(epochMs=source.clock(),monotonicMs=101))
    ledger=source.ledger();ownership=dict(runId=RUN,fixtureUrl=URL,ticket=TICKET,nonce=vm.NONCE)
    result=(ledger,document,workers,ownership,vm.DIRECTORY,vm.ENTITY)
    return result+(source,) if include_source else result


class WorldWebEchoTests(unittest.TestCase):
    def test_actual_original_code_callback_native_delivery_and_matching_displayed_receive_join(self):
        result=echoes.chain(*originals());self.assertEqual([1,1,1],[len(result[k]) for k in ('attempts','accepted','echoes')])
        self.assertEqual('world-event',result['accepted'][0]['callback']['kind'])
        self.assertTrue(result['accepted'][0]['attempt']['nativeDispatch']['detail']['type']=='release')

    def test_ack_outgoing_reply_foreign_nonce_or_cooperative_echo_cannot_substitute_actual_boundaries(self):
        for fault in ('envelope','nonce','frame','mainFrame','delivery','nativeReturn','vmCode','worker','reply','slot','page','echo','timestamp'):
            ledger,document,workers,ownership,directory,entity=originals();worker=workers['source']['workers'][0]
            envelope=next(row for row in ledger['events'] if row['kind']=='native-envelope')
            if fault=='envelope':envelope['detail']['envelope']=json.dumps(dict(type=3))
            elif fault=='nonce':envelope['detail']['documentNonce']='foreign'
            elif fault=='frame':envelope['detail']['frame']='http://foreign.invalid/'
            elif fault=='mainFrame':envelope['detail']['mainFrame']=False
            elif fault=='delivery':next(row for row in ledger['events'] if row['kind']=='script-delivery')['detail']['message']='{}'
            elif fault=='nativeReturn':ledger['events']=[row for row in ledger['events'] if not(row['kind']=='signal-return' and row['detail']['entry']==envelope['sequence'])]
            elif fault=='vmCode':worker['code']['sha256']='a'*64
            elif fault=='worker':worker['events'][1]['payload']['entityId']='22222222-2222-4222-8222-222222222222'
            elif fault=='reply':worker['events'][2]['payload']['message']='{}'
            elif fault=='slot':next(row for row in ledger['events'] if row['kind']=='script-event-slot')['detail']['active']=False
            elif fault=='page':next(row for row in ledger['events'] if row['kind']=='page-reply')['detail']['message']='{}'
            elif fault=='echo':document['source']['dom']['echoes'][0]['message']=json.dumps(dict(contract='overte-web-parity-v1',action='echo',sequence=2,surface='world'))
            else:worker['events'][1]['invokedEpochMs']=99002
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):echoes.chain(ledger,document,workers,ownership,directory,entity)

    def test_foreign_normal_attempt_can_be_observed_with_no_bridge_delivery_or_echo(self):
        source=OriginalSources(status_origin='foreign');source.identity['sourceIdentity']='web-entity:'+vm.ENTITY;source.view['sourceIdentity']=source.identity['sourceIdentity']
        for event in source.events:event['identity']['sourceIdentity']=source.identity['sourceIdentity']
        source.pointer();workers=vm.packet(vm.execute()['events'][:1]);row=workers['source']['workers'][0]
        row['manager']['assignedEpochMs']=99000;row['code']['submittedEpochMs']=99001
        row['events'][0].update(invokedEpochMs=99999,capturedEpochMs=99999)
        workers.update(clockBefore=dict(epochMs=source.clock(),monotonicMs=100),clockAfter=dict(epochMs=source.clock(),monotonicMs=101))
        result=echoes.chain(source.ledger(),source.document(),workers,dict(runId=RUN,fixtureUrl=URL,ticket=TICKET,nonce=vm.NONCE),vm.DIRECTORY,vm.ENTITY)
        self.assertEqual([1,0,0],[len(result[k]) for k in ('attempts','accepted','echoes')])


if __name__=='__main__':unittest.main()
