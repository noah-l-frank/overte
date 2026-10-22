"""Actual owners/archive/normal transport; explicit synthetic Qt/model boundary."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI,NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import VERSION
from ios.adapters import avatar_controls,normal_input
from ios.adapters.avatar_actions import IOSAvatarActions
from ios.adapters.avatar_input_owner import AvatarInputOwner
from ios.adapters.avatar_sources import IOSAvatarSources
from ios.self_tests.test_ios_avatar_controls import Boundary
from ios.self_tests.test_ios_avatar_sources import SourcesFixture
from ios.self_tests.test_ios_avatar_input_owner import BINDING
from ios.self_tests import test_ios_avatar_entities as entity_tests
from ios.self_tests import test_ios_avatar_renderers as renderer_tests
from ios.self_tests import test_ios_avatar_state as state_tests


class Widget(Boundary):
    def __init__(self,fixture):
        super().__init__();self.fixture=fixture;self.avatar_url=fixture.prototypes['state']['source']['requestedUrl'];self.saved=None
        self.wearable_id=None;self.wearable_url=None;self.failed_geometry=False
        self.entity_revision=1
    def observed(self):
        self.fixture.tick();self.clock=self.fixture.clock
        value=super().observed();value.update(sampleEpochMs=self.fixture.now(),elapsedMs=round(self.fixture.clock*1000));return value
    def rows(self):
        rows=super().rows()
        def add(identifier,**fields):
            rows.append(dict(id=identifier,token=str(uuid.uuid5(uuid.NAMESPACE_URL,identifier+str(self.wearable_id))),enabled=True,focused=False,
                inputReady=True,rootId=self.root(),qmlSource='file:///app.bundle/qml/hifi/AvatarApp.qml',**fields))
        if self.screen=='avatar' and self.dialog=='none':add('avatar.wearables-open')
        if self.screen=='avatar' and self.dialog=='wearables':
            add('avatar.wearable-add');add('avatar.wearable-choice',choices=[self.wearable_id] if self.wearable_id else [],index=0 if self.wearable_id else -1)
            if self.wearable_id:add('avatar.wearable-remove',selectedId=self.wearable_id)
            add('avatar.wearables.confirm');add('avatar.wearables.cancel')
        if self.screen=='avatar' and self.dialog=='none' and self.name:
            rows.append(dict(id='avatar.favorite.'+hashlib.sha256(self.name.encode()).hexdigest()[:32],name=self.name,
                token=str(uuid.uuid5(uuid.NAMESPACE_URL,self.name)),enabled=True,focused=False,inputReady=True,
                rootId=self.root(),qmlSource='file:///app.bundle/qml/hifi/AvatarApp.qml'))
        return rows
    def post(self,request,timeout):
        payload=json.loads(request.data);identifier=None;before=self.avatar_url;title=self.popup_title
        if payload['operation']=='edit':
            rows=[row for row in self.rows() if row['token']==payload['input']['fieldToken']]
            if rows:identifier=rows[0]['id']
        result=super().post(request,timeout)
        if identifier=='avatar.manage':self.manage=not self.manage
        elif identifier and identifier.startswith('avatar.favorite.') and identifier not in ('avatar.favorite.confirm','avatar.favorite.cancel'):
            self.dialog='popup';self.popup_title=('Delete Favorite: ' if self.manage else 'Load Favorite: ')+self.name
        elif identifier=='avatar.favorite.confirm':self.saved=dict(avatarUrl=self.avatar_url,avatarScale=self.scale,avatarEntites=[])
        elif identifier=='avatar.popup.confirm' and title.startswith('Load Favorite: '):
            self.avatar_url=self.saved['avatarUrl'];self.scale=self.saved['avatarScale']
            if self.wearable_id:self.entity_revision+=1;self.wearable_id=None
        elif identifier=='avatar.popup.confirm' and title.startswith('Delete Favorite: '):self.avatar_url=before;self.name=''
        elif identifier=='avatar.wearables-open':self.dialog='wearables'
        elif identifier=='avatar.wearable-add':self.dialog='popup';self.popup_title='Specify Wearable URL';self.draft=''
        elif identifier=='avatar.popup.confirm' and title=='Specify Wearable URL':
            self.avatar_url=before;self.dialog='wearables';self.wearable_id=str(uuid.uuid4());self.wearable_url=self.draft
            self.entity_revision+=1
            source=self.fixture.prototypes['entities']['source'];event=deepcopy(source['events'][0]);last=source['events'][-1]
            event.update(sequence=len(source['events'])+1,eventId=uuid.uuid4().hex)
            event['clock'].update(epochMs=self.fixture.now(),monotonicMs=round(self.fixture.clock*1000))
            event['caller'].update(sequence=last['caller']['sequence']+1,invokedEpochMs=self.fixture.now())
            event['entity'].update(entityId=self.wearable_id,modelUrl=self.wearable_url,lastEditedEpochUs=str(self.fixture.now()*1000))
            source['events'].append(event)
        elif identifier=='avatar.wearables.confirm':self.dialog='none'
        elif identifier=='avatar.wearable-remove':self.wearable_id=None;self.entity_revision+=1
        if self.avatar_url!=before:
            native=self.fixture.prototypes['state'];generation=native['source']['modelHistory']['currentGeneration']+1
            state_tests.requested(native,generation,self.avatar_url,generation)
            state_tests.event(native,'finished',generation,self.avatar_url,assignment=generation,resource=self.avatar_url,
                success=not self.avatar_url.endswith('/missing.fst'))
            for event in native['source']['modelHistory']['events'][-3:]:
                event.update(epochMs=self.fixture.now(),monotonicMs=round(self.fixture.clock*1000))
        if payload['operation']=='edit':self.receipt['status']['sampleEpochMs']=self.fixture.now()
        return result


class UIKit(NativeUI):
    def __init__(self,fixture):
        self.fixture=fixture;self.inputs=[];self.selected=None
        super().__init__(self,'owned-session',lambda:True,monotonic=lambda:fixture.clock,sleep=fixture.sleep)
    def call(self,method,path,body=None):
        if path.endswith('/elements'):
            self.selected=body['value'];return [{'element-6066-11e4-a52e-4f735466cecf':'original-tablet-button'}]
        if path.endswith(('/displayed','/enabled')):return True
        if path.endswith('/click'):
            self.inputs.append(self.selected)
            if self.selected=='OverteTabletOpen':self.fixture.widget.shown=True
            elif self.selected=='OverteTabletClose':self.fixture.widget.shown=False
            else:raise AssertionError('Unexpected UIKit control')
            return None
        raise AssertionError('Unexpected UIKit transport')


class AvatarActionTests(unittest.TestCase):
    def test_reviewed_code_pins_match_candidate_files_and_never_use_native_code_to_build_expected(self):
        from ios.adapters.avatar_code import pins,validate
        expected=pins();root=Path(__file__).resolve().parents[4]
        for suffix,identity in expected.items():
            raw=(root/'scripts'/suffix[1:]).read_bytes().decode('utf-8').encode('utf-16le')
            self.assertEqual(dict(codeUnits=len(raw)//2,sha256=hashlib.sha256(raw).hexdigest()),identity)
        with self.assertRaises(NativeUIError):validate(dict(avatarCodePinsVersion=True,encoding='utf-16le-code-units',sources={}))

    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.path=Path(temporary.name);os.chmod(self.path,0o700);self.root=self.path/'originals';self.root.mkdir(mode=0o700)
        self.fixture=SourcesFixture();self.fixture.widget=Widget(self.fixture);self.fixture.widget.shown=False
        self.fixture.prototypes['scripts']=entity_tests.packet()[3]
        self.fixture.prototypes['renderers']['source']['avatars'][0].update(requestedUrl=self.fixture.widget.avatar_url,resourceUrl=self.fixture.widget.avatar_url)
        self.fixture.mutate=self.mutate
        self.native=normal_input.NativeInput(self.fixture.widget,'owned-session',self.fixture.widget.target,self.fixture.widget.process,
            native_epoch_ms=self.fixture.now,monotonic=lambda:self.fixture.clock,sleep=self.fixture.sleep)
        readers=self.fixture.readers();readers['ui']=avatar_controls.IOSAvatarIO(self.native)
        self.lock=ScriptSourceLock(self.path/'script-feature-sources.lock');self.sdk=UIKit(self.fixture)
        self.source=None
        self.readers=readers
    def mutate(self,name,value):
        widget=self.fixture.widget
        if name=='state':
            source=value['source'];source.update(requestedUrl=widget.avatar_url,resourceUrl=widget.avatar_url,targetScale=widget.scale,modelScale=widget.scale)
            if widget.avatar_url.endswith('/missing.fst'):source['resourceUrl']=source['defaultResourceUrl']
            entries={} if not widget.name else {widget.name:deepcopy(widget.saved)}
            source['bookmarks']['entries']=entries
            raw=json.dumps(entries,sort_keys=True,separators=(',',':')).encode()
            source['bookmarkFile'].update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),contentBase64=base64.b64encode(raw).decode())
        elif name=='renderers':
            value['source']['avatars'][0].update(requestedUrl=widget.avatar_url,resourceUrl=widget.avatar_url,targetScale=widget.scale,modelScale=widget.scale)
            if widget.avatar_url.endswith('/missing.fst'):value['source']['avatars'][0]['resourceUrl']=self.fixture.prototypes['state']['source']['defaultResourceUrl']
            if widget.wearable_id:
                renderer_tests.attach(value)
                row=value['source']['avatarEntities'][-1];row.update(id=widget.wearable_id,modelUrl=widget.wearable_url,resourceUrl=widget.wearable_url,
                    geometryLoaded=not widget.failed_geometry,addedToScene=not widget.failed_geometry,loadFailed=widget.failed_geometry)
                value['source']['tree']['entities'][-1]['id']=widget.wearable_id
            value['source']['tree'].update(revisionBefore=widget.entity_revision,revisionAfter=widget.entity_revision)
        elif name=='people':
            value['source']['tabletShown']=widget.shown
            for root in value['source']['roots']:root.update(visible=widget.screen=='people',active=widget.shown and widget.screen=='people')
    def make_sources(self):
        return IOSAvatarSources(PrivateFeatureState(self.path/'ios-avatar-primary-sources.json'),self.root,BINDING,
            self.fixture.run,'primary',self.lock,lambda:True,self.fixture.phase,readers=self.readers,
            monotonic=lambda:self.fixture.clock,epoch_ms=self.fixture.host)
    def owner(self):
        inputs=AvatarInputOwner(PrivateFeatureState(self.path/'ios-avatar-primary-inputs.json'),self.lock,BINDING,
            self.fixture.run,'primary',self.fixture.phase.fixture_url,lambda:True)
        return IOSAvatarActions(PrivateFeatureState(self.path/'ios-avatar-primary-actions.json'),self.source,inputs,self.sdk,
            dict(sessionId='00000000-0000-4000-8000-000000000002',username='e2e-'+'c'*32),entity_tests.EXPECTED)
    def action(self,verb,inputs,ticket):
        self.fixture.journal.activate(self.fixture.run,ticket,verb,inputs)
        return dict(contractVersion=VERSION,runId=self.fixture.run,ticket=ticket,fixtureUrl=self.fixture.phase.fixture_url,verb=verb,inputs=inputs)

    def test_original_normal_url_favorite_scale_recovery_delete_and_idempotent_no_resend(self):
        with self.lock.held(),patch.object(normal_input,'urlopen',self.fixture.widget.post):
            self.source=self.make_sources();owner=self.owner();owner.prepare();original=self.fixture.widget.avatar_url
            cases=[('avatar-url',dict(resource='avatar-a.fst')),('avatar-bookmark-save',dict(name='e2e-'+self.fixture.run)),
                ('avatar-scale',dict(value=1.5)),('wearable-add',dict(resource='gltf-bundle/main.gltf')),('avatar-bookmark-choose',dict(name='e2e-'+self.fixture.run)),
                ('avatar-restore',{}),('avatar-bookmark-delete',dict(name='e2e-'+self.fixture.run))]
            cases.insert(4,('avatar-url',dict(resource='missing.fst')))
            for index,(verb,inputs) in enumerate(cases,1):
                query=self.action(verb,inputs,f'{index:032x}');self.assertEqual({'performed':True},owner.act(query))
                delivered=len(self.fixture.widget.requests);self.assertEqual({'performed':True},owner.act(query))
                self.assertEqual(delivered,len(self.fixture.widget.requests))
            self.assertEqual(original,self.fixture.widget.avatar_url);self.assertEqual('',self.fixture.widget.name)
            self.assertEqual(1.,self.fixture.widget.scale);self.assertEqual(['OverteTabletOpen'],self.sdk.inputs)
            restored=self.owner();self.assertEqual(8,len(restored.state['calls']));self.assertEqual(1,len(restored.state['owned']))
            self.assertTrue(all(row['phase']=='acknowledged' for row in restored.state['calls']))
            self.assertTrue(all(row['phase']=='acknowledged' for row in restored.inputs.state['calls']))

    def test_lost_native_event_return_retains_exact_recipe_and_blocks_whole_action_replay(self):
        with self.lock.held(),patch.object(normal_input,'urlopen',self.fixture.widget.post):
            self.source=self.make_sources();owner=self.owner();owner.prepare();self.fixture.widget.lost=True
            query=self.action('avatar-url',dict(resource='avatar-a.fst'),'2'*32)
            with self.assertRaises(NativeUIError):owner.act(query)
            requests=len(self.fixture.widget.requests);restored=self.owner()
            with self.assertRaises(NativeUIError):restored.act(query)
            self.assertEqual(requests,len(self.fixture.widget.requests))
            self.assertEqual('acting',restored.state['calls'][-1]['phase'])
            event=restored.inputs.state['calls'][-1]['events'][-1]
            self.assertEqual('issued',event['phase']);self.assertIsNone(event['delivery'])

    def test_failed_geometry_retains_actual_returned_UUID_before_failure_and_never_recreates_it(self):
        with self.lock.held(),patch.object(normal_input,'urlopen',self.fixture.widget.post):
            self.source=self.make_sources();owner=self.owner();owner.prepare();self.fixture.widget.failed_geometry=True
            query=self.action('wearable-add',dict(resource='gltf-bundle/main.gltf'),'2'*32)
            with self.assertRaises(NativeUIError):owner.act(query)
            original_id=self.fixture.widget.wearable_id;self.assertIsNotNone(original_id)
            restored=self.owner();self.assertEqual(original_id,restored.state['owned'][0]['id'])
            count=sum(row['operation']=='edit' for row in self.fixture.widget.requests)
            with self.assertRaises(NativeUIError):restored.act(query)
            self.assertEqual(count,sum(row['operation']=='edit' for row in self.fixture.widget.requests));self.assertEqual(original_id,self.fixture.widget.wearable_id)

    def test_unowned_original_entity_change_is_refused_before_recipe_input_and_never_excluded_as_owned(self):
        renderer_tests.attach(self.fixture.prototypes['renderers'])
        with self.lock.held(),patch.object(normal_input,'urlopen',self.fixture.widget.post):
            self.source=self.make_sources();owner=self.owner();owner.prepare()
            self.fixture.prototypes['renderers']['source']['tree']['entities'][0]['semanticSha256']='0'*64
            self.fixture.widget.entity_revision+=1
            query=self.action('avatar-scale',dict(value=1.5),'2'*32);count=len(self.fixture.widget.requests)
            with self.assertRaises(NativeUIError):owner.act(query)
            self.assertEqual([],owner.state['owned'])
            actual=[row for row in self.fixture.widget.requests[count:] if row['operation']=='edit'];self.assertEqual([],actual)


if __name__=='__main__':unittest.main()
