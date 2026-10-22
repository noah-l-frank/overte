"""Kernel process proofs on owned synthetic stdin workers, never Overte services."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import ast
import io
from http.server import BaseHTTPRequestHandler
import textwrap
import threading
from pathlib import Path
import sys
import unittest
import uuid
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from fixture.messages_mixer import MessagesMixerObservation, valid_control_command
from self_tests import test_messages_mixer as fixture_seams


@unittest.skipUnless(sys.platform.startswith('linux'),'Linux original fixture process source')
class MixerFixtureSourceTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture_seams.MessagesMixerTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.processes={role:self.fixture.spawn(role) for role in MessagesMixerObservation.ROLES}
        self.source=MessagesMixerObservation(self.fixture.mixer,self.processes,self.fixture.owner.matches,
            '11111111-2222-4333-8444-555555555555',1)

    def command(self,action,**changes):
        return dict(schemaVersion=2,commandId=uuid.uuid4().hex,runId='a'*32,instance=self.source.instance,
            observedGeneration=self.fixture.mixer.state()['generation'],action=action,**changes)

    def original_control(self):
        domain=(Path(__file__).resolve().parents[1]/'fixture/domain.py').read_text()
        function=next(node for node in ast.walk(ast.parse(domain)) if isinstance(node,ast.FunctionDef) and node.name=='mixer_control')
        namespace=dict(transition_lock=threading.Lock(),stack_state='online',mixer=self.fixture.mixer,
            mixer_observation=self.source,assignment_processes=self.fixture.processes,need=lambda value:self.assertTrue(value))
        exec(compile(textwrap.dedent(ast.get_source_segment(domain,function)),'original-domain-mixer-control','exec'),namespace)
        return namespace['mixer_control']

    def test_only_original_mixer_changes_while_all_eight_actual_kernel_processes_stay_pinned(self):
        first=self.source.state();self.assertTrue(first['mixer']['running']);self.assertEqual(8,len(first['processes']))
        self.fixture.mixer.transition('offline');absent=self.source.state()
        self.assertFalse(absent['mixer']['running']);self.assertIsNone(absent['mixerIdentity'])
        self.assertEqual(first['processes'],absent['processes']);self.assertEqual(first['instance'],absent['instance'])
        self.fixture.mixer.transition('online');fresh=self.source.state()
        self.assertTrue(fresh['mixer']['running']);self.assertNotEqual(first['mixerIdentity'],fresh['mixerIdentity'])
        self.assertEqual(first['processes'],fresh['processes']);self.assertEqual(first['domainId'],fresh['domainId'])
        self.assertEqual(3,fresh['sequence']);self.assertEqual(3,fresh['mixer']['generation'])
        self.assertNotIn(self.fixture.owner.owner,json.dumps(fresh))
        self.assertNotIn('processId',json.dumps(fresh));self.assertNotIn('startIdentity',json.dumps(fresh))

    def test_dead_non_mixer_and_lost_original_ownership_are_unavailable_not_unchanged(self):
        self.source.state();process=self.processes['assignment-1'];process.terminate();process.wait(timeout=3)
        with self.assertRaises(NativeUIError):self.source.state()
        self.assertIsNone(self.fixture.mixer.process.poll())
        source=MessagesMixerObservation(self.fixture.mixer,{**self.processes,'assignment-1':self.fixture.spawn('1')},
            self.fixture.owner.matches,'11111111-2222-4333-8444-555555555555',1)
        source.state();source.owned=lambda _pid:False
        with self.assertRaises(NativeUIError):source.state()
        self.assertIsNone(self.fixture.mixer.process.poll())

    def test_original_endpoint_wraps_actual_source_after_only_its_existing_transition(self):
        control=self.original_control();original=self.fixture.mixer.process
        for stream in (original.stdin,original.stdout,original.stderr):self.addCleanup(stream.close)
        first=control(None);offline=control(self.command('offline'));online=control(self.command('online'))
        self.assertTrue(first['mixer']['running']);self.assertFalse(offline['mixer']['running']);self.assertTrue(online['mixer']['running'])
        self.assertIsNotNone(original.poll());self.assertNotIn(original,self.fixture.processes)
        self.assertEqual(first['processes'],online['processes']);self.assertEqual(first['domainId'],online['domainId'])
        self.assertNotEqual(first['mixerIdentity'],online['mixerIdentity'])

    def test_online_first_fences_offline_that_arrives_after_recovery_and_binds_original_run(self):
        control=self.original_control();first=control(None);late=self.command('offline')
        online=self.command('online');restored=control(online)
        self.assertTrue(restored['offlineFenced']);self.assertEqual('a'*32,restored['runId'])
        self.assertEqual(first['mixerIdentity'],restored['mixerIdentity'])
        self.assertEqual(first['mixer']['generation'],restored['mixer']['generation'])
        for refused in (late,online,{**self.command('offline'),'runId':'b'*32},
                        {**self.command('offline'),'instance':'b'*32},dict(schemaVersion=1,action='offline')):
            with self.assertRaises(NativeUIError):control(refused)
        final=control(None);self.assertEqual(restored['commands'],final['commands'])
        self.assertEqual(first['mixerIdentity'],final['mixerIdentity'])

    def test_admission_consumes_nonce_before_failed_actual_input_and_online_fence_survives_failure(self):
        control=self.original_control();offline=self.command('offline');original=self.fixture.mixer.transition
        def failed(action):
            original(action)
            raise RuntimeError('lost original transition response')
        with patch.object(self.fixture.mixer,'transition',failed):
            with self.assertRaises(RuntimeError):control(offline)
        actual=control(None);self.assertFalse(actual['mixer']['running'])
        self.assertEqual('failed',actual['commands'][0]['status'])
        with self.assertRaises(NativeUIError):control(offline)
        with patch.object(self.fixture.mixer,'transition',failed):
            with self.assertRaises(RuntimeError):control(self.command('online'))
        actual=control(None);self.assertTrue(actual['mixer']['running']);self.assertTrue(actual['offlineFenced'])
        self.assertEqual(['failed','failed'],[row['status'] for row in actual['commands']])
        with self.assertRaises(NativeUIError):control(self.command('offline'))

    def test_stale_generation_unknown_scope_and_pending_callback_never_dispatch_input(self):
        control=self.original_control();first=control(None);command=self.command('offline')
        for refused in ({**command,'observedGeneration':0},{**command,'observedGeneration':True},
                        {**command,'schemaVersion':True},{**command,'extra':1},
                        {**command,'instance':'b'*32}):
            with self.assertRaises(NativeUIError):control(refused)
        self.assertEqual(first['mixerIdentity'],control(None)['mixerIdentity'])
        self.source.admit(command)
        with self.assertRaises(NativeUIError):control(self.command('online'))
        pending=control(None);self.assertEqual('pending',pending['commands'][0]['status'])
        self.assertEqual(first['mixerIdentity'],pending['mixerIdentity'])
        self.source.complete(command,failed=True)
        final=control(self.command('online'));self.assertTrue(final['offlineFenced'])
        self.assertEqual(first['mixerIdentity'],final['mixerIdentity'])

    def test_original_http_body_passes_closed_v2_command_without_rewriting_original_nonce(self):
        domain=(Path(__file__).resolve().parents[1]/'fixture/domain.py').read_text()
        cls=next(node for node in ast.walk(ast.parse(domain)) if isinstance(node,ast.ClassDef) and node.name=='DomainControlHandler')
        namespace=dict(BaseHTTPRequestHandler=BaseHTTPRequestHandler,json=json,sys=sys,Path=Path,
            valid_control_command=valid_control_command)
        exec(compile(ast.Module(body=[cls],type_ignores=[]),'original-domain-control-handler','exec'),namespace)
        def request(command,token='t'*48):
            handler=namespace['DomainControlHandler'].__new__(namespace['DomainControlHandler'])
            raw=json.dumps(command).encode();handler.path='/v1/messages-mixer-state';handler.token='t'*48
            handler.headers={'Content-Length':str(len(raw)),'X-Overte-E2E-Token':token}
            handler.rfile=io.BytesIO(raw);handler.wfile=io.BytesIO();handler.mixer=self.original_control()
            statuses=[];handler.send_error=lambda status,*args:statuses.append(status)
            handler.send_response=lambda status:statuses.append(status);handler.send_header=lambda *args:None
            handler.end_headers=lambda:None;handler.do_POST()
            return statuses,handler.wfile.getvalue()
        for command in (dict(schemaVersion=1,action='offline'),{**self.command('offline'),'schemaVersion':True},
                        {**self.command('offline'),'unexpected':True}):
            self.assertEqual([400],request(command)[0])
        self.assertEqual([404],request(self.command('offline'),token='bad')[0])
        command=self.command('online');statuses,raw=request(command);self.assertEqual([200],statuses)
        value=json.loads(raw);self.assertEqual(command['commandId'],value['commands'][0]['commandId'])
        self.assertTrue(value['offlineFenced']);self.assertEqual('completed',value['commands'][0]['status'])
        self.assertEqual([503],request(self.command('offline'))[0])



if __name__=='__main__':unittest.main()
