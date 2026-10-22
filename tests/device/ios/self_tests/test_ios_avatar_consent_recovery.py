"""Exact actor invitation and no-repeat ordinary consent continuation."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
import uuid
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.avatar_consent import IOSAvatarConsent
from ios.adapters.avatar_input_reads import IOSAvatarInputReads
from ios.adapters import avatar_inputs,normal_input
from ios.self_tests import test_ios_avatar_consent as fixture
from ios.self_tests.test_ios_avatar_inputs import packet


class AvatarConsentRecoveryTests(unittest.TestCase):
    def setup_case(self,lost_at):
        f=fixture.AvatarConsentTests();f.setUp();self.addCleanup(f.doCleanups)
        held=f.lock.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        self.f=f;self.events=[];self.edits=[];self.queries=[];post=f.fixture.widget.post
        def transport(request,timeout):
            query=json.loads(request.data);event=None
            if query['operation']=='edit':
                row=next(row for row in f.fixture.widget.rows() if row['token']==query['input']['fieldToken'])
                event=dict(sequence=len(self.events)+1,eventId=str(uuid.uuid4()),inputId=str(uuid.uuid4()),kind='received',
                    clock=dict(epochMs=f.fixture.now(),monotonicMs=round(f.fixture.clock*1000)),
                    details=dict(outerCommandId=query['commandId'],command=deepcopy(query['input']),controlId=row['id'],
                        root={key:row[key] for key in ('rootId','qmlSource')}))
                self.events.append(event);self.edits.append(deepcopy(query['input']))
            result=post(request,timeout)
            if event is not None:
                self.events.append(dict(sequence=len(self.events)+1,eventId=str(uuid.uuid4()),inputId=event['inputId'],kind='returned',
                    clock=dict(epochMs=f.fixture.now(),monotonicMs=round(f.fixture.clock*1000)),details=deepcopy(f.fixture.widget.receipt)))
                if len(self.edits)==lost_at:raise NativeUIError('Synthetic transport loss after actual actor normal event returned')
            return result
        boundary=patch.object(normal_input,'urlopen',transport);boundary.start();self.addCleanup(boundary.stop);f.source=f.sources()
        def send(query):
            self.queries.append(deepcopy(query));f.fixture.tick();self.current=packet(42,f.fixture.now())
            self.current.update(requestId=query['commandId'],runId=f.fixture.run,sequence=len(self.queries))
            for key in ('clockBefore','clockAfter'):self.current[key]['monotonicMs']=round(f.fixture.clock*1000)
            self.current['source']['events']=deepcopy(self.events)
        self.reader=avatar_inputs.IOSAvatarInputs(send,lambda:json.dumps(self.current),f.fixture.now,lambda:True,42,
            monotonic=lambda:f.fixture.clock,sleep=f.fixture.sleep);self.call=f.query()
    def owner(self):
        f=self.f;base=f.owner();reads=IOSAvatarInputReads(PrivateFeatureState(f.path/'ios-avatar-actor-input-reads.json'),f.root,
            base.sources.binding,base.sources.run,'actor',f.lock,lambda:True,self.reader,monotonic=lambda:f.fixture.clock)
        return IOSAvatarConsent(base.store,base.sources,base.inputs,f.sdk,base.peer,base.username,base.origin,input_reads=reads)
    def test_lost_accept_terminal_close_and_connections_fetch_continue_with_the_same_actual_invitation(self):
        for position in range(1,4):
            with self.subTest(position=position):
                self.setup_case(position);owner=self.owner()
                with self.assertRaises(NativeUIError):owner.act(self.call)
                clock=deepcopy(owner.state['calls'][-1]['operationClock']);prefix=deepcopy(self.edits)
                restored=self.owner();self.assertEqual({'performed':True},restored.act(self.call))
                self.assertEqual(prefix,self.edits[:position]);self.assertEqual(3,len(self.edits));self.assertEqual(1,len(self.queries))
                self.assertEqual(clock,restored.state['calls'][-1]['operationClock']);self.assertEqual(fixture.REQUEST,restored.state['calls'][-1]['invitation']['requestId'])
                self.assertEqual('idle',self.f.fixture.widget.phase);self.assertEqual('connectionsTab',self.f.fixture.widget.tab)
    def test_different_terminal_UUID_cannot_be_closed_after_recovering_an_earlier_accept(self):
        self.setup_case(1);owner=self.owner()
        with self.assertRaises(NativeUIError):owner.act(self.call)
        self.f.fixture.widget.request_id='00000000-0000-4000-8000-000000000008';before=deepcopy(self.edits)
        with self.assertRaises(NativeUIError):self.owner().act(self.call)
        self.assertEqual(before,self.edits);self.assertEqual('connection',self.f.fixture.widget.dialog)
    def test_original_deadline_is_not_renewed_after_actor_reconstruction(self):
        self.setup_case(1);owner=self.owner()
        with self.assertRaises(NativeUIError):owner.act(self.call)
        self.f.fixture.clock+=26;before=deepcopy(self.edits)
        with self.assertRaises(NativeUIError):self.owner().act(self.call)
        self.assertEqual(before,self.edits);self.assertEqual([],self.queries)
    def test_slow_actor_UIKit_intent_candidate_or_element_lookup_cannot_open_after_deadline(self):
        for fault in ('intent-save','candidate','lookup'):
            with self.subTest(fault=fault):
                self.setup_case(100);self.f.fixture.widget.shown=False;owner=self.owner();sdk=self.f.sdk
                check=sdk.check_continuity;save=owner.save;call=sdk.call
                def saved():
                    save()
                    if fault=='intent-save' and owner.state['calls'][-1]['phase']=='issuing':self.f.fixture.clock+=26
                def candidate():
                    if fault=='candidate':self.f.fixture.clock+=26
                    return check()
                def transport(method,path,body=None):
                    value=call(method,path,body)
                    if fault=='lookup' and path.endswith('/elements'):self.f.fixture.clock+=26
                    return value
                owner.save=saved;sdk.check_continuity=candidate;sdk.call=transport
                with self.assertRaises(NativeUIError):owner.act(self.call)
                self.assertIsNot(owner.sdk,sdk);self.assertIs(sdk.check_continuity,candidate)
                self.assertEqual([],sdk.inputs);self.assertEqual([],self.edits)
                self.assertEqual('issuing',owner.state['calls'][-1]['phase'])
    def test_lost_actor_durable_input_finish_is_adopted_without_new_consent_or_input(self):
        self.setup_case(100);owner=self.owner();finish=owner.inputs.finish
        def lost():
            finish();raise OSError('Lost return after actual actor input finish')
        owner.inputs.finish=lost
        with self.assertRaises(OSError):owner.act(self.call)
        self.assertEqual('acknowledged',self.owner().inputs.state['phase']);prefix=deepcopy(self.edits)
        restored=self.owner();clock=deepcopy(restored.state['calls'][-1]['operationClock'])
        with patch.object(restored.inputs,'finish',side_effect=AssertionError('Original actor finish is already saved')):
            self.assertEqual({'performed':True},restored.act(self.call))
        self.assertEqual(prefix,self.edits);self.assertEqual([],self.queries)
        self.assertEqual(clock,restored.state['calls'][-1]['operationClock'])


if __name__=='__main__':unittest.main()
