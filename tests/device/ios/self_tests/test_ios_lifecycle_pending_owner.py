"""Normal editor replacement and real host WALs; Qt/native/SDK modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from ios.adapters import feature_observation,lifecycle_pending_commands as receipts
from ios.adapters.lifecycle_pending_owner import LifecyclePendingOwner
from ios.adapters.lifecycle_editors_runtime import IOSLifecycleEditorsRuntime
from ios.self_tests.test_ios_lifecycle_editors import EditorDomain


class PendingDomain:
    def __init__(self,case):
        self.d=EditorDomain(case);self.source=self.d.source;self.native=self.d.f.f.p.boundary
        self.rows=[];self.query=None;self.queries=[];self.sequence=0;self.packet=None;self.lost=None;self.never=None
        for editor in ('create','chat'):
            self.d.flow.open(editor);self.d.flow.back(editor)
        self.d.flow.open('scripts');self.d.flow.type('scripts','retry-'+self.source.run)
        original=self.native.original
        def tap():
            raw=original();reply=json.loads(raw);command=self.native.request
            if command['operation'] in ('hold','attempt','release') and not any(row['command']['commandId']==command['commandId'] for row in self.rows):
                self.rows.append(dict(index=len(self.rows)+1,command=deepcopy(command),reply=deepcopy(reply),recordedEpochMs=self.d.f.f.stamp()['epochMs']))
            return raw
        self.native.original=tap
        send=self.source.pending.send
        def deliver(command):
            if command['operation']==self.never:raise OSError('Declared unknown command delivery before modeled native reception')
            value=send(command)
            if command['operation']==self.lost:
                self.lost=None;self.native.original();raise OSError('Declared lost return after actual modeled native command')
            return value
        self.source.pending.send=deliver
        old_post=feature_observation.post_request.side_effect;client=self.source.source['client'];old_execute=client.execute
        def post(request,timeout):
            query=json.loads(request.data)
            if query['action']!=receipts.ACTION:return old_post(request,timeout)
            self.query=deepcopy(query);self.queries.append(deepcopy(query));self.sequence+=1;raw=json.dumps(query).encode()
            class Response:
                status=200
                def __enter__(self):return self
                def __exit__(self,*args):return False
                def read(self,limit):return raw[:limit]
            return Response()
        def execute(session,operation,values):
            if operation=='mobile: pullFile' and values['remotePath'].endswith('/'+receipts.FILE):
                before=self.d.f.f.stamp();after=self.d.f.f.stamp()
                self.packet=dict(iosLifecyclePendingCommandsVersion=1,requestId=self.query['commandId'],runId=self.query['runId'],instance='c'*32,
                    sequence=self.sequence,processId=42,clockDomain='native-main-lifecycle-pending-commands',clockBefore=before,clockAfter=after,
                    source=dict(installed=True,complete=True,commands=deepcopy(self.rows)))
                return base64.b64encode(json.dumps(self.packet).encode()).decode()
            return old_execute(session,operation,values)
        client.execute=execute;case.enterContext(patch.object(feature_observation,'post_request',side_effect=post))
        self.runtime=IOSLifecycleEditorsRuntime(self.d.f.f.f.adapter);self.owner=self.reopen()
    def reopen(self):
        self.owner=self.runtime.pending_child('test-only',self.d.flow);return self.owner
    def count(self,operation):return sum(row['operation']==operation for row in self.native.commands)


class LifecyclePendingOwnerTests(unittest.TestCase):
    def setUp(self):self.b=PendingDomain(self)

    def test_normal_held_callback_home_reopen_and_actual_stale_rejection_keep_original_generation_four(self):
        b=self.b;held=b.owner.act('hold');captured=deepcopy(held['commit']['observation']['events'][0]);event=held['commit']['observation']['eventId']
        replaced=b.d.flow.replace_scripts();self.assertEqual(4,replaced['generation'])
        rejected=b.owner.act('attempt');self.assertEqual('context-retired',rejected['commit']['observation']['events'][-1]['reason'])
        released=b.owner.act('release');self.assertEqual([],released['resources']['pendingRuns'])
        actual=b.d.flow.history.historical_editor(len(b.d.flow.history.state['frames']))
        self.assertEqual(dict(editor='scripts',text='',focused=False,generation=4,keyboard=False),actual)
        self.assertEqual(captured,rejected['commit']['observation']['events'][0]);self.assertEqual(event,released['commit']['observation']['eventId'])
        self.assertEqual([1,1,1],[b.count(operation) for operation in ('hold','attempt','release')])
        b.reopen().act('release');self.assertEqual(1,b.count('release'))
        b.d.flow.back('scripts');closed=b.d.flow.history.historical_editor(len(b.d.flow.history.state['frames']))
        self.assertEqual(dict(editor='none',text='',focused=False,generation=0,keyboard=False),closed)
        self.assertEqual(4,len(b.d.flow.history.state['aliases']))
        malformed=deepcopy(b.owner.previous);malformed['state']['events'][-1]['after']['index']=1024
        with self.assertRaises(NativeUIError):b.owner.decode(malformed)

    def test_lost_hold_recovers_exact_native_return_without_capturing_another_event(self):
        b=self.b;b.lost='hold'
        with self.assertRaises(NativeUIError):b.owner.act('hold')
        self.assertEqual('issued',b.owner.state['events'][0]['phase']);saved=deepcopy(b.rows[0])
        held=b.reopen().act('hold');self.assertEqual(saved['reply'],held);self.assertEqual(1,b.count('hold'))
        self.assertEqual(saved,b.rows[0]);self.assertIsNotNone(b.owner.state['events'][0]['after'])

    def test_lost_stale_attempt_is_not_reissued_and_new_field_remains_empty_unfocused(self):
        b=self.b;b.owner.act('hold');b.d.flow.replace_scripts();b.lost='attempt'
        with self.assertRaises(NativeUIError):b.owner.act('attempt')
        b.reopen().act('attempt');self.assertEqual(1,b.count('attempt'))
        actual=b.d.flow.history.historical_editor(len(b.d.flow.history.state['frames']))
        self.assertEqual('',actual['text']);self.assertFalse(actual['focused']);self.assertFalse(actual['keyboard'])

    def test_unknown_unreceived_command_remains_issued_without_native_resend(self):
        b=self.b;b.never='hold'
        with self.assertRaises(NativeUIError):b.owner.act('hold')
        with self.assertRaises(NativeUIError):b.reopen().act('hold')
        self.assertEqual(0,b.count('hold'));self.assertEqual('issued',b.owner.state['events'][0]['phase'])
        self.assertEqual([],b.rows)

    def test_saved_receipt_before_parent_return_recovers_unchanged_inode_without_getter_repeat(self):
        b=self.b;write=OriginalFrameStore.write;saved={}
        def interrupted(store,index,value):
            result=write(store,index,value)
            if store.namespace=='ios-lifecycle-pending-proof':
                path=store.path(store.expand(result));saved.update(path=path,inode=path.stat().st_ino,body=path.read_bytes())
                raise OSError('Declared lost saved-receipt return before parent append')
            return result
        with patch.object(OriginalFrameStore,'write',interrupted):
            with self.assertRaises(OSError):b.owner.act('hold')
        count=len(b.queries);b.reopen().act('hold')
        self.assertEqual(count,len(b.queries));self.assertEqual(1,b.count('hold'))
        self.assertEqual(saved['inode'],saved['path'].stat().st_ino);self.assertEqual(saved['body'],saved['path'].read_bytes())

    def test_literal_one_editor_state_reads_and_explicit_replacement_migrates_without_changing_old_frames(self):
        b=self.b;flow=b.d.flow;old=deepcopy(flow.previous);legacy=deepcopy(old);legacy['iosLifecycleEditorsVersion']=1
        flow.store.write(legacy,old);flow.previous=deepcopy(legacy);flow.version=1;flow.decode(legacy)
        b.owner.act('hold');original=[deepcopy(ref) for ref in flow.history.state['frames']]
        flow.replace_scripts();self.assertEqual(2,flow.store.read()['iosLifecycleEditorsVersion'])
        self.assertEqual(original,flow.history.state['frames'][:len(original)])
        self.assertEqual(4,flow.history.state['aliases'][-1]['generation'])

    def test_wrong_sent_result_is_not_a_successful_retired_context_attempt(self):
        b=self.b;b.owner.act('hold');b.d.flow.replace_scripts();b.native.fault='attempt-sent'
        with self.assertRaises(NativeUIError):b.owner.act('attempt')
        self.assertEqual(1,b.count('attempt'));self.assertEqual('returned',b.owner.state['events'][-1]['phase'])
        self.assertIsNone(b.owner.state['events'][-1]['after'])

    def test_lost_release_is_recovered_without_releasing_another_event(self):
        b=self.b;b.owner.act('hold');b.d.flow.replace_scripts();b.owner.act('attempt');b.lost='release'
        with self.assertRaises(NativeUIError):b.owner.act('release')
        result=b.reopen().act('release');self.assertEqual(1,b.count('release'));self.assertEqual([],result['resources']['pendingRuns'])

    def test_failed_durable_intent_prevents_native_hold(self):
        b=self.b
        with patch.object(b.owner.store,'write',side_effect=OSError('Declared failed native intent CAS')):
            with self.assertRaises(OSError):b.owner.act('hold')
        self.assertEqual(0,b.count('hold'));self.assertIsNone(b.owner.store.read());self.assertEqual([],b.rows)
