"""Host-only original source producers; no phone/session transport is executed."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import subprocess
import unittest
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[1]/'adapters/android-phone')]
from adapters.normal_ui import NativeUIError
from overte_phone_avatar_people_native import PhoneAvatarPeopleObservation,command,validate,history,model,replies,digest
from self_tests.test_native_account_observation import account
RUN='a'*32
SESSION='11111111-1111-4111-8111-111111111111'
URL='https://controlled.invalid/feature-fixture/v1/runs/'+RUN+'/tickets/'+'b'*32+'/avatar-a.fst'


def loads(url=URL,*,instance='1'*32):
    return dict(modelLoadsVersion=1,instance=instance,sequence=1,capturedEpochMs=20000,complete=True,currentGeneration=1,requestedSha256=digest(url),events=[
        dict(eventSequence=1,generation=1,kind='requested',capturedEpochMs=19999,requestedSha256=digest(url),resourceSha256='',success=None),
        dict(eventSequence=2,generation=1,kind='finished',capturedEpochMs=20000,requestedSha256=digest(url),resourceSha256=digest(url),success=True)])


def avatar():
    return dict(sessionId=SESSION,replicated=False,requestedUrl=URL,advertisedLoads=loads(),modelInstance='2'*32,modelLoads=loads(instance='3'*32),rigId=4,
        loaded=True,visible=True,addedToScene=True,targetScale=1.0,scale=1.0,hipsJoint=17,feetPosition=[0,0,0],orientation=[0,0,0,1],shouldRender=True,
        geometry=dict(instance='4'*32,url=URL.rsplit('/',1)[0]+'/mannequin/mannequin.fbx',texturesLoaded=True,textures={'eyes':URL.rsplit('/',1)[0]+'/mannequin/Eyes.png'}))


def source():
    prefs={key:dict(present=False,value=None) for key in ('filtered','nearDistance','nearbySortIndicatorColumn','nearbySortIndicatorOrder','connectionsSortIndicatorColumn','connectionsSortIndicatorOrder')}
    return dict(view=dict(avatarPeopleViewVersion=1,tabletShown=False,avatar=dict(present=False,dialogs=[]),people=dict(present=False,dialog=False),models={},preferences=prefs),
        bookmarks=dict(present=False,sha256=digest(''),bytes=0,bookmarks={}),auth=account(),accountOrigin='https://controlled.invalid',avatar=avatar(),peers=[],canRezAvatarEntities=True,attachments=[],preferredAvatarUrl=URL,preferredAvatarName='',
        domainId='22222222-2222-4222-8222-222222222222',connected=True,
        resourceReplies=dict(resourceRepliesVersion=1,instance='5'*32,sequence=1,capturedEpochMs=20000,complete=True,runId=RUN,events=[]),
        peopleReplies=dict(peopleRepliesVersion=1,instance='6'*32,sequence=1,capturedEpochMs=20000,complete=True,events=[]),
        avatarEntityOrigins=dict(avatarEntityOriginsVersion=1,instance='7'*32,sequence=1,capturedEpochMs=20000,runId=RUN,complete=True,events=[]),
        avatarEntities=dict(complete=True,entities=[],absentIds=[],advertisedIds=[],queriedIds=[],rememberedIds=[],retainedIds=[]))


class Boundary:
    def __init__(self):self.epoch=20000;self.clock=0;self.sequence=0;self.commands=[];self.sample=None;self.okay=True;self.edit=None;self.ignored=False;self.state=source()
    def send(self,request):
        self.commands.append(deepcopy(request))
        if self.ignored:return
        self.sequence+=1;self.epoch+=1
        value=deepcopy(self.state)
        value['auth']['observation']['capturedEpochMs']=self.epoch
        for actual in [value['avatar'],*value['peers']]:
            for key in ('advertisedLoads','modelLoads'):actual[key]['sequence']=self.sequence;actual[key]['capturedEpochMs']=self.epoch
        for key in ('resourceReplies','peopleReplies','avatarEntityOrigins'):value[key]['sequence']=self.sequence;value[key]['capturedEpochMs']=self.epoch
        self.sample=dict(avatarPeopleObservationVersion=1,commandId=request['commandId'],runId=RUN,instance='f'*32,sequence=self.sequence,processId=31,
            requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,source=value)
        if self.edit:self.edit(self.sample)
    def sleep(self,seconds):self.clock+=seconds;self.epoch+=round(seconds*1000)
    def reader(self):return PhoneAvatarPeopleObservation(self.send,lambda:json.dumps(self.sample),lambda:self.epoch,lambda:self.okay,31,monotonic=lambda:self.clock,sleep=self.sleep)


class AvatarPeopleNativeTests(unittest.TestCase):
    def test_closed_original_query_has_no_expected_or_mutating_fields(self):
        b=Boundary();r=b.reader();self.assertEqual(r.read(RUN),b.sample)
        self.assertEqual({'schemaVersion','commandId','action','runId'},set(b.commands[0]));self.assertEqual(2,r.read(RUN)['sequence'])
        valid=dict(schemaVersion=1,commandId='a'*32,runId=RUN,action='phone-avatar-people-observe')
        for edit in (dict(schemaVersion=True),dict(expectedLoaded=True),dict(expectedSession=SESSION),dict(action='phone-avatar-people-set'),dict(commandId='ios-'+'a'*32)):
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):command(valid|edit)
    def test_missing_mandatory_sources_boolean_versions_and_wrong_process_fail(self):
        for edit in (lambda v:v.update(processId=32),lambda v:v.update(avatarPeopleObservationVersion=True),lambda v:v['source'].pop('peopleReplies'),
                lambda v:v['source']['resourceReplies'].update(complete=False),lambda v:v['source']['avatar'].update(geometry=None),lambda v:v['source']['view'].update(expectedDialog=False)):
            b=Boundary();b.edit=edit
            with self.subTest(edit=edit),self.assertRaises((NativeUIError,KeyError)):b.reader().read(RUN)
    def test_advertised_and_loaded_geometry_are_independent_originals(self):
        b=Boundary();b.state['avatar']['geometry']=None;b.state['avatar']['loaded']=False
        value=b.reader().read(RUN);self.assertEqual(URL,value['source']['avatar']['requestedUrl']);self.assertIsNone(value['source']['avatar']['geometry'])
    def test_failed_generation_survives_original_fallback_and_new_request_clears_its_scope(self):
        missing=URL.replace('avatar-a.fst','missing.fst');h=loads(missing);h['events'][1].update(success=False)
        h['events'].append(dict(eventSequence=3,generation=1,kind='finished',capturedEpochMs=20000,requestedSha256=digest(missing),resourceSha256=digest('qrc:/meshes/defaultAvatar_full.fst'),success=True))
        self.assertEqual(h,history(h,20000));self.assertFalse(h['events'][1]['success']);self.assertTrue(h['events'][2]['success'])
        wrong=deepcopy(h);wrong['events'][1]['generation']=2
        with self.assertRaises(NativeUIError):history(wrong,20000)
        wrong=deepcopy(h);wrong['events'][2]['requestedSha256']=digest(URL)
        with self.assertRaises(NativeUIError):history(wrong,20000)
    def test_original_history_cannot_be_rewritten_dropped_or_reinstanced(self):
        for edit in (lambda v:v['source']['avatar']['advertisedLoads']['events'][1].update(success=False),
                lambda v:v['source']['avatar']['advertisedLoads'].update(instance='e'*32),
                lambda v:v['source']['avatar']['advertisedLoads']['events'].pop(),
                lambda v:v['source']['peopleReplies'].update(instance='e'*32)):
            b=Boundary();r=b.reader();r.read(RUN);b.edit=edit
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):r.read(RUN)
    def test_foreign_duplicate_peer_and_unbound_native_requested_model_fail(self):
        for edit in (lambda s:s['avatar'].update(requestedUrl=URL+'-foreign'),lambda s:s['peers'].append(deepcopy(s['avatar'])),lambda s:s['peers'].append(deepcopy(s['avatar'])|dict(sessionId='33333333-3333-4333-8333-333333333333')),lambda s:s.update(domainId='00000000-0000-0000-0000-000000000000')):
            b=Boundary();edit(b.state)
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):b.reader().read(RUN)
    def test_stale_future_and_slow_native_acquisitions_fail(self):
        for edit in (lambda v:v.update(requestedEpochMs=18000,capturedEpochMs=18000),lambda v:v.update(capturedEpochMs=23000),
                lambda v:v.update(requestedEpochMs=18000,capturedEpochMs=20001)):
            b=Boundary();b.edit=edit
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):b.reader().read(RUN)
        b=Boundary();b.ignored=True
        with self.assertRaises(NativeUIError):b.reader().read(RUN)
        self.assertEqual(1,len(b.commands))
    def test_lost_candidate_guard_prevents_even_readonly_dispatch(self):
        b=Boundary();b.okay=False
        with self.assertRaises(NativeUIError):b.reader().read(RUN)
        self.assertEqual([],b.commands)
    def test_original_xhr_body_reply_hashes_and_response_identity_are_retained(self):
        b=Boundary();b.state['peopleReplies']['events']=[dict(eventSequence=1,responseId='c'*32,method='POST',requestedUrlSha256=digest('https://controlled.invalid/api/v1/user/connection_request'),
            replyUrlSha256=digest('https://controlled.invalid/api/v1/user/connection_request'),requestBodySha256=digest('original body'),httpStatus=200,networkError=0,fromCache=False,redirected=False,capturedEpochMs=20000,bytes=2,sha256=digest('{}'))]
        r=b.reader();one=r.read(RUN);self.assertEqual(digest('original body'),one['source']['peopleReplies']['events'][0]['requestBodySha256'])
        b.state['peopleReplies']['events'][0]['sha256']=digest('foreign')
        with self.assertRaises(NativeUIError):r.read(RUN)
    def test_ack_expected_state_and_old_avatar_projection_cannot_replace_original(self):
        for value in (dict(performed=True),dict(avatar='A',modelLoaded=True,loadFailed=False),dict(available=False)):
            b=Boundary();b.edit=lambda original:original.update(source=value)
            with self.subTest(value=value),self.assertRaises(NativeUIError):b.reader().read(RUN)

class AvatarEntityRetirementTests(unittest.TestCase):
    def original(self):
        b=Boundary();id='88888888-8888-4888-8888-888888888888';url=URL.rsplit('/',1)[0]+'/gltf-bundle/main.gltf'
        b.state['avatarEntityOrigins']['events']=[dict(eventSequence=1,capturedEpochMs=20000,runId=RUN,ticket='b'*32,
            entityId=id,parentId=SESSION,parentJointIndex=17,treePresent=True,modelUrlSha256=digest(url))]
        row=dict(entityId=id,type='Model',host='avatar',parentId=SESSION,parentJointIndex=17,modelUrl=url,visible=True,originalObject=True,
            localPosition=[0,0,0],localRotation=[0,0,0,1],localDimensions=[1,1,1],model=None)
        b.state['avatarEntities']=dict(complete=True,entities=[row],absentIds=[],advertisedIds=[id],queriedIds=[id],rememberedIds=[id],retainedIds=[id])
        return b,id,url
    def test_map_removal_tree_removal_and_final_native_object_drain_are_separate_originals(self):
        from overte_phone_avatar_people_measurements import wearable
        from feature_journeys.phase_fixture import PhasePending
        b,id,url=self.original();r=b.reader();r.read(RUN)
        actual=b.state['avatarEntities'];actual['advertisedIds']=[]
        with self.assertRaises(PhasePending):wearable(RUN,r.read(RUN)['source'],dict(wearable={url}),{})
        actual.update(entities=[],absentIds=[id])
        with self.assertRaises(PhasePending):wearable(RUN,r.read(RUN)['source'],dict(wearable={url}),{})
        actual['retainedIds']=[]
        self.assertEqual((False,[id]),wearable(RUN,r.read(RUN)['source'],dict(wearable={url}),{}))
        self.assertEqual([id],actual['rememberedIds']) # Absence never forgets the queried original.
    def test_same_uuid_replacement_never_supplies_original_ownership(self):
        from overte_phone_avatar_people_measurements import wearable
        b,id,url=self.original();b.state['avatarEntities']['entities'][0]['originalObject']=False
        actual=b.reader().read(RUN)
        with self.assertRaises(NativeUIError):wearable(RUN,actual['source'],dict(wearable={url}),{})
    def test_orphan_queries_cannot_be_dropped_or_replace_absence_with_empty_success(self):
        b,id,url=self.original();r=b.reader();r.read(RUN)
        b.state['avatarEntities'].update(entities=[],absentIds=[],advertisedIds=[],queriedIds=[],rememberedIds=[],retainedIds=[])
        with self.assertRaises(NativeUIError):r.read(RUN)
        b,id,url=self.original();b.state['avatarEntityOrigins']['events']=[];r=b.reader();r.read(RUN)
        b.state['avatarEntities'].update(entities=[],absentIds=[],advertisedIds=[],queriedIds=[],rememberedIds=[],retainedIds=[])
        with self.assertRaises(NativeUIError):r.read(RUN)
    def test_resume_restores_original_queries_without_retiming_or_replay(self):
        b,id,url=self.original();first=b.reader().read(RUN);resumed=b.reader();resumed.restore([first])
        next=resumed.read(RUN);self.assertGreater(next['sequence'],first['sequence']);self.assertEqual(first['capturedEpochMs'],resumed.last['capturedEpochMs']-1)
        for change in (lambda v:v.update(processId=32),lambda v:v['source']['avatarEntities'].update(rememberedIds=[])):
            wrong=deepcopy(first);change(wrong)
            with self.subTest(change=change),self.assertRaises(NativeUIError):b.reader().restore([wrong])


class AvatarPeopleProbeGrammarTests(unittest.TestCase):
    def test_original_probe_closed_grammar_rejects_setters_extra_fields_and_invalid_inputs(self):
        root=Path(__file__).resolve().parents[3]
        source=(root/'tests/device/probe/overte_e2e_probe.js').read_text()
        start=source.index('    var lastPhoneAvatarPeopleRequest=')
        end=source.index('    function validPhoneScriptFileRequest(',start)
        code="""function objectKeysMatch(value,keys) { return JSON.stringify(Object.keys(value).sort())===JSON.stringify(keys.slice().sort()); }
