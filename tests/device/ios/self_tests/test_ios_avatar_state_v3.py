"""Writer-three native producer seams and actual versioned source/transport."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import json
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from ios.adapters import avatar_state,feature_observation
from ios.adapters.avatar_postlogout import restored
from ios.self_tests import test_ios_avatar_sources as sources_fixture
from ios.self_tests.test_ios_avatar_state import RUN,ORIGINAL,A,MISSING,DEFAULT,Boundary,Native,ClockBoundary
from self_tests.test_native_account_observation import account,event


def packet3():
    # This producer emits v3 directly. Existing v1/v2 fixtures are unchanged.
    return dict(iosAvatarStateVersion=3,requestId='ios-'+'b'*32,runId=RUN,instance='c'*32,sequence=1,processId=42,
        clockDomain='native-main-avatar',clockBefore=dict(epochMs=1700000000100,monotonicMs=100),clockAfter=dict(epochMs=1700000000200,monotonicMs=200),
        source=dict(sessionPresent=True,sessionId='00000000-0000-4000-8000-000000000001',requestedUrl=ORIGINAL,resourceUrl=ORIGINAL,
            defaultResourceUrl=DEFAULT,geometryLoaded=True,rigReady=True,shouldRender=True,targetScale=1.,modelScale=1.,jointNames=['Root','Hips','Head'],
            bookmarks=dict(source='AvatarBookmarks.getBookmarks',entries={},loadError=False),
            bookmarkFile=dict(source='avatar-bookmarks-persistence',status='ready',reason='',bytes=2,sha256=hashlib.sha256(b'{}').hexdigest(),
                contentBase64=base64.b64encode(b'{}').decode(),identity=dict(device='1',inode='1')),
            modelHistory=dict(avatarModelHistoryVersion=1,instance='d'*32,processId=42,currentGeneration=0,eventSequence=0,complete=True,events=[])))


class State3Boundary(Boundary):
    def original(self):
        self.clock+=.001;value=packet3();self.sequence+=1;value.update(requestId=self.requests[-1]['commandId'],sequence=self.sequence)
        value['clockBefore']=self.clocks();self.clock+=.001;value['clockAfter']=self.clocks();self.last=deepcopy(value);return json.dumps(value)


class AvatarState3Tests(unittest.TestCase):
    def test_actual_HTTP_AFC_factory_retains_writer3_and_original_independent_clocks(self):
        native=Native();clock=ClockBoundary();source=State3Boundary();observer=native.observer()
        observer.monotonic=lambda:source.clock;observer.sleep=source.sleep;observer.epoch_ms=lambda:9000
        def stamp(value):
            source.native_clock();epoch=source.epoch();value.update(processId=42,capturedEpochMs=epoch,requestedEpochMs=epoch,animation={},animationFence={})
        clock.mutate=stamp
        def post(request,timeout):
            query=native.fixture.set_client_command(json.loads(request.data));native.commands.append(deepcopy(query));native.echo=json.dumps(query).encode()
            (clock if query['action']=='feature-native-observe' else source).send(query);return native
        def execute(session,operation,values):
            self.assertEqual(('native-session','mobile: pullFile'),(session,operation));path=values['remotePath'];native.reads.append(path)
            return base64.b64encode((clock.original() if path.endswith('/feature-native-observation.json') else source.original()).encode()).decode()
        with patch.object(feature_observation,'post_request',side_effect=post),patch.object(native,'execute',side_effect=execute):value=observer.avatar_state().read(RUN)
        self.assertEqual(source.last,value);self.assertEqual(3,value['iosAvatarStateVersion']);self.assertTrue(value['source']['sessionPresent'])
        self.assertEqual(['feature-native-observe',avatar_state.ACTION,'feature-native-observe'],[row['action'] for row in native.commands])

    def test_active_model_reader_and_fact_helpers_refuse_null_or_contradictory_session(self):
        valid=packet3();avatar_state.original(valid)
        for present,session in ((False,'00000000-0000-0000-0000-000000000000'),(True,'00000000-0000-0000-0000-000000000000'),(False,valid['source']['sessionId']),(1,valid['source']['sessionId'])):
            value=deepcopy(valid);value['source'].update(sessionPresent=present,sessionId=session)
            with self.subTest(present=present,session=session),self.assertRaises(NativeUIError):avatar_state.original(value)
            with self.assertRaises(NativeUIError):avatar_state.model_state(value,original_url=ORIGINAL,avatar_url=A,missing_url=MISSING)

    def test_active_source_group_accepts_native_writer3_but_never_signedout_source(self):
        f=sources_fixture.AvatarSourcesTests();f.setUp();self.addCleanup(f.doCleanups);f.fixture.prototypes['state']=packet3()
        with f.lock.held():
            owner=f.owner();value=owner.read();self.assertEqual(3,value['originals']['state']['iosAvatarStateVersion'])
            f.fixture.prototypes['state']['source'].update(sessionPresent=False,sessionId='00000000-0000-0000-0000-000000000000')
            with self.assertRaises(NativeUIError):owner.read()


class AvatarPostLogoutTests(unittest.TestCase):
    def setUp(self):
        self.child='e'*32;self.fixture='https://controlled.invalid/feature-fixture/v1/runs/'+self.child+'/'
        core=ClockBoundary();core.send(dict(commandId='ios-'+'1'*32));self.before=deepcopy(core.sample)
        self.before.update(processId=42,sequence=1,capturedEpochMs=20000,requestedEpochMs=20000,animation={},animationFence={})
        self.before['account']=account();self.before['account'].update(loggedIn=True,principalSha256=hashlib.sha256(('e2e-'+self.child).encode()).hexdigest())
        self.before['account']['observation'].update(tokenPresent=True,tokenValid=True,refreshPresent=True,endpointSha256=hashlib.sha256(b'https://controlled.invalid').hexdigest())
        self.accounts=[]
        for index,epoch in ((2,20001),(3,20004)):
            value=deepcopy(self.before);value.update(requestId='ios-'+str(index)*32,sequence=index,capturedEpochMs=epoch,requestedEpochMs=epoch)
            value['account'].update(loggedIn=False,principalSha256=hashlib.sha256(b'').hexdigest())
            value['account']['observation'].update(capturedEpochMs=epoch,credentialGeneration=2,tokenPresent=False,tokenValid=False,refreshPresent=False,
                eventSequence=1,events=[event(kind='logout-complete',epoch=20001,generation=2)])
            self.accounts.append(value)
        self.baseline=packet3();self.current=packet3();self.current.update(requestId='ios-'+'4'*32,sequence=2)
        self.baseline['clockBefore'].update(epochMs=19998);self.baseline['clockAfter'].update(epochMs=19999)
        self.current['clockBefore'].update(epochMs=20002);self.current['clockAfter'].update(epochMs=20003)
        self.current['source'].update(sessionPresent=False,sessionId='00000000-0000-0000-0000-000000000000')
        from ios.self_tests.test_ios_avatar_input_owner import BINDING
        self.binding=BINDING
    def derive(self):return restored(self.current,self.baseline,*self.accounts,self.before,binding=self.binding,child_run=self.child,fixture_url=self.fixture,ticket='f'*32)
    def test_only_closed_postlogout_join_accepts_actual_zero_uuid_without_relabeling(self):
        before=deepcopy(self.current);result=self.derive();self.assertFalse(result['sessionPresent'])
        self.assertEqual('00000000-0000-0000-0000-000000000000',result['actualSessionId']);self.assertEqual(before,self.current)
        with self.assertRaises(NativeUIError):avatar_state.original(self.current)
    def test_actual_absent_empty_bookmark_file_is_distinct_from_unavailable_or_loaded_entries(self):
        from ios.adapters.avatar_observation import bookmark_file
        absent=dict(source='avatar-bookmarks-persistence',status='absent',reason='',bytes=None,sha256=None,contentBase64=None,identity=None)
        self.baseline['source']['bookmarkFile']=deepcopy(absent)
        self.assertEqual({},bookmark_file(self.baseline['source'],allow_missing=True));self.derive()
        with self.assertRaises(NativeUIError):bookmark_file(self.baseline['source'],allow_missing=False)
        self.baseline['source']['bookmarks']['entries']['unrelated']={}
        with self.assertRaises(NativeUIError):bookmark_file(self.baseline['source'],allow_missing=True)
        self.baseline['source']['bookmarks']['entries']={};self.baseline['source']['bookmarkFile'].update(status='unavailable',reason='open-error')
        with self.assertRaises(NativeUIError):bookmark_file(self.baseline['source'],allow_missing=True)
        with self.assertRaises(NativeUIError):self.derive()
    def test_missing_logout_foreign_account_generation_clock_or_model_cannot_establish_restoration(self):
        for fault in ('signal','logged-in','generation','time','model','session','birth','version'):
            old=deepcopy((self.current,self.accounts))
            if fault=='signal':self.accounts[0]['account']['observation'].update(eventSequence=0,events=[])
            elif fault=='logged-in':self.accounts[0]['account']=deepcopy(self.before['account'])
            elif fault=='generation':self.accounts[1]['account']['observation']['credentialGeneration']=3
            elif fault=='time':self.current['clockAfter']['epochMs']=20005
            elif fault=='model':self.current['source']['resourceUrl']=A
            elif fault=='session':self.current['source']['sessionPresent']=True
            elif fault=='birth':self.current['instance']='f'*32
            else:self.current['iosAvatarStateVersion']=2;del self.current['source']['sessionPresent']
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.derive()
            self.current,self.accounts=old


if __name__=='__main__':unittest.main()
