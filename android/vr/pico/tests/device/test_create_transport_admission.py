"""Real Create phase/CAS admission at the actual NativeNavigationIO writer.

SDK, Qt observation and writer status are declared host seams. No ACK is an
entity effect; this checks only publication and retained original ownership.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import inspect
import json
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch
import test_create_journey as parent_fixture
from adapters.normal_ui import NativeUIError
from adapters.pico4.navigation import NativeNavigationIO,PicoNavigation
from adapters.pico4.normal_create import PicoCreateIO
from adapters.pico4.normal_scripts import PicoScriptIO
from adapters.token_create_ui import TokenCreateUI


class CreateTransportAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.h=parent_fixture.CreateJourneyTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.root,self.b=self.h.root,self.h.b
        # A lost completion keeps the exact original activated Open call.
        with patch.object(self.root,'complete_call',side_effect=NativeUIError('declared lost completion')):
            with self.assertRaises(NativeUIError):self.h.act('open')
        self.pending=self.root.state()['pending'];self.published=[];self.status=None
        self.snapshot=lambda:parent_fixture.RuntimeIO(self.b).capture()
        binding=self.root.state()['binding'];identity=binding['processIdentity']
        def require(target,original,_reason):
            self.assertEqual(self.root.target,target);self.assertEqual(identity,original)
        def read(_target,_package,path,**_kwargs):
            if path.endswith('observation.json'):return json.dumps(self.snapshot())
            self.assertTrue(path.endswith('status.json'));return json.dumps(self.status) if self.status else ''
        def write(_target,_package,path,raw):
            self.assertTrue(path.endswith('command.json'));command=json.loads(raw);self.published.append(deepcopy(command))
            self.b.ui.command_sequence+=1
            self.status=dict(schemaVersion=1,bridgeId=command['bridgeId'],commandId=command['commandId'],sequence=command['sequence'],
                performed=True,error='',processId=123,updatedEpochMs=self.b.epoch())
        sdk=SimpleNamespace(require_same_process=require,require_pico_session_identity=lambda _target:identity,
            _installation=lambda _target:None,probe_retry_policy=lambda:(1,0),adb=SimpleNamespace(
            foreground_package=lambda _target:'org.overte.pico',epoch_milliseconds=lambda _target:self.b.epoch(),
            read_debug_app_file=read,write_debug_app_file=write))
        self.native=NativeNavigationIO(sdk,self.root.target,identity,lambda _operation:None)
        candidate=dict(schemaVersion=1,sourceRevision=binding['sourceRevision'],artifactSha256=binding['artifactSha256'],installedCandidateVerified=True)
        self.navigation=PicoNavigation(self.native,self.h.path/'transport-ui.json',candidate,identity,'http://controlled.test/scene.json',
            monotonic=self.b.now,sleep=self.b.ui.sleep)
        io=PicoScriptIO(self.navigation)
        self.native.bind_before_send(lambda command:self.root.dispatch_admission(command,self.navigation))
        self.flow=TokenCreateUI(PicoCreateIO(io),self.root.input,monotonic=self.b.now,sleep=self.b.ui.sleep)

    def send(self,identifier='create.tab.0'):
        with self.root.lock.held():return self.flow.input(identifier)

    def generic(self,identifier='tablet.page.2'):
        original=self.snapshot;self.generic_row=dict(id=identifier,token=str(uuid.uuid4()),enabled=True,focused=False)
        def snapshot():
            value=original();value['controls']=[deepcopy(self.generic_row)];return value
        self.snapshot=snapshot

    def test_exact_original_intent_reaches_single_original_writer(self):
        self.send();self.assertEqual(1,len(self.published));original=self.root.state()['lastInput']['original']
        self.assertEqual(original['controlToken'],self.published[0]['controlToken'])
        self.assertEqual(self.pending,self.root.state()['pending'])

    def test_phase_advance_in_actual_last_native_guard_prevents_publication(self):
        original=self.native.guard;advanced=False
        def guard():
            nonlocal advanced
            original()
            if inspect.currentframe().f_back.f_code.co_name=='send' and not advanced:
                advanced=True;self.h.journal.activate(self.root.run,uuid.uuid4().hex,'cleanup',{})
        with patch.object(self.native,'guard',guard),self.assertRaises(NativeUIError):self.send()
        self.assertTrue(advanced);self.assertEqual([],self.published);self.assertEqual(self.pending,self.root.state()['pending'])
        count=self.root.state()['inputCount']
        with self.assertRaises(NativeUIError):self.root.invoke('reconcile')
        self.assertEqual(count,self.root.state()['inputCount']);self.assertEqual([],self.published)

    def test_frozen_native_clock_cannot_hide_slow_final_phase_read(self):
        self.b.freeze_epoch=True;original=self.root.phase_fence;reads=0
        def phase():
            nonlocal reads
            result=original();reads+=1
            if reads==2:self.b.ui.clock+=2
            return result
        with patch.object(self.root,'phase_fence',phase),self.assertRaises(NativeUIError):self.send()
        self.assertEqual(2,reads);self.assertEqual([],self.published);self.assertEqual(self.pending,self.root.state()['pending'])

    def test_changed_original_native_token_after_command_capture_prevents_publication(self):
        original=self.native.guard;changed=False
        def guard():
            nonlocal changed
            original()
            if inspect.currentframe().f_back.f_code.co_name=='send' and not changed:
                changed=True;self.b.focus='create.tab.0'
        with patch.object(self.native,'guard',guard),self.assertRaises(NativeUIError):self.send()
        self.assertTrue(changed);self.assertEqual([],self.published);self.assertEqual(self.pending,self.root.state()['pending'])

    def test_original_generic_pager_and_home_without_input_ready_reach_original_writer(self):
        self.generic();self.send('tablet.page.2');self.generic_row['id']='tablet.home';self.send('tablet.home')
        self.assertEqual(['tablet.page.2','tablet.home'],[r['controlId'] for r in self.published])
        self.assertEqual(self.pending,self.root.state()['pending'])

    def test_disabled_actual_generic_pager_after_intent_refuses_final_publication(self):
        self.generic();original=self.native.guard
        def guard():
            original()
            if inspect.currentframe().f_back.f_code.co_name=='send':self.generic_row['enabled']=False
        with patch.object(self.native,'guard',guard),self.assertRaises(NativeUIError):self.send('tablet.page.2')
        self.assertEqual([],self.published);self.assertEqual(self.pending,self.root.state()['pending'])

    def test_foreign_generic_reference_refuses_before_publication(self):
        self.generic();reference=self.flow.capture();reference['controls'][0]['token']=str(uuid.uuid4())
        with self.root.lock.held(),self.assertRaises(NativeUIError):self.flow.io.activate('tablet.page.2',reference=reference)
        self.assertEqual([],self.published);self.assertEqual(self.pending,self.root.state()['pending'])

    def test_stale_original_generic_scope_refuses_final_publication(self):
        self.generic();original=self.native.guard
        def guard():
            original()
            if inspect.currentframe().f_back.f_code.co_name=='send':self.b.ui.clock+=5.1
        with patch.object(self.native,'guard',guard),self.assertRaises(NativeUIError):self.send('tablet.page.2')
        self.assertEqual([],self.published);self.assertEqual(self.pending,self.root.state()['pending'])

    def test_feature_control_without_input_ready_remains_unavailable(self):
        original=self.snapshot
        def snapshot():
            value=original();next(row for row in value['controls'] if row['id']=='create.tab.0').pop('inputReady');return value
        self.snapshot=snapshot
        with self.assertRaises(NativeUIError):self.send()
        self.assertEqual([],self.published);self.assertEqual(self.pending,self.root.state()['pending'])


class CreateTransportFactoryTests(unittest.TestCase):
    def test_actual_pico_create_factory_binds_original_navigation_callback(self):
        import test_normal_create as original
        h=original.PicoCreateTests();h.setUp();self.addCleanup(h.doCleanups);seen=[]
        def admit(command,navigation):
            self.assertIsInstance(navigation.io,NativeNavigationIO);self.assertEqual([],h.native.inputs)
            seen.append(deepcopy(command))
        flow=h.instance._create_controls(h.native.target,h.widget.intents.append,before_send=admit)
        flow.input('create.tab.0');self.assertEqual(1,len(seen));self.assertEqual([seen[0]],h.native.inputs)


if __name__=='__main__':unittest.main()