function phoneFileInteger(v,lo,hi) { return typeof v==='number' && Number.isInteger(v) && v>=lo && v<=hi; }
"""+source[start:end]+"""
const assert=require('assert');const request={schemaVersion:1,commandId:'a'.repeat(32),action:'activate',instance:'b'.repeat(32),generation:'c'.repeat(32),sequence:1,observedElapsedMs:0,controlId:'people.ConnectionAccept',controlToken:'d'.repeat(32)};
assert(validPhoneAvatarPeopleRequest(request));
assert(validPhoneAvatarPeopleRequest({...request,action:'replace',controlId:'avatar.dialog.input',text:'https://controlled.invalid/owned/avatar-a.fst'}));
assert(validPhoneAvatarPeopleRequest({...request,action:'set-value',controlId:'avatar.scale',value:15}));
for (const bad of [{...request,expectedConnection:'connected'},{...request,action:'set-state'},{...request,action:'replace',text:'credential',controlId:'avatar.dialog.input'},{...request,action:'set-value',value:41,controlId:'avatar.scale'},{...request,action:'set-value',value:15},{...request,action:'scroll',direction:'down'},{...request,action:'replace',text:'https://user:password@controlled.invalid/a',controlId:'avatar.dialog.input'},{...request,controlId:'people.remove.'}]) { assert(!validPhoneAvatarPeopleRequest(bad),JSON.stringify(bad)); }
"""
        subprocess.run(['node','-e',code],check=True,capture_output=True,text=True,timeout=10)
    def test_actor_readonly_source_factory_cannot_issue_primary_ui_input(self):
        from appium_adapter import readonly_feature_command
        value=dict(schemaVersion=1,commandId='a'*32,action='phone-avatar-people-observe',runId=RUN)
        readonly_feature_command(value)
        value=dict(schemaVersion=1,commandId='a'*32,action='phone-avatar-people-ui',request=dict(schemaVersion=1,commandId='a'*32,action='observe'))
        readonly_feature_command(value)
        value['request']['action']='activate'
        with self.assertRaises((RuntimeError,ValueError)):readonly_feature_command(value)

if __name__=='__main__':unittest.main()
