"""Native Pal DTO boundary counterexamples; no native/device execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest

from adapters.normal_ui import NativeUIError
from ios.adapters import people_model as model

RUN='a'*32
PEER='e2e-'+'b'*32


def packet():
    root=dict(rootId='00000000-0000-4000-8000-000000000001',qmlSource='qrc:/qml/hifi/Pal.qml',windowPresent=True,
        visible=True,active=True,connectionState=dict(phase='idle',message='',peerName='',peer='',requestId=''),
        activeTab='connectionsTab',myData=dict(userName='self'),ignored={},nearbyUserModelData=[],nearbyRows=[],
        connectionRows=[dict(userName=PEER,connection='connection',profileUrl='',placeName='Owned domain')],
        timers=dict.fromkeys(model.TIMERS,False),panels=dict.fromkeys(model.PANELS,False),
        pagination=dict(endpoint='/api/v1/users/connections',initialized=True,requestPending=False,
            additionalFirstPageRequested=False,delayedClear=False,retrievedAtLeastOnePage=True,currentPageToRetrieve=-1,
            totalPages=1,totalEntries=1,itemsPerPage=1000,sortKey='username,ASC',searchFilter=''),httpCallbacks=[],httpCounter=1)
    return dict(iosPeopleModelVersion=1,requestId='ios-'+'c'*32,runId=RUN,instance='d'*32,sequence=1,processId=42,
        clockDomain='native-main-people-model',clockBefore=dict(epochMs=1700000000100,monotonicMs=100),
        clockAfter=dict(epochMs=1700000000110,monotonicMs=110),source=dict(complete=True,tabletShown=True,roots=[root]))


class PeopleModelTests(unittest.TestCase):
    def test_relationship_reads_only_actual_completed_Pal_table_and_keeps_materialized_rows_original(self):
        value=packet();rows=model.relationship(value,PEER,present=True,after_epoch=1700000000100)
        self.assertEqual(value['source']['roots'][0]['connectionRows'],rows)
        rows[0]['placeName']='changed'
        self.assertEqual('Owned domain',value['source']['roots'][0]['connectionRows'][0]['placeName'])
        with self.assertRaises(NativeUIError):model.relationship(value,PEER,present=False,after_epoch=1700000000100)
        with self.assertRaises(NativeUIError):model.relationship(value,PEER,present=True,after_epoch=1700000000101)

    def test_backend_ACK_requested_peer_or_placeholder_empty_model_is_not_materialization(self):
        for key,replacement in (('requestPending',True),('additionalFirstPageRequested',True),('delayedClear',True),
                ('retrievedAtLeastOnePage',False),('currentPageToRetrieve',1),('totalEntries',0)):
            value=packet();value['source']['roots'][0]['pagination'][key]=replacement
            with self.subTest(key=key),self.assertRaises(NativeUIError):
                model.relationship(value,PEER,present=True,after_epoch=1700000000100)
        value=packet();root=value['source']['roots'][0];root['connectionRows']=[];root['pagination']['totalEntries']=0
        with self.assertRaises(NativeUIError):model.relationship(value,PEER,present=True,after_epoch=1700000000100)
        self.assertEqual([],model.relationship(value,PEER,present=False,after_epoch=1700000000100))
        value['source']['complete']=False
        with self.assertRaises(NativeUIError):model.relationship(value,PEER,present=False,after_epoch=1700000000100)

    def test_hidden_retained_roots_actual_callbacks_prompt_and_three_timers_each_prevent_QML_drain(self):
        value=packet();value['source']['tabletShown']=False;root=value['source']['roots'][0];root['active']=False
        self.assertTrue(model.drained(value))
        for key in model.TIMERS:
            changed=deepcopy(value);changed['source']['roots'][0]['timers'][key]=True
            self.assertFalse(model.drained(changed))
        for key in model.PANELS:
            changed=deepcopy(value);changed['source']['roots'][0]['panels'][key]=True
            self.assertFalse(model.drained(changed))
        for key,replacement in (('httpCallbacks',['0']),('connectionState',dict(phase='cancelled',message='',peerName=''))):
            changed=deepcopy(value);changed['source']['roots'][0][key]=replacement
            self.assertFalse(model.drained(changed))
        hidden=deepcopy(root);hidden.update(rootId='00000000-0000-4000-8000-000000000002',visible=False)
        hidden['pagination']['requestPending']=True;value['source']['roots'].append(hidden)
        self.assertFalse(model.drained(value))

    def test_real_root_context_callback_key_and_native_clock_fail_closed(self):
        for field,replacement in (('rootId','guessed'),('qmlSource','https://foreign.invalid/Pal.qml'),
                ('httpCallbacks',['1']),('httpCallbacks',['00']),('httpCounter',True)):
            value=packet();value['source']['roots'][0][field]=replacement
            with self.subTest(field=field,replacement=replacement),self.assertRaises(NativeUIError):model.original(value)
        for field,replacement in (('processId',True),('iosPeopleModelVersion',True),('clockDomain','host')):
            value=packet();value[field]=replacement
            with self.subTest(field=field),self.assertRaises(NativeUIError):model.original(value)
        value=packet();value['clockAfter']['monotonicMs']=500
        with self.assertRaises(NativeUIError):model.original(value)

    def test_original_source_replacement_clock_regression_and_callback_counter_reset_cannot_hide_ownership(self):
        first=packet();second=deepcopy(first);second.update(requestId='ios-'+'e'*32,sequence=2)
        second['clockBefore']=dict(epochMs=1700000000200,monotonicMs=200)
        second['clockAfter']=dict(epochMs=1700000000210,monotonicMs=210)
        query=dict(schemaVersion=1,commandId=second['requestId'],action=model.ACTION,runId=RUN)
        model.validate(second,query,42,previous=first)
        for fault in ('source','counter','clock','duplicate'):
            changed=deepcopy(second)
            if fault=='source':changed['instance']='f'*32
            elif fault=='counter':changed['source']['roots'][0]['httpCounter']=0
            elif fault=='clock':changed['clockBefore']['epochMs']=1700000000100
            else:changed['source']['roots'].append(deepcopy(changed['source']['roots'][0]))
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):model.validate(changed,query,42,previous=first)


if __name__=='__main__':unittest.main()
