"""Actual distinct Tablet DTO/source joins; native hooks are not executed."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import tablet_web_source as trace
from ios.self_tests.test_ios_tablet_web_sources import packet as source_packet,stamp,RUN,ROOT,IDENTITY


def query(index=1):return dict(schemaVersion=1,action=trace.ACTION,commandId='ios-'+format(index,'032x'),runId=RUN,fixtureUrl=ROOT)


def packet(index=1,inline=True):
    source=source_packet();nav=source['navigations'][1 if inline else 0]
    identity=dict(handle='1',creation=1,grant=1,page=1,nonce='11111111-2222-3333-4444-555555555555',
        url=source['carriers'][0]['bindings'][0]['transportUrl'] if inline else nav['sourceUrl'],
        sourceUrl=source['carriers'][0]['bindings'][0]['transportUrl'] if inline else nav['sourceUrl'],
        sourceIdentity=IDENTITY if inline else 'tablet:original-http-birth',surface='tablet',
        source=dict(root=nav['root'],navigation=nav['id'],fixtureUrl=ROOT,carrier='4'*32 if inline else None,binding='5'*32 if inline else None))
    value=dict(iosTabletWebVersion=1,commandId=query(index)['commandId'],runId=RUN,fixtureUrl=ROOT,instance='e'*32,sequence=index,processId=31,
        clockDomain='native-main-ios-tablet-web',clockBefore=stamp(91000),clockAfter=stamp(91000),complete=True,eventSequence=0,events=[])
    def event(kind,detail):
        ordinal=len(value['events'])+1;value['events'].append(dict(sequence=ordinal,eventId=format(ordinal,'032x'),kind=kind,
            clock=stamp(90400+ordinal),identity=deepcopy(identity),detail=deepcopy(detail)));value['eventSequence']=ordinal
    event('view-created',{});event('document-began',dict(frame=identity['url']))
    event('evaluation-enter',dict(codeSha256='a'*64));event('callback-enter',dict(entry=3,result=dict(error=False)))
    event('callback-return',dict(entry=3));event('native-finished',{});event('document-verified',{})
    return value


class TabletWebSourceTests(unittest.TestCase):
    def test_http_and_inline_original_sources_join_without_normalizing_either_dto(self):
        for inline in (False,True):
            value=packet(inline=inline);original=deepcopy(value);sources=source_packet();before=deepcopy(sources)
            trace.validate(value,query(),31,91000);self.assertEqual(value,trace.join_sources(value,sources));self.assertEqual([],trace.pending(value))
            self.assertEqual(original,value);self.assertEqual(before,sources)
            self.assertNotIn('httpStatus',value);self.assertNotIn('iosWorldWebVersion',value)

    def test_same_shaped_foreign_source_root_binding_policy_and_bytes_cannot_join(self):
        for fault in ('root','navigation','binding','carrier','policy','transport','unreturned','bytes','pid','retimed'):
            value=packet();sources=source_packet();item=value['events'][0]['identity']
            if fault=='root':item['source']['root']='9'*32
            elif fault=='navigation':item['source']['navigation']='2'*32
            elif fault=='binding':item['source']['binding']='9'*32
            elif fault=='carrier':item['source']['carrier']='9'*32
            elif fault=='policy':item['sourceIdentity']='tablet:pending-new-property'
            elif fault=='transport':item['sourceUrl']='http://'+'9'*32+'.overte-inline.invalid/index.html'
            elif fault=='unreturned':sources['carriers'][0]['bindings'][0].pop('returned')
            elif fault=='bytes':sources['navigations'][1]['body']['sha256']='9'*64
            elif fault=='pid':sources['processId']=32
            else:sources['carriers'][0]['bindings'][0]['returned']=stamp(90900)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):trace.join_sources(value,sources)

    def test_one_actual_grant_cannot_change_source_when_pending_properties_change(self):
        value=packet();sources=source_packet();trace.join_sources(value,sources)
        # Both source inputs exist and are internally valid. One actual native
        # grant still cannot change its original source association mid-flight.
        last=value['events'][-1]['identity'];last['source']=deepcopy(packet(inline=False)['events'][0]['identity']['source'])
        last['sourceIdentity']='tablet:original-http-birth';last['sourceUrl']=sources['navigations'][0]['sourceUrl']
        with self.assertRaises(NativeUIError):trace.join_sources(value,sources)

    def test_source_clock_domains_are_distinct_not_compared_as_shared_monotonic_origin(self):
        value=packet();sources=source_packet()
        # Same native process epochs, independent actual timer origins.
        for root in sources['roots']:
            root['clock']['monotonicMs']+=100000
        for nav in sources['navigations']:
            nav['clock']['monotonicMs']+=100000;nav['returned']['clock']['monotonicMs']+=100000
        carrier=sources['carriers'][0];carrier['clock']['monotonicMs']+=100000
        for binding in carrier['bindings']:
            binding['clock']['monotonicMs']+=100000;binding['returned']['monotonicMs']+=100000
        sources['clockBefore']['monotonicMs']+=100000;sources['clockAfter']['monotonicMs']+=100000
        trace.join_sources(value,sources)

    def test_native_owner_death_does_not_finish_original_callback(self):
        value=packet();value['events']=value['events'][:4];value['eventSequence']=4
        death=deepcopy(value['events'][0]);death.update(sequence=5,eventId='f'*32,kind='owner-destroyed',clock=stamp(90500));value['events'].append(death);value['eventSequence']=5
        self.assertEqual([3],trace.pending(value))
        changed=deepcopy(value);changed['events'][3]['identity']['grant']=2
        with self.assertRaises(NativeUIError):trace.original(changed)

    def test_prefix_counters_birth_clock_closed_schema_and_global_key_text_are_rejected(self):
        before=packet();current=packet(2);trace.validate(current,query(2),31,previous=before)
        for fault in ('prefix','birth','counter','bool','clock','world','key','expected'):
            value=deepcopy(current)
            if fault=='prefix':value['events'][0]['eventId']='f'*32
            elif fault=='birth':value['instance']='f'*32
            elif fault=='counter':value['sequence']=1
            elif fault=='bool':value['eventSequence']=True
            elif fault=='clock':value['clockBefore']=stamp(90999)
            elif fault=='world':value['events'][0]['identity']['surface']='world-entity'
            elif fault=='key':value['events'][0].update(kind='key-enter',detail=dict(text='private',key=65,modifiers=0))
            else:value['expectedPage']='reference'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):trace.validate(value,query(2),31,previous=before)

    def test_real_transport_sends_own_closed_action_and_unknown_return_is_never_replayed(self):
        calls=[];raw={}
        def send(q):
            calls.append(deepcopy(q));value=packet(len(calls));value['commandId']=q['commandId'];raw['value']=json.dumps(value)
        reader=trace.IOSTabletWebSource(send,lambda:raw['value'],lambda:91000,lambda:True,31,monotonic=lambda:0)
        a=reader.read(RUN,ROOT);b=reader.read(RUN,ROOT);self.assertEqual(trace.ACTION,calls[0]['action']);self.assertEqual(2,b['sequence'])
        a['events'].clear();self.assertEqual(7,len(reader.last['events']))
        def lost(q):calls.append(deepcopy(q));raise OSError('Lost actual send return')
        reader.send=lost
        with self.assertRaises(NativeUIError):reader.read(RUN,ROOT)
        self.assertEqual(3,len(calls))


if __name__=='__main__':unittest.main()
