"""Real reciprocal provider logic and independently controlled native seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import unittest
from urllib.parse import urlencode
from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from ios.adapters import avatar_social as social,avatar_code
from ios.self_tests.test_ios_avatar_social_http import wire,ORIGIN
from ios.self_tests.test_ios_avatar_scripts import packet as scripts_packet
from ios.self_tests.test_ios_people_model import packet as people_packet
from ios.self_tests.test_ios_avatar_peer import setup as peer_setup
from ios.self_tests.test_ios_emote_peer import PRIMARY,ACTOR,native
from self_tests import test_avatar_social_provider as provider_tests
NODES,RUN,TICKET=provider_tests.NODES,provider_tests.RUN,provider_tests.TICKET
from self_tests.test_native_account_observation import account as account_packet


class SocialFixture:
    def __init__(self):
        self.logic=provider_tests.SocialTests();self.logic.setUp();self.expected=avatar_code.pins();self.frames={};self.http={}
        for role,binding in (('primary',PRIMARY),('actor',ACTOR)):
            frame=deepcopy(peer_setup()[0 if role=='primary' else 4]);originals=frame['originals'];pid=int(binding['processIdentity'])
            state=originals['state'];state['runId']=RUN;state['source']['sessionId']=NODES[role]
            rendered=originals['renderers'];rendered['runId']=RUN
            for row in rendered['source']['avatars']:row['sessionId']=NODES[role] if row['self'] else NODES['actor' if role=='primary' else 'primary']
            rendered['source']['avatars'].sort(key=lambda row:row['sessionId'])
            for packet in (state,rendered):
                packet['clockBefore']=dict(epochMs=9000001010,monotonicMs=1010);packet['clockAfter']=dict(epochMs=9000001020,monotonicMs=1020)
            for row in rendered['source']['avatars']:
                for key in ('rigPose','externalPose'):
                    if row[key]:row[key]['capturedEpochMs']=9000001010
            account=account_packet();account['loggedIn']=True;account['principalSha256']=hashlib.sha256(self.logic.principals[role].encode()).hexdigest()
            account['observation'].update(capturedEpochMs=9000001040,tokenPresent=True,tokenValid=True,
                endpointPresent=True,endpointSha256=hashlib.sha256(ORIGIN.encode()).hexdigest())
            middle=native(9000001040,4);middle['processId']=pid;middle['account']=account;originals['native']=middle
            people=people_packet();people.update(processId=pid,runId=RUN)
            people['clockBefore']=dict(epochMs=9000001050,monotonicMs=1050);people['clockAfter']=dict(epochMs=9000001060,monotonicMs=1060)
            model=people['source']['roots'][0];model['myData']['userName']=self.logic.principals[role]
            model['connectionRows'][0]['userName']=self.logic.principals['actor' if role=='primary' else 'primary']
            originals['people']=people
            packet=dict(iosAvatarSocialHttpVersion=1,requestId='ios-'+'a'*32,runId=RUN,instance='b'*32,sequence=1,
                processId=pid,clockDomain='native-process-avatar-social-http',clockBefore=dict(epochMs=9000001000,monotonicMs=1000),
                clockAfter=dict(epochMs=9000001001,monotonicMs=1001),events=[])
            scripts=scripts_packet();scripts.update(processId=pid,runId=RUN)
            scripts['clockBefore']=dict(epochMs=9000001100,monotonicMs=1100);scripts['clockAfter']=dict(epochMs=9000001110,monotonicMs=1110)
            worker=scripts['source']['workers'][0];worker['membership']['assignedEpochMs']=9000000001;worker['code']['submittedEpochMs']=9000000002
            worker['avatar']['code']=[dict(sequence=index,url='qrc:/scripts'+suffix,submittedEpochMs=9000000002+index,
                encoding='utf-16le-code-units',**identity) for index,(suffix,identity) in enumerate(self.expected.items(),1)]
            originals.update(http=packet,scripts=scripts);self.http[role]=packet
            frame['phaseBefore']=frame['phaseAfter']=dict(activations=[dict(ticket=TICKET)])
            frame['clockJoin'].update(nativeBefore=native(9000000000,3),nativeAfter=native(9000001200,5),
                hostBeforeEpochMs=1700000000000.,hostAfterEpochMs=1700000001200.,hostBeforeMonotonic=1.,hostAfterMonotonic=2.2,
                sourceTimes=[dict(source='native',field='capturedEpochMs',epochMs=9000001040)])
            for key in ('nativeBefore','nativeAfter'):frame['clockJoin'][key]['processId']=pid
            self.frames[role]=frame
        self.seal()

    def seal(self):
        for frame in self.frames.values():frame['clockJoin']['originalsSha256']=digest(frame['originals'])

    def response(self,role,method,path= social.REQUEST,query='',body=None):
        if body is None:body=dict(user_connection_request=dict(node_id=NODES[role],proposed_node_id=NODES['actor' if role=='primary' else 'primary'])) if method=='POST' else None
        raw=json.dumps(body).encode() if body is not None else b''
        with self.logic.provider.response(method,path,query,raw,self.logic.tokens[role]) as response:
            status,data,response_id,written=response
            written(dict(status=status,responseId=response_id,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
        packet=self.http[role];xhr=f'{len(packet["events"])+100:032x}';reply=f'{len(packet["events"])+200:032x}'
        suffix='/system/libraries/peopleConnection.js' if path==social.REQUEST else '/system/request-service.js' if path==social.CONNECTIONS else '/system/pal.js'
        worker=self.frames[role]['originals']['scripts']['source']['workers'][0]
        source=dict(callerChain=['qrc:/scripts/modules/request.js','qrc:/scripts'+suffix],engine=deepcopy(worker['membership']),
            submitted=deepcopy(worker['code']),requestUrl=ORIGIN+path+('?' +query if query else ''),method=method,protocolSignature='cHBwcHBwcHBwcHBwcHBwcA==')
        def add(kind,details):
            index=len(packet['events'])+1
            packet['events'].append(dict(sequence=index,eventId=f'{index:032x}',xhrId=xhr,kind=kind,
                clock=dict(epochMs=9000000100+index,monotonicMs=100+index),details=details))
        add('created',source);add('sent',dict(replyId=reply,url=source['requestUrl'],method=method,body=wire(raw),authorizationAttached=True,contentType='application/json'))
        add('reply-finished',dict(replyId=reply,httpStatus=status,networkError=0,responseId=response_id,body=wire(data)))
        add('callback-enter',dict(callback='readystatechange',readyState=4))
        add('text-read',dict(replyId=reply,scriptSource=source['callerChain'][0],sha256=wire(data)['sha256']))
        add('callback-leave',dict(callback='readystatechange',readyState=4));self.seal()
        return json.loads(data)

    def connect(self):
        self.response('primary','POST');self.response('actor','POST')
        self.response('primary','GET',query=urlencode(dict(node_id=NODES['primary'],proposed_node_id=NODES['actor'])))
        for role in ('primary','actor'):self.response(role,'GET',social.CONNECTIONS,'page=1&per_page=1000&sort=username%2CASC')

    def kwargs(self):return dict(principals=self.logic.principals,owned_origin=ORIGIN,provider_instance=self.logic.provider.instance,run=RUN,ticket=TICKET)
    def connected(self):
        self.seal()
        return social.connected(self.frames['primary'],self.frames['actor'],PRIMARY,ACTOR,self.logic.provider.snapshot(RUN),
            **self.kwargs(),barriers={role:dict(nativeEpochMs=9000000000,providerEpochMs=1700000000000,httpEvent=0) for role in ('primary','actor')},expected_code=self.expected)


class AvatarSocialTests(unittest.TestCase):
    def test_both_actual_POSTs_consumed_bytes_candidate_modules_and_materialized_tables(self):
        fixture=SocialFixture();fixture.connect();value=fixture.connected()
        self.assertEqual('connected',value['connection']);self.assertFalse(value['pendingDialog'])
        self.assertEqual({'primary','actor'},set(value['consumptions']))
        self.assertNotEqual(value['consumptions']['primary']['post']['original']['http']['capturedEpochMs'],
            value['consumptions']['primary']['post']['original']['nativeRead']['clock']['epochMs'])
        from ios.adapters import avatar_social_http as http
        packet=fixture.http['primary'];status=fixture.logic.provider.snapshot(RUN);before=deepcopy(packet)
        kwargs=dict(provider_instance=fixture.logic.provider.instance,owned_origin=ORIGIN,run=RUN,ticket=TICKET,
            role='primary',after_native_epoch=9000000000,after_provider_epoch=1700000000000,after_event=0)
        rows=http.consumed_responses(packet,status,**kwargs)
        self.assertEqual(3,len(rows));self.assertEqual(rows[-1],http.consumed_response(packet,status,**kwargs))
        self.assertEqual(before,packet)
        self.assertEqual([],http.consumed_responses(packet,status,**(kwargs|{'after_event':100})))
        with self.assertRaises(NativeUIError):http.consumed_response(packet,status,**(kwargs|{'after_event':100}))

    def test_provider_ACK_get_or_success_without_actual_peer_POST_and_consumption_is_insufficient(self):
        for fault in ('actorRead','post','model','row','module','principal','unparsed','lateRead'):
            fixture=SocialFixture();fixture.connect();frame=fixture.frames['actor'];native=frame['originals']
            if fault=='actorRead':native['http']['events']=[]
            elif fault=='post':
                native['http']['events']=native['http']['events'][6:]
                for index,event in enumerate(native['http']['events'],1):event['sequence']=index
            elif fault=='model':native['people']['source']['roots'][0]['pagination']['retrievedAtLeastOnePage']=False
            elif fault=='row':native['people']['source']['roots'][0]['connectionRows'][0]['placeName']='stale row'
            elif fault=='module':native['scripts']['source']['workers'][0]['avatar']['code'][0]['sha256']='0'*64
            elif fault=='principal':native['native']['account']['principalSha256']='0'*64
            elif fault=='unparsed':native['people']['source']['roots'][0]['httpCallbacks']=['0']
            else:native['people']['clockBefore']['epochMs']=9000000100
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):fixture.connected()

    def test_real_invitation_needs_matching_actual_peer_prompt_and_same_original_request(self):
        fixture=SocialFixture();request='00000000-0000-4000-8000-000000000009'
        for role,other,phase in (('primary','actor','outgoing'),('actor','primary','incoming')):
            model=fixture.frames[role]['originals']['people']['source']['roots'][0]
            model['connectionState']=dict(phase=phase,message='',peerName='actual peer',peer=NODES[other],requestId=request)
            model['panels']['connectionPrompt']=True
        fixture.seal()
        def read():return social.pending(fixture.frames['primary'],fixture.frames['actor'],PRIMARY,ACTOR,
            fixture.logic.provider.snapshot(RUN),**fixture.kwargs(),expected_code=fixture.expected)
        self.assertEqual('pending',read()['connection'])
        fixture.frames['actor']['originals']['people']['source']['roots'][0]['connectionState']['requestId']=NODES['actor'];fixture.seal()
        with self.assertRaises(NativeUIError):read()

    def test_actual_delete_and_fresh_empty_materialized_tables_are_both_required(self):
        fixture=SocialFixture()
        fixture.logic.request('primary');fixture.logic.request('actor')
        fixture.response('primary','DELETE','/api/v1/user/connections/'+fixture.logic.principals['actor'])
        for role in ('primary','actor'):
            fixture.response(role,'GET',social.CONNECTIONS,'page=1&per_page=1000&sort=username%2CASC')
            root=fixture.frames[role]['originals']['people']['source']['roots'][0]
            root['connectionRows']=[];root['pagination']['totalEntries']=0
        def read():
            fixture.seal()
            return social.absent(fixture.frames['primary'],fixture.frames['actor'],PRIMARY,ACTOR,
                fixture.logic.provider.snapshot(RUN),**fixture.kwargs(),expected_code=fixture.expected,require_delete=True,
                barriers={role:dict(nativeEpochMs=9000000000,providerEpochMs=1700000000000,httpEvent=0) for role in ('primary','actor')})
        self.assertEqual('none',read()['connection'])
        fixture.http['primary']['events']=fixture.http['primary']['events'][6:]
        for index,event in enumerate(fixture.http['primary']['events'],1):event['sequence']=index
        with self.assertRaises(NativeUIError):read()


if __name__=='__main__':unittest.main()
