"""Synthetic native/OpenXR boundaries; no physical controller or headset run."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_back import PicoLifecycleBack,BUTTON
from adapters.script_journey.history import pack,unpack
from openxr_input.adapter_session import AdapterSessionError,PicoOpenXrAdapterSession
from self_tests.test_pico_lifecycle_source import Boundary,RUN
from self_tests.test_pico_openxr_adapter_session import FakeTransport

BINDING=dict(sourceRevision='1'*40,artifactSha256='2'*64,processIdentity='123:400',sessionId='session-owned',
    generation=1,targetFingerprint='3'*64)


class Native(Boundary):
    def __init__(self):
        super().__init__();self.mode='released';self.effect=False;self.change=None
    def send(self,request):
        if self.effect:
            self.rows[0].update(current=False,text='',focused=False,visible=False)
            self.home,self.raised=True,False
            if self.mode!='hidden':self.rows[0].update(fieldAlive=False,pageAlive=False,attached=False)
            if self.mode=='released':self.rows[0].update(contextAlive=False,alive=False)
        super().send(request)
        self.value['capturedEpochMs']=20000+round(self.clock*1000)
        if self.change:self.change(self.value)
    def source(self):
        value=super().source();value.clock_ms=lambda:20000+round(self.clock*1000);return value


class Transport(FakeTransport):
    def __init__(self,native,path):super().__init__();self.native,self.path=native,path;self.fail=None;self.before=None
    def stage(self,envelope,profile):
        # Assert the exact original envelope reached durable host intent before
        # the first possible transport write, including a lost commit response.
        owner=json.loads(self.path.read_text());state=unpack(owner['payload'])[0]
        if self.before:self.before(state,envelope)
        assert state['phase']=='enveloped' and state['envelope']==envelope
        result=super().stage(envelope,profile);self.native.effect=self.native.mode!='ignored'
        if self.fail=='grant':raise AdapterSessionError('explicit synthetic uncertain commit')
        return result
    def read_status(self,**kwargs):
        result=super().read_status(**kwargs)
        result.update(updatedEpochMs=20000)
        if self.fail=='ack' and kwargs.get('expected_sequence'):raise AdapterSessionError('explicit synthetic lost ACK')
        if self.fail=='neutral':result['state']='error'
        if self.fail=='future':result['updatedEpochMs']=500000
        return result


class LifecycleBackTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='pico-lifecycle-back-');self.root=Path(self.temporary.name)
        self.root.chmod(0o700);self.path=self.root/'owner.json';self.native=Native()
        self.transport=Transport(self.native,self.path)
        self.session=PicoOpenXrAdapterSession(self.transport,'explicit-synthetic-target',self.root)
        self.session.begin(BINDING['processIdentity'])
    def tearDown(self):self.temporary.cleanup()
    def owner(self,**kwargs):
        return PicoLifecycleBack(self.native.source(),self.session,self.path,RUN,kwargs.get('binding',BINDING),
            lambda:self.native.alive,monotonic=lambda:self.native.clock,sleep=self.native.sleep)
    def test_real_route_source_and_keyboard_quiet_release_original_objects(self):
        owner=self.owner();result=owner.back()
        self.assertEqual('released',result['phase']);self.assertTrue(result['routeObserved']);self.assertTrue(result['editorRetired'])
        self.assertEqual(BUTTON,self.transport.envelopes[0]['commands'][0]['arguments'])
        self.assertGreaterEqual(self.native.clock,3);self.assertTrue(self.path.exists())
        state=unpack(json.loads(self.path.read_text())['payload'])[0]
        self.assertGreaterEqual(len(state['frames']),14)
        for original in state['frames']:self.assertEqual(original['raw'],json.dumps(json.loads(original['raw'])))
        self.assertEqual(20000,state['neutral']['updatedEpochMs']) # Never retimed to the final native sample.
        with self.assertRaises(NativeUIError):owner.back()
        self.assertEqual(1,len(self.transport.envelopes))
    def test_retained_original_context_is_reported_and_never_hidden_by_page_retirement(self):
        self.native.mode='retained';result=self.owner().back()
        self.assertEqual('retained',result['phase']);self.assertFalse(result['editorRetired'])
        self.assertTrue(result['editor']['contextAlive']);self.assertFalse(result['editor']['pageAlive'])
        reconstructed=self.owner();self.native.mode='released'
        self.assertTrue(reconstructed.reconcile()['editorRetired']);self.assertEqual(1,len(self.transport.envelopes))
        self.assertTrue(self.path.exists()) # Full-feature join is still absent.
    def test_ack_and_hidden_page_never_qualify_an_observed_retired_editor(self):
        for mode in ('ignored','hidden'):
            with self.subTest(mode=mode):
                self.native.mode=mode
                with self.assertRaises(NativeUIError):self.owner().back()
                self.assertEqual(1,len(self.transport.envelopes));self.assertTrue(self.path.exists())
                with self.assertRaises(NativeUIError):self.owner().back()
                # Reset only the explicit isolated synthetic boundary per case.
                self.tearDown();self.setUp()
    def test_lost_ack_reconciles_original_once_without_replaying_input(self):
        self.transport.fail='ack'
        with self.assertRaises(NativeUIError):self.owner().back()
        self.transport.fail=None
        self.assertTrue(self.owner().reconcile()['editorRetired']);self.assertEqual(1,len(self.transport.envelopes))
    def test_uncertain_grant_or_newer_stream_cannot_be_adopted_or_reissued(self):
        self.transport.fail='grant'
        with self.assertRaises(NativeUIError):self.owner().back()
        self.transport.fail=None
        with self.assertRaises(NativeUIError):self.owner().reconcile()
        with self.assertRaises(NativeUIError):self.owner().back()
        self.assertEqual(1,len(self.transport.envelopes));self.assertTrue(self.path.exists())
    def test_read_only_reconciliation_rejects_newer_session_cursor(self):
        self.owner().back()
        with self.session._lock():
            state=self.session._load();state['nextSequence']+=1;self.session._save(state)
        with self.assertRaises(NativeUIError):self.owner().reconcile()
        self.assertEqual(1,len(self.transport.envelopes))
    def test_keyboard_ghost_pressed_key_and_unavailable_native_source_keep_original_journal(self):
        faults=(lambda v:v['source']['keyboard']['keys'][0].update(pressed=True),
            lambda v:v['source']['keyboard']['entities'][-1].update(visible=True),
            lambda v:v['source'].update(complete=False),lambda v:v['source'].update(current='f'*32))
        for fault in faults:
            def apply(value):
                if self.native.effect:fault(value)
            self.native.change=apply
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.owner().back()
            self.assertTrue(self.path.exists());self.assertEqual(1,len(self.transport.envelopes))
            self.tearDown();self.setUp()
    def test_foreign_candidate_process_run_and_changed_original_bytes_fail_without_sending(self):
        self.owner().back();original=self.path.read_text()
        for key in ('sourceRevision','artifactSha256','processIdentity','sessionId','generation','targetFingerprint'):
            binding=deepcopy(BINDING);binding[key]=2 if key=='generation' else ('4'*len(binding[key]))
            with self.subTest(key=key),self.assertRaises((NativeUIError,ValueError)):self.owner(binding=binding)
        value=json.loads(original);state=unpack(value['payload'])[0];state['frames'][0]['raw']+=' '
        value['payload']=pack([state]);self.path.write_text(json.dumps(value));self.path.chmod(0o600)
        with self.assertRaises(NativeUIError):self.owner()
        self.assertEqual(1,len(self.transport.envelopes))
    def test_source_and_host_clock_both_have_to_measure_the_full_quiet_window(self):
        def frozen(value):value['capturedEpochMs']=20000
        self.native.change=frozen
        with self.assertRaises(NativeUIError):self.owner().back()
        self.assertTrue(self.path.exists());self.assertEqual(1,len(self.transport.envelopes))
    def test_future_or_failed_native_neutrality_never_turns_an_ack_into_quiet(self):
        for mode in ('future','neutral'):
            self.transport.fail=mode
            with self.subTest(mode=mode),self.assertRaises(NativeUIError):self.owner().back()
            self.assertTrue(self.path.exists());self.assertEqual(1,len(self.transport.envelopes))
            self.tearDown();self.setUp()
    def test_final_neutral_read_and_locked_intent_do_not_age_an_original_into_success(self):
        owner=self.owner();original=self.session.require_owned_neutral;calls=0
        def slow(*args):
            nonlocal calls
            result=original(*args);calls+=1
            if calls==2:self.native.clock+=2
            return result
        self.session.require_owned_neutral=slow
        with self.assertRaises(NativeUIError):owner.back()
        self.assertTrue(self.path.exists());self.assertEqual(1,len(self.transport.envelopes))
        self.tearDown();self.setUp();owner=self.owner();save=owner.save
        def slow_intent(value):
            save(value)
            if value['phase']=='enveloped':self.native.clock+=2
        owner.save=slow_intent
        with self.assertRaises(NativeUIError):owner.back()
        self.assertTrue(self.path.exists());self.assertEqual([],self.transport.envelopes)

    def test_durable_intent_failure_prevents_even_the_first_possible_transport_write(self):
        owner=self.owner();original=owner.save
        def fail(value):
            if value['phase']=='enveloped':raise NativeUIError('explicit synthetic disk failure')
            original(value)
        owner.save=fail
        with self.assertRaises(NativeUIError):owner.back()
        self.assertEqual([],self.transport.envelopes);self.assertTrue(self.path.exists())
        with self.assertRaises(NativeUIError):self.owner().reconcile()
        with self.assertRaises(NativeUIError):self.owner().back()


if __name__=='__main__':unittest.main()
