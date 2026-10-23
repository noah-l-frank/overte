"""Actual private files/FDs and serialized AFC fence; native lease is modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.private_login_input import PrivateLoginInput,FILE
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.avatar_abort_credentials import AvatarAbortCredentials
from ios.adapters.private_login_transport import IOSPrivateLoginTransport
from ios.self_tests.test_ios_avatar_input_owner import BINDING,RUN
from self_tests.test_private_login_input import Boundary,INPUT

CHILD='d'*32


class AvatarAbortCredentialsTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.root.chmod(0o700)
        self.private=PrivateFeatureState(self.root/'ios-avatar-primary-private-login-input.json')
        native_root=self.root/'private-app-storage';native_root.mkdir(mode=0o700)
        self.native=Boundary(native_root,self.private);self.addCleanup(self.native.close)
        self.native.fault='drain-error'
        initial=PrivateLoginInput(self.native,self.private,BINDING,CHILD,component_only=False,monotonic=lambda:self.native.clock,sleep=self.native.sleep)
        with self.assertRaises(NativeUIError):initial.replace(deepcopy(INPUT))
        self.assertTrue(self.private.read()['transferPending']);self.assertIsNotNone(self.native.deferred);self.native.fault='';self.prior_drains=self.native.drains
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock')
        self.store=PrivateFeatureState(self.root/('ios-avatar-primary-'+RUN+'-abort-credentials.json'))
        def original(*,remote,limit):
            if remote.endswith('/'+FILE):return self.native.read()
            name=remote.rsplit('/',1)[-1];self.assertTrue(name.startswith('feature-login-input-'))
            return self.native.drain(name).decode()
        def execute(_session,operation,values):
            self.assertEqual('mobile: pullFile',operation)
            return base64.b64encode(self.native.drain(values['remotePath'].rsplit('/',1)[-1])).decode()
        self.observer=SimpleNamespace(guard=self.native.guard,process=dict(pid=42),remote='@app:documents/results/native.json',
            send=self.native.send,original=original,sleep=self.native.sleep,client=SimpleNamespace(execute=execute),session='actual-session')
        self.transport=IOSPrivateLoginTransport(self.observer)
    def owner(self):
        return AvatarAbortCredentials(self.store,self.private,self.transport,BINDING,RUN,CHILD,'primary',self.lock,lambda:True,
            epoch_ms=lambda:1700000000000+self.native.clock*1000,monotonic=lambda:self.native.clock)
    def retires(self):return len([row for row in self.native.commands if row['operation']=='retire'])

    def test_serialized_private_fence_and_two_actual_absences_precede_owner_retirement_without_text_artifacts(self):
        with self.lock.held():
            owner=self.owner();self.assertEqual(dict(performed=True),owner.cleanup());commands=deepcopy(self.native.commands)
            self.assertEqual(dict(performed=True),self.owner().cleanup());self.assertEqual(commands,self.native.commands)
            with patch.object(self.transport,'guard',side_effect=AssertionError('No SDK during historical private-file replay')):
                self.assertEqual(owner.state,AvatarAbortCredentials.archive(owner.previous,store=self.store,private_store=self.private,
                    binding=BINDING,run=RUN,child_run=CHILD,role='primary',lock=self.lock))
        self.assertEqual(1,self.native.drains-self.prior_drains);self.assertEqual(1,self.retires());self.assertIsNone(self.private.read())
        self.assertIsNone(self.native.deferred);self.assertFalse(list(self.native.root.iterdir()))
        self.assertTrue(all(row['fd'] is None for row in self.native.rows.values()))
        self.assertNotIn(INPUT['text'],self.store.path.read_text());self.assertEqual(['retire','inspect','inspect'],[row['query']['operation'] for row in owner.state['queries']])
        for fault in ('missing-fence','fence-after-retire'):
            state=deepcopy(owner.state)
            if fault=='missing-fence':state['drains']=[]
            else:
                state['drains'][-1]['acquisition']['hostAfterEpochMs']+=1
                state['drains'][-1]['acquisition']['hostAfterMonotonic']+=.001
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):owner.decode(owner.envelope(state))

    def test_lost_retire_return_is_followed_by_distinct_inspects_without_another_retire_or_secret_fence(self):
        send=self.observer.send;lost=[]
        def missing(query):
            result=send(query)
            if query['operation']=='retire' and not lost:lost.append(True);raise OSError('Actual retire return lost')
            return result
        self.observer.send=missing
        with self.lock.held():
            with self.assertRaises(OSError):self.owner().cleanup()
            before=deepcopy(self.owner().state['operationClock']);self.native.clock+=26
            owner=self.owner();self.assertEqual(dict(performed=True),owner.cleanup())
            self.assertEqual(before,owner.state['operationClock'])
        self.assertEqual('abandoned',owner.state['queries'][0]['status']);self.assertEqual(1,self.retires());self.assertEqual(1,self.native.drains-self.prior_drains)
        self.assertEqual(3,len({row['query']['commandId'] for row in owner.state['queries']}));self.assertIsNone(self.private.read())

    def test_slow_retire_intent_cannot_send_after_its_original_deadline_or_replay_on_reconstruction(self):
        write=self.store.write;slow=[]
        def saving(value,previous):
            write(value,previous)
            from adapters.script_feature.history import unpack
            state=unpack(value['payload'])[0]
            if state['pending'] is not None and not slow:slow.append(True);self.native.clock+=26
        with self.lock.held():
            with patch.object(self.store,'write',side_effect=saving),self.assertRaises(NativeUIError):self.owner().cleanup()
            self.assertEqual(0,self.retires())
            with self.assertRaises(NativeUIError):self.owner().cleanup()
        self.assertEqual(0,self.retires());self.assertIsNotNone(self.private.read())

    def test_ignored_retire_ack_never_becomes_file_absence_and_never_authorizes_replay(self):
        self.native.fault='cleanup-ack'
        with self.lock.held():
            with self.assertRaises(NativeUIError):self.owner().cleanup()
            with self.assertRaises(NativeUIError):self.owner().cleanup()
        self.assertIsNotNone(self.private.read());self.assertEqual(1,self.retires());self.assertTrue(list(self.native.root.iterdir()))

    def test_actual_remaining_fd_refuses_cleanup_until_the_real_last_fd_closes(self):
        self.native.fault='fd-retained'
        with self.lock.held():
            with self.assertRaises(NativeUIError):self.owner().cleanup()
            self.assertIsNotNone(self.private.read());self.assertTrue(any(row['fd'] is not None for row in self.native.rows.values()))
            self.native.close();self.assertEqual(dict(performed=True),self.owner().cleanup())
        self.assertEqual(1,self.retires())

    def test_lost_private_journal_discard_return_is_adopted_without_more_queries(self):
        discard=self.private.discard;lost=[]
        def missing(value):
            discard(value)
            if not lost:lost.append(True);raise OSError('Actual discard return lost')
        with self.lock.held():
            with patch.object(self.private,'discard',side_effect=missing),self.assertRaises(OSError):self.owner().cleanup()
            commands=deepcopy(self.native.commands);self.assertEqual(dict(performed=True),self.owner().cleanup())
        self.assertEqual(commands,self.native.commands)

    def test_unsafe_matching_payload_is_refused_before_it_can_enter_an_original(self):
        import json
        original=self.observer.original
        def unsafe(**kwargs):
            value=json.loads(original(**kwargs));value['enteredText']=INPUT['text'];return json.dumps(value)
        self.observer.original=unsafe
        with self.lock.held(),self.assertRaises(NativeUIError):self.owner().cleanup()
        self.assertNotIn(INPUT['text'],self.store.path.read_text());self.assertIsNotNone(self.private.read())

    def test_changed_actual_private_owner_after_fence_refuses_retire_before_its_transport(self):
        original=self.observer.original;changed=[]
        def foreign(**kwargs):
            result=original(**kwargs)
            if not kwargs['remote'].endswith('/'+FILE) and not changed:
                value=self.private.read();self.private.write(dict(value,inputId='e'*32),value);changed.append(True)
            return result
        self.observer.original=foreign
        with self.lock.held(),self.assertRaises(NativeUIError):self.owner().cleanup()
        self.assertEqual(0,self.retires());self.assertEqual('e'*32,self.private.read()['inputId'])

    def test_slow_original_journal_save_refuses_fresh_return_and_retains_the_actual_packet_for_later_cleanup(self):
        write=self.store.write;slow=[]
        def saving(value,previous):
            write(value,previous)
            from adapters.script_feature.history import unpack
            state=unpack(value['payload'])[0]
            if state['queries'] and state['queries'][-1]['status']=='observed' and not slow:slow.append(True);self.native.clock+=1.501
        with self.lock.held():
            with patch.object(self.store,'write',side_effect=saving),self.assertRaises(NativeUIError):self.owner().cleanup()
            self.assertIsNotNone(self.private.read());owner=self.owner();self.assertIsNotNone(owner.state['queries'][0]['packet'])
            self.assertEqual(dict(performed=True),owner.cleanup())
        self.assertEqual(1,self.retires())


if __name__=='__main__':unittest.main()
