"""Explicit native DTO boundary joined to real OAuth/social provider events."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import json
import unittest

from adapters.normal_ui import NativeUIError
from ios.adapters import avatar_social_http as native
from self_tests import test_avatar_social_provider as social_tests
from feature_journeys.avatar_social_provider import USERS

RUN, TICKET = social_tests.RUN, social_tests.TICKET
ORIGIN = 'https://owned.invalid'


def wire(raw):
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), contentBase64=base64.b64encode(raw).decode())


class SocialHttpTests(unittest.TestCase):
    def setUp(self):
        self.logic=social_tests.SocialTests(); self.logic.setUp()
        provider=self.logic.provider
        with provider.response('GET',USERS,'filter=connections',b'',self.logic.tokens['primary']) as response:
            status,raw,response_id,written=response
            written(dict(status=status,responseId=response_id,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
        self.status=provider.snapshot(RUN)
        self.value=dict(iosAvatarSocialHttpVersion=1,requestId='ios-'+'a'*32,runId=RUN,instance='b'*32,
            sequence=1,processId=42,clockDomain='native-process-avatar-social-http',
            clockBefore=dict(epochMs=9000001000,monotonicMs=1000),clockAfter=dict(epochMs=9000001001,monotonicMs=1001),events=[])
        self.xhr='c'*32; self.reply='d'*32
        source=dict(callerChain=['qrc:/scripts/modules/request.js','qrc:/scripts/system/pal.js'],
            engine=dict(instance='e'*32,assigned=True,url='qrc:/scripts/defaultScripts.js',loadGeneration=1,assignedEpochMs=9000000001),
            submitted=dict(submitted=True,encoding='utf-16le-code-units',codeUnits=100,sha256='f'*64,submittedEpochMs=9000000002),
            requestUrl=ORIGIN+USERS+'?filter=connections',method='GET',protocolSignature=base64.b64encode(b'p'*16).decode())
        self.add('created',source)
        self.add('callback-enter',dict(callback='readystatechange',readyState=1))
        self.add('callback-leave',dict(callback='readystatechange',readyState=1))
        self.add('sent',dict(replyId=self.reply,url=source['requestUrl'],method='GET',body=wire(b''),
                            authorizationAttached=True,contentType=''))
        self.add('timer-state',dict(active=False))
        self.add('reply-finished',dict(replyId=self.reply,httpStatus=200,networkError=0,responseId=response_id,body=wire(raw)))
        self.add('callback-enter',dict(callback='readystatechange',readyState=4))
        self.add('text-read',dict(replyId=self.reply,scriptSource=source['callerChain'][0],sha256=wire(raw)['sha256']))
        self.add('callback-leave',dict(callback='readystatechange',readyState=4))

    def add(self,kind,details=None):
        index=len(self.value['events'])+1
        self.value['events'].append(dict(sequence=index,eventId=f'{index:032x}',xhrId=self.xhr,kind=kind,
            clock=dict(epochMs=9000000100+index,monotonicMs=100+index),details={} if details is None else details))

    def consumed(self,value=None,status=None,**changes):
        arguments=dict(provider_instance=self.logic.provider.instance,owned_origin=ORIGIN,run=RUN,ticket=TICKET,role='primary',
            after_native_epoch=9000000000,after_provider_epoch=1700000000000,after_event=0)
        arguments.update(changes)
        return native.consumed_response(self.value if value is None else value,self.status if status is None else status,**arguments)

    def test_distinct_provider_native_clocks_join_exact_original_request_reply_and_callback_read(self):
        result=self.consumed()
        self.assertEqual(self.status['history'][0],result['http'])
        self.assertEqual(self.value['events'][7],result['nativeRead'])
        self.assertNotEqual(result['http']['capturedEpochMs'],result['nativeRead']['clock']['epochMs'])
        self.assertNotIn('connected',result)
        self.assertEqual(0,self.value['events'][3]['details']['body']['bytes'])

    def test_ACK_provider_or_finished_response_without_actual_callback_read_is_insufficient(self):
        for missing in ('text-read','reply-finished'):
            value=deepcopy(self.value)
            value['events']=[event for event in value['events'] if event['kind']!=missing]
            for sequence,event in enumerate(value['events'],1):event['sequence']=sequence
            with self.assertRaises(NativeUIError):self.consumed(value)
        value=deepcopy(self.value)
        # Move read out of actual callback while preserving valid clock/order.
        value['events'][7]['kind'],value['events'][8]['kind']='callback-leave','text-read'
        value['events'][7]['details'],value['events'][8]['details']=value['events'][8]['details'],value['events'][7]['details']
        with self.assertRaises(NativeUIError):self.consumed(value)

    def test_wrong_role_origin_ticket_native_or_provider_barrier_cannot_retime_old_request(self):
        for changed in (dict(role='actor'),dict(owned_origin='https://other.invalid'),dict(ticket='0'*32),
                        dict(after_native_epoch=9000000200),dict(after_provider_epoch=1700000000001),dict(after_event=1)):
            with self.assertRaises(NativeUIError):self.consumed(**changed)
        status=deepcopy(self.status);status['history'][0]['written']=False;status['history'][0]['writeEpochMs']=None
        with self.assertRaises(NativeUIError):self.consumed(status=status)

    def test_exact_bytes_authorization_and_first_original_script_owner_are_required(self):
        for index,key,replacement in ((3,'authorizationAttached',False),(3,'body',wire(b'foreign')),
                (5,'body',wire(b'{}')),(0,'callerChain',['qrc:/scripts/modules/request.js','qrc:/scripts/system/places/places.js'])):
            value=deepcopy(self.value);value['events'][index]['details'][key]=replacement
            with self.assertRaises(NativeUIError):self.consumed(value)
        value=deepcopy(self.value);value['events'][7]['details']['scriptSource']='qrc:/scripts/system/pal.js'
        with self.assertRaises(NativeUIError):native.original(value)

    def test_only_real_original_lifetime_events_drain_the_same_owned_XHR(self):
        self.assertFalse(native.drained(self.value,[self.xhr]))
        self.add('reply-destroyed',dict(replyId=self.reply)); self.add('callbacks-released')
        self.assertFalse(native.drained(self.value,[self.xhr]))
        self.add('timer-destroyed');self.add('xhr-destroyed')
        self.assertTrue(native.drained(self.value,[self.xhr]))
        with self.assertRaises(NativeUIError):native.drained(self.value,['0'*32])
        value=deepcopy(self.value);value['events'][-2]['kind']='xhr-destroyed'
        with self.assertRaises(NativeUIError):native.original(value)

    def test_history_truncation_rewrite_foreign_PID_source_or_clock_is_rejected(self):
        query=dict(schemaVersion=1,commandId=self.value['requestId'],action=native.ACTION,runId=RUN)
        native.validate(self.value,query,42)
        newer=deepcopy(self.value);newer.update(requestId='ios-'+'1'*32,sequence=2,
            clockBefore=dict(epochMs=9000001002,monotonicMs=1002),clockAfter=dict(epochMs=9000001003,monotonicMs=1003))
        query['commandId']=newer['requestId'];native.validate(newer,query,42,previous=self.value)
        for operation in ('rewrite','truncate','pid','birth','clock'):
            bad=deepcopy(newer)
            if operation=='rewrite':bad['events'][0]['details']['submitted']['sha256']='0'*64
            elif operation=='truncate':bad['events']=bad['events'][:-1]
            elif operation=='pid':bad['processId']=43
            elif operation=='birth':bad['instance']='0'*32
            else:bad['clockAfter']['monotonicMs']+=300
            with self.assertRaises(NativeUIError):native.validate(bad,query,42,previous=self.value)
        status=deepcopy(self.status);status['history'][0]['responseSha256']='0'*64
        with self.assertRaises(NativeUIError):native.provider_status(status,instance=self.logic.provider.instance,run=RUN,previous=self.status)


if __name__=='__main__':unittest.main()
