"""Real private consent/input/source owners at a synthetic independent SDK."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import VERSION
from ios.adapters import normal_input,avatar_controls
from ios.adapters.avatar_consent import IOSAvatarConsent
from ios.adapters.avatar_input_owner import AvatarInputOwner
from ios.adapters.avatar_sources import IOSAvatarSources
from ios.self_tests.test_ios_avatar_sources import SourcesFixture
from ios.self_tests.test_ios_avatar_controls import Boundary
from ios.self_tests.test_ios_avatar_actions import UIKit
from ios.self_tests.test_ios_avatar_input_owner import BINDING
from self_tests.test_native_account_observation import account as account_packet

PEER='00000000-0000-4000-8000-000000000002'
USERNAME='e2e-'+'e'*32
ORIGIN='https://controlled.invalid'
REQUEST='00000000-0000-4000-8000-000000000009'


class ConsentWidget(Boundary):
    def __init__(self,fixture):
        super().__init__();self.fixture=fixture;self.screen='people';self.dialog='connection';self.phase='incoming';self.tab='nearbyTab'
        self.actual_peer=PEER
        self.request_id=REQUEST
    def observed(self):
        self.fixture.tick();self.clock=self.fixture.clock;value=super().observed()
        value.update(sampleEpochMs=self.fixture.now(),elapsedMs=round(self.fixture.clock*1000));return value
    def rows(self):
        rows=super().rows()
        if self.screen=='people':
            page=next(row for row in rows if row['id']=='people.page')
            page['activeTab']=self.tab;page['connectionState'].update(peer=self.actual_peer,requestId=self.request_id)
            def add(identifier):rows.append(dict(id=identifier,token=str(uuid.uuid5(uuid.NAMESPACE_URL,identifier)),enabled=True,
                focused=False,inputReady=True,rootId=self.root(),qmlSource='file:///app.bundle/qml/hifi/Pal.qml'))
            if self.phase=='incoming':add('people.accept');add('people.decline')
            if self.dialog=='none':add('people.nearby');add('people.connections')
        return rows
    def post(self,request,timeout):
        payload=json.loads(request.data);identifier=None
        if payload['operation']=='edit':
            rows=[row for row in self.rows() if row['token']==payload['input']['fieldToken']]
            if rows:identifier=rows[0]['id']
        result=super().post(request,timeout)
        if identifier=='people.accept':self.phase='success'
        elif identifier=='people.decline':self.phase='declined'
        elif identifier=='people.nearby':self.tab='nearbyTab'
        elif identifier=='people.connections':self.tab='connectionsTab'
        if payload['operation']=='edit':self.receipt['status']['sampleEpochMs']=self.fixture.now()
        return result


class AvatarConsentTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.path=Path(temporary.name);self.path.chmod(0o700);self.root=self.path/'originals';self.root.mkdir(mode=0o700)
        self.fixture=SourcesFixture();self.fixture.widget=ConsentWidget(self.fixture);self.username=USERNAME
        original=self.fixture.core.send
        def native_send(query):
            original(query);account=account_packet();account.update(loggedIn=True,principalSha256=hashlib.sha256(self.username.encode()).hexdigest())
            account['observation'].update(capturedEpochMs=self.fixture.now(),tokenPresent=True,tokenValid=True,
                endpointPresent=True,endpointSha256=hashlib.sha256(ORIGIN.encode()).hexdigest())
            self.fixture.core.sample['account']=account
        self.fixture.core.send=native_send
        self.fixture.mutate=self.mutate
        native=normal_input.NativeInput(self.fixture.widget,'owned-session',self.fixture.widget.target,self.fixture.widget.process,
            native_epoch_ms=self.fixture.now,monotonic=lambda:self.fixture.clock,sleep=self.fixture.sleep)
        self.readers=self.fixture.readers();self.readers['ui']=avatar_controls.IOSAvatarIO(native)
        self.lock=ScriptSourceLock(self.path/'script-feature-sources.lock');self.sdk=UIKit(self.fixture);self.source=None
    def mutate(self,name,value):
        if name=='people':
            widget=self.fixture.widget;value['source']['tabletShown']=widget.shown
            root=value['source']['roots'][0];root.update(rootId=widget.root(),qmlSource='file:///app.bundle/qml/hifi/Pal.qml',
                visible=widget.screen=='people',active=widget.shown and widget.screen=='people',activeTab=widget.tab)
            root['connectionState'].update(phase=widget.phase,peer=widget.actual_peer,requestId=widget.request_id)
            root['panels']['connectionPrompt']=widget.dialog=='connection'
    def sources(self):return IOSAvatarSources(PrivateFeatureState(self.path/'ios-avatar-actor-sources.json'),self.root,BINDING,
        self.fixture.run,'actor',self.lock,lambda:True,self.fixture.phase,readers=self.readers,
        monotonic=lambda:self.fixture.clock,epoch_ms=self.fixture.host)
    def owner(self):
        inputs=AvatarInputOwner(PrivateFeatureState(self.path/'ios-avatar-actor-inputs.json'),self.lock,BINDING,
            self.fixture.run,'actor',self.fixture.phase.fixture_url,lambda:True)
        return IOSAvatarConsent(PrivateFeatureState(self.path/'ios-avatar-actor-consent.json'),self.source,inputs,self.sdk,PEER,USERNAME,ORIGIN)
    def query(self,verb='peer-accept'):
        ticket='a'*32;self.fixture.journal.activate(self.fixture.run,ticket,verb,{})
        return dict(contractVersion=VERSION,runId=self.fixture.run,ticket=ticket,fixtureUrl=self.fixture.phase.fixture_url,verb=verb,inputs={})

    def test_real_normal_accept_or_decline_owned_once_then_terminal_close_and_real_tab_navigation(self):
        for verb in ('peer-accept','peer-reject'):
            with self.subTest(verb=verb):
                # Separate private owner namespaces and SDK boundary per case.
                if verb=='peer-reject':self.tearDown();self.setUp()
                with self.lock.held(),patch.object(normal_input,'urlopen',self.fixture.widget.post):
                    self.source=self.sources();owner=self.owner();query=self.query(verb)
                    self.assertEqual({'performed':True},owner.act(query));count=len(self.fixture.widget.requests)
                    self.assertEqual({'performed':True},self.owner().act(query));self.assertEqual(count,len(self.fixture.widget.requests))
                    call=owner.state['calls'][-1];self.assertEqual(REQUEST,call['invitation']['requestId'])
                    self.assertEqual('acknowledged',call['phase']);self.assertEqual('idle',self.fixture.widget.phase)
                    self.assertEqual('connectionsTab',self.fixture.widget.tab)
                    self.assertTrue(all(event['phase']=='observed' for event in owner.inputs.state['calls'][-1]['events']))

    def test_lost_real_event_result_keeps_issued_command_and_never_repeats_consent(self):
        with self.lock.held(),patch.object(normal_input,'urlopen',self.fixture.widget.post):
            self.source=self.sources();owner=self.owner();query=self.query();self.fixture.widget.lost=True
            with self.assertRaises(NativeUIError):owner.act(query)
            count=len(self.fixture.widget.requests);rebuilt=self.owner()
            with self.assertRaises(NativeUIError):rebuilt.act(query)
            self.assertEqual(count,len(self.fixture.widget.requests));event=rebuilt.inputs.state['calls'][-1]['events'][-1]
            self.assertEqual('issued',event['phase']);self.assertIsNone(event['delivery'])

    def test_foreign_actual_account_or_peer_is_refused_before_accept(self):
        for fault in ('account','peer'):
            with self.subTest(fault=fault):
                if fault=='peer':self.tearDown();self.setUp()
                if fault=='account':self.username='e2e-'+'f'*32
                else:self.fixture.widget.actual_peer='00000000-0000-4000-8000-000000000003'
                with self.lock.held(),patch.object(normal_input,'urlopen',self.fixture.widget.post):
                    self.source=self.sources();owner=self.owner();query=self.query()
                    with self.assertRaises(NativeUIError):owner.act(query)
                    self.assertFalse(any(row['operation']=='edit' for row in self.fixture.widget.requests))

    def test_old_original_invitation_cannot_be_relabelled_as_a_new_phase_consent(self):
        with self.lock.held(),patch.object(normal_input,'urlopen',self.fixture.widget.post):
            self.source=self.sources();owner=self.owner();query=self.query();owner.act(query)
            self.fixture.widget.phase='incoming';self.fixture.widget.dialog='connection'
            next_query=query|dict(ticket='b'*32)
            self.fixture.journal.activate(self.fixture.run,next_query['ticket'],next_query['verb'],{})
            count=sum(row['operation']=='edit' for row in self.fixture.widget.requests)
            with self.assertRaises(NativeUIError):owner.act(next_query)
            self.assertEqual(count,sum(row['operation']=='edit' for row in self.fixture.widget.requests))

    def test_changed_same_peer_invitation_after_durable_admission_never_sends_response(self):
        with self.lock.held(),patch.object(normal_input,'urlopen',self.fixture.widget.post):
            self.source=self.sources();owner=self.owner();query=self.query();save=owner.save
            def changed():
                save()
                if owner.state['calls'] and owner.state['calls'][-1]['invitation'] is not None:
                    self.fixture.widget.request_id='00000000-0000-4000-8000-000000000010'
            owner.save=changed
            with self.assertRaises(NativeUIError):owner.act(query)
            self.assertEqual(REQUEST,owner.state['calls'][-1]['invitation']['requestId'])
            self.assertFalse(any(row['operation']=='edit' for row in self.fixture.widget.requests))

    def test_reconstruction_compares_original_accept_reference_with_retained_invitation(self):
        with self.lock.held(),patch.object(normal_input,'urlopen',self.fixture.widget.post):
            self.source=self.sources();owner=self.owner();owner.act(self.query())
            state=deepcopy(owner.inputs.state)
            event=next(event for event in state['calls'][0]['events'] if event['intent']['controlId']=='people.accept')
            page=next(row for row in event['intent']['reference']['controls'] if row['id']=='people.page')
            page['connectionState']['requestId']='00000000-0000-4000-8000-000000000010'
            owner.inputs.store.write(owner.inputs.envelope(state),owner.inputs.previous)
            with self.assertRaises(NativeUIError):self.owner()


if __name__=='__main__':unittest.main()
