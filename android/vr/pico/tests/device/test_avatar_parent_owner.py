"""Parent interruption fences over explicit SDK/Qt/Model DTO actors.

The separate live native case owns the original QML/persistence/callback join.
These counters exercise common arguments, durable files and no-resend behavior.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import hashlib
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(HERE)]
import test_avatar_favorites_owner as favorite_fixture
from adapters.pico4 import avatar_model_connections as callbacks
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.history import unpack,pack
from feature_journeys.scenarios import VERSION


class AvatarParentOwnerTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(os.environ,dict(OVERTE_PICO_AVATAR_PARENT_SOURCE='1')))
        favorites=favorite_fixture.AvatarFavoritesTests(methodName='runTest');favorites.setUp();self.addCleanup(favorites.doCleanups)
        self.f=favorites.fixture;f=self.f;self.sequence=0;self.birth='9'*32;self.original_epoch=f.epoch
        def source():
            packet={}
            def send(request):
                self.sequence+=1
                row=dict(id='1'*32,urlSha256=hashlib.sha256(favorite_fixture.ORIGINAL.encode()).hexdigest(),
                    change=1,createdEpochMs=self.original_epoch,enteredEpochMs=self.original_epoch,returnedEpochMs=self.original_epoch,
                    ownerAlive=True,senderAlive=True,captureAlive=False,connected=True,disconnected=True,completed=True,
                    ownerThreadOnly=True,dispatches=1,active=0)
                # The one baseline actor capture is fixed across URL actions;
                # it is not an actual downloaded Model or native callback.
                packet.update(schemaVersion=1,requestId=request['commandId'],instance='c'*32,sequence=self.sequence,
                    processId=123,requestedEpochMs=f.epoch,capturedEpochMs=f.epoch,source=dict(picoAvatarModelConnectionsVersion=1,
                        instance=self.birth,avatarInstance=f.source['avatarLoads']['instance'],sessionId=f.source['sessionId'],
                        connections=dict(avatarModelConnectionsVersion=1,instance='b'*32,capturedEpochMs=f.epoch,rows=[row])))
            return callbacks.NativePicoAvatarModelConnections(send,lambda:json.dumps(packet),lambda:f.epoch,lambda:True,123,
                monotonic=lambda:f.clock,sleep=f.sleep)
        self.enterContext(patch.object(f.instance,'_avatar_model_connections_observer',side_effect=lambda _target:source()))
        with f.lock.held():f.instance._avatar_parent(f.target,favorite_fixture.RUN,source_lock=f.lock).prepare()
    def request(self):
        f=self.f;ticket=f.activate('avatar-url',dict(resource='avatar-a.fst'))
        return dict(contractVersion=VERSION,runId=favorite_fixture.RUN,verb='avatar-url',inputs=dict(resource='avatar-a.fst'),
            ticket=ticket,fixtureUrl=f.phase.fixture_url)
    def invoke(self,request):return self.f.instance.invoke(self.f.target,'feature.avatar-people.act',request)
    def test_lost_parent_result_after_durable_child_completion_never_resends(self):
        request=self.request();original=PrivateFeatureState.write
        def lost(store,value,previous):
            original(store,value,previous)
            if value.get('picoAvatarParentVersion')==1:
                state=unpack(value['payload'])[0]
                if state['calls'] and state['calls'][-1]['after'] is not None:raise OSError('Declared lost durable parent result')
        with patch.object(PrivateFeatureState,'write',lost),self.assertRaises(ValueError):self.invoke(request)
        count=len(self.f.native.inputs);self.assertGreater(count,0)
        with self.assertRaises(ValueError):self.invoke(request)
        self.assertEqual(count,len(self.f.native.inputs));self.assertTrue(self.f.instance._avatar_parent_owned(self.f.target))
    def test_lost_durable_parent_intent_remains_owned_before_any_normal_input(self):
        request=self.request();original=PrivateFeatureState.write
        def lost(store,value,previous):
            original(store,value,previous)
            if value.get('picoAvatarParentVersion')==1 and unpack(value['payload'])[0]['pending'] is not None:
                raise OSError('Declared lost durable parent intent')
        with patch.object(PrivateFeatureState,'write',lost),self.assertRaises(ValueError):self.invoke(request)
        self.assertFalse(self.f.native.inputs)
        with self.assertRaises(ValueError):self.invoke(request)
        self.assertFalse(self.f.native.inputs);self.assertTrue(self.f.instance._avatar_parent_owned(self.f.target))
    def test_foreign_phase_ticket_refuses_before_child_input(self):
        request=self.request();request['ticket']=uuid.uuid4().hex
        with self.assertRaises(ValueError):self.invoke(request)
        self.assertFalse(self.f.native.inputs)
    def test_replaced_callback_owner_is_not_adopted_from_old_parent_history(self):
        request=self.request();self.birth='8'*32
        with self.assertRaises(ValueError):self.invoke(request)
        self.assertFalse(self.f.native.inputs)
    def test_missing_full_state_and_final_retirement_never_produce_defaults(self):
        f=self.f;request=dict(contractVersion=VERSION,runId=favorite_fixture.RUN)
        for kind,fields in (('observe',dict(afterSequence=0)),('cleanup',{})):
            with self.assertRaises(ValueError):f.instance.invoke(f.target,'feature.avatar-people.'+kind,request|fields)
        self.assertFalse(any(cap.startswith('feature.avatar-people.') for cap in f.instance.capabilities(f.target)))
        self.assertFalse(f.native.inputs);self.assertTrue(f.instance._avatar_parent_owned(f.target))
    def test_original_preinput_child_frame_cannot_replace_settled_child_receipt(self):
        f=self.f;self.invoke(self.request())
        ticket=f.activate('avatar-bookmark-save',dict(name='e2e-'+favorite_fixture.RUN))
        self.invoke(dict(contractVersion=VERSION,runId=favorite_fixture.RUN,verb='avatar-bookmark-save',
            inputs=dict(name='e2e-'+favorite_fixture.RUN),ticket=ticket,fixtureUrl=f.phase.fixture_url))
        with f.lock.held():
            parent=f.instance._avatar_parent(f.target,favorite_fixture.RUN,source_lock=f.lock)
            _,favorites=parent.children();call=favorites.state['calls'][-1]
            original_before=favorites.state['frames'][call['before']-1]
            reference=favorites.archive.frame_reference(original_before)
            record=parent.store.read();state=unpack(record['payload'])[0]
            self.assertNotEqual(reference,state['calls'][-1]['child']['frame'])
            state['calls'][-1]['child']['frame']=reference;changed=dict(record,payload=pack([state]))
            parent.store.write(changed,record)
        count=len(f.native.inputs)
        def cold():
            with f.lock.held():return f.instance._avatar_parent(f.target,favorite_fixture.RUN,source_lock=f.lock)
        with self.assertRaises((ValueError,RuntimeError)):cold()
        self.assertEqual(count,len(f.native.inputs));self.assertTrue(f.instance._avatar_parent_owned(f.target))


if __name__=='__main__':unittest.main()
