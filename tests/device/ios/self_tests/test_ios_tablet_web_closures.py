"""Independent native Tablet HTTP/inline lifetime DTO and source associations."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import tablet_web_closures as source,tablet_web_source as native
from ios.self_tests.test_ios_tablet_web_source import packet as trace,query as trace_query
from ios.self_tests.test_ios_tablet_web_sources import packet as sources,stamp,RUN,ROOT


def query(index=1):return dict(trace_query(index),action=source.ACTION)


def transcript(inline=True):
    value=trace(inline=inline);value['events'][0]['identity']['nonce']=''
    for event in value['events'][1:]:event['identity']['page']=2
    return value


def packet(index=1,inline=True,ended=False):
    view=transcript(inline)['events'][0]['identity']
    def row(id_,creation,page,epoch):
        descriptor=dict(handle=int(view['handle']),creation=creation,grant=view['grant'],page=page,surface='tablet',
            identitySha256=hashlib.sha256(view['sourceIdentity'].encode()).hexdigest(),sourceUrl=view['sourceUrl'],source=deepcopy(view['source']))
        zero=lambda:dict(created=0,retired=0,pending=0)
        return dict(id=id_,descriptor=descriptor,createdEpochMs=epoch,updatedEpochMs=90800 if ended else 90500,
            callbacks={key:zero() for key in source.KINDS},resources={key:zero() for key in source.RESOURCES})
    rows=[row(1,0,1,90399),row(2,1,1,90401),row(3,1,2,90402)]
    def count(row,kind,amount,callback=False):
        row['callbacks' if callback else 'resources'][kind]=dict(created=amount,retired=amount if ended else 0,pending=0 if ended else amount)
    count(rows[0],'policy-grant',1);count(rows[0],'native-delegate',1);count(rows[1],'native-view',1);count(rows[1],'native-presentation',2)
    count(rows[0],'rule-list',1,True);count(rows[1],'notification',3,True);count(rows[2],'javascript',1,True)
    return dict(iosTabletWebClosuresVersion=1,commandId=query(index)['commandId'],runId=RUN,fixtureUrl=ROOT,instance='d'*32,
        sequence=index,processId=31,capturedEpochMs=91000,complete=True,contexts=rows)


class TabletClosuresTests(unittest.TestCase):
    def test_original_http_and_inline_histories_join_pre_view_policy_and_actual_frame_birth(self):
        for inline in (False,True):
            before=packet(inline=inline);after=packet(2,inline=inline,ended=True)
            source.original(before);self.assertEqual(before,source.join_sources(before,sources(),transcript(inline)))
            source.validate(after,query(2),31,91000,before);source.join_sources(after,sources(),transcript(inline));self.assertEqual(3,len(source.drained(after,before)))
            if inline:self.assertIn('.overte-inline.invalid/',before['contexts'][0]['descriptor']['sourceUrl'])
            self.assertNotIn('iosWebClosureVersion',before)

    def test_no_callback_pending_is_not_weak_native_view_or_presentation_death(self):
        before=packet();after=packet(2,ended=True)
        for kind in ('native-view','native-delegate','native-presentation','policy-grant'):
            changed=deepcopy(after)
            row=next(row for row in changed['contexts'] if row['resources'][kind]['created']>0);counter=row['resources'][kind]
            counter['retired']-=1;counter['pending']+=1
            self.assertTrue(all(counter['pending']==0 for row in changed['contexts'] for counter in row['callbacks'].values()))
            with self.subTest(kind=kind),self.assertRaises(NativeUIError):source.drained(changed,before)
        empty=deepcopy(before);empty['contexts']=[]
        with self.assertRaises(NativeUIError):source.drained(after,empty)

    def test_source_stamp_carrier_identity_frame_and_pre_view_creation_must_be_original(self):
        for fault in ('root','carrier','identity','page','creation','sourceURL'):
            value=packet();item=value['contexts'][0]['descriptor']
            if fault=='root':item['source']['root']='9'*32
            elif fault=='carrier':item['source']['carrier']='9'*32
            elif fault=='identity':item['identitySha256']='9'*64
            elif fault=='page':item['page']=99
            elif fault=='creation':item['creation']=99
            else:item['sourceUrl']='http://'+'9'*32+'.overte-inline.invalid/index.html'
            source.original(value)  # individually typed descriptor, no source join
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.join_sources(value,sources(),transcript())

    def test_native_counters_source_birth_and_immutable_descriptor_cannot_reset_or_be_http_aliases(self):
        before=packet();after=packet(2,ended=True)
        for fault in ('birth','counter','row','rewrite','bool','legacy','foreignFixture'):
            value=deepcopy(after)
            if fault=='birth':value['instance']='9'*32
            elif fault=='counter':value['contexts'][0]['resources']['policy-grant']=dict(created=0,retired=0,pending=0)
            elif fault=='row':value['contexts'].pop(0)
            elif fault=='rewrite':value['contexts'][0]['createdEpochMs']+=1
            elif fault=='bool':value['contexts'][0]['callbacks']['javascript']['created']=True
            elif fault=='legacy':value['iosWebClosureVersion']=5;value.pop('iosTabletWebClosuresVersion')
            else:value['fixtureUrl']=ROOT.replace(RUN,'9'*32)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.validate(value,query(2),31,91000,before)

    def test_bounded_source_transport_returns_originals_and_unknown_send_is_not_replayed(self):
        sent=[];raw={}
        def send(q):
            sent.append(deepcopy(q));value=packet(len(sent));value['commandId']=q['commandId'];raw['value']=json.dumps(value)
        reader=source.IOSTabletWebClosures(send,lambda:raw['value'],lambda:91000,lambda:True,31,monotonic=lambda:0)
        value=reader.read(RUN,ROOT);self.assertEqual(source.ACTION,sent[0]['action']);self.assertEqual(packet()['contexts'],value['contexts'])
        def lost(q):sent.append(deepcopy(q));raise OSError('Lost actual closure query return')
        reader.send=lost
        with self.assertRaises(NativeUIError):reader.read(RUN,ROOT)
        self.assertEqual(2,len(sent))


if __name__=='__main__':unittest.main()
