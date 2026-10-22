"""Original source/carrier DTO boundaries; native Qt hooks remain uncompiled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import json
import unittest
from adapters.normal_ui import NativeUIError
from feature_journeys.browser_fixture import inline_source
from ios.adapters import tablet_web_sources as source

RUN='a'*32
ROOT='http://127.0.0.1:18000/feature-fixture/v1/runs/'+RUN+'/'
TICKET='b'*32
IDENTITY='tablet:com.highfidelity.interface.tablet.system:actual-source-birth'


def stamp(epoch=90000):return dict(epochMs=epoch,monotonicMs=epoch-80000)


def query(index=1):return dict(schemaVersion=1,action=source.ACTION,commandId='ios-'+format(index,'032x'),runId=RUN,fixtureUrl=ROOT)


def packet(index=1):
    raw=inline_source(RUN,TICKET,ROOT);encoded=base64.b64encode(raw).decode();inline='data:text/html;charset=utf-8;base64,'+encoded
    def navigation(id_,kind,url,epoch):
        return dict(id=id_,root='1'*32,fixtureUrl=ROOT,tablet='com.highfidelity.interface.tablet.system',sourceUrl=url,
            sourceSha256=hashlib.sha256(url.encode()).hexdigest(),scriptUrl='',kind=kind,body=None if kind=='http' else dict(base64=encoded,sha256=hashlib.sha256(raw).hexdigest(),charset='utf-8'),
            clock=stamp(epoch),returned=dict(clock=stamp(epoch+1),invoked=True))
    binding=dict(id='5'*32,clock=stamp(90200),token='6'*32,revision=1,transportUrl='http://'+'6'*32+'.overte-inline.invalid/index.html',
        sha256=hashlib.sha256(raw).hexdigest(),charset='utf-8',returned=stamp(90201),current=True,contextAlive=True,pageAlive=True)
    carrier=dict(id='4'*32,navigation='3'*32,root='1'*32,identity=IDENTITY,clock=stamp(90150),alive=True,bindings=[binding])
    return dict(iosTabletSourcesVersion=1,commandId=query(index)['commandId'],runId=RUN,fixtureUrl=ROOT,instance='f'*32,sequence=index,processId=31,
        clockDomain='native-main-ios-tablet-sources',clockBefore=stamp(91000),clockAfter=stamp(91000),complete=True,
        roots=[dict(id='1'*32,clock=stamp(89900),alive=True)],navigations=[navigation('2'*32,'http',ROOT+'tickets/'+TICKET+'/index.html',90000),navigation('3'*32,'inline',inline,90100)],carriers=[carrier])


def ended(value):
    current=deepcopy(value);row=current['carriers'][0];binding=row['bindings'][0]
    row.update(alive=False,retired=stamp(90400),retireReturned=stamp(90401),destroyed=stamp(90500));binding.update(current=False,pageAlive=False,revoked=stamp(90400));return current


class TabletSourcesTests(unittest.TestCase):
    def test_original_decoded_bytes_and_same_native_root_are_mandatory(self):
        value=packet();source.validate(value,query(),31,91000);carrier,binding=source.inline(value,IDENTITY)
        self.assertEqual('4'*32,carrier['id']);self.assertEqual('6'*32,binding['token'])
        # Invoking a normal source route supplies no document/DOM/HTTP result.
        self.assertNotIn('documentLoads',value);self.assertNotIn('httpStatus',value)
        for fault in ('bytes','source-hash','unjoined-root','no-http-input','retimed-input'):
            changed=deepcopy(value)
            if fault=='bytes':changed['navigations'][1]['body']['sha256']='0'*64
            elif fault=='source-hash':changed['navigations'][1]['sourceSha256']='0'*64
            elif fault=='unjoined-root':changed['carriers'][0]['root']='7'*32
            elif fault=='no-http-input':changed['navigations'].pop(0)
            else:changed['navigations'][1]['clock']=stamp(92000)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.validate(changed,query(),31,91000)

    def test_retired_flag_without_original_weak_death_and_revocation_is_not_absence(self):
        old=packet();value=ended(packet(2));source.validate(value,query(2),31,91000,old);source.retired(value,IDENTITY)
        for fault in ('live-owner','missing-revoke','live-page','resurrected-binding','missing-return'):
            changed=deepcopy(value);row=changed['carriers'][0];binding=row['bindings'][0]
            if fault=='live-owner':row['alive']=True
            elif fault=='missing-revoke':binding.pop('revoked')
            elif fault=='live-page':binding['pageAlive']=True
            elif fault=='missing-return':row.pop('retireReturned')
            else:binding.update(current=True)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.retired(changed,IDENTITY)
        resurrected=packet(3)
        with self.assertRaises(NativeUIError):source.validate(resurrected,query(3),31,91000,value)

    def test_native_histories_cannot_reset_rewrite_or_change_actual_source_birth(self):
        before=packet();after=packet(2);source.validate(after,query(2),31,91000,before)
        for fault in ('birth','rewrite','counter','bool-invoked','foreign-query'):
            changed=deepcopy(after)
            if fault=='birth':changed['instance']='0'*32
            elif fault=='rewrite':changed['navigations'][0]['returned']['clock']=stamp(90002)
            elif fault=='counter':changed['sequence']=1
            elif fault=='bool-invoked':changed['navigations'][0]['returned']['invoked']=1
            else:changed['runId']='0'*32
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.validate(changed,query(2),31,91000,before)

    def test_real_bounded_transport_sends_only_own_action_and_keeps_raw_original(self):
        calls=[];raw=[None]
        def send(request):
            calls.append(deepcopy(request));source.command(request);value=packet(len(calls));value['commandId']=request['commandId'];raw[0]=json.dumps(value)
        reader=source.IOSTabletSources(send,lambda:raw[0],lambda:91000,lambda:True,31,monotonic=lambda:0)
        first=reader.read(RUN,ROOT);second=reader.read(RUN,ROOT)
        self.assertEqual(2,len(calls));self.assertEqual(source.ACTION,calls[0]['action']);self.assertEqual(first['carriers'],second['carriers'])
        self.assertEqual(second,json.loads(raw[0]));self.assertEqual(2,reader.last['sequence'])
