"""Real Phone input coordinator with synthetic SDK/native/OS boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import json
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
sys.path.insert(0,str(ROOT/'tests/device/adapters/android-phone'))
import test_feature_adapters as bound
from overte_phone_script_actions import PhoneScriptActions
from adapters.normal_ui import NativeUIError
from feature_journeys.scenarios import VERSION

RUN='a'*32
FIXTURE='http://fixture.test/feature-fixture/v1/runs/'+RUN+'/'


class ScriptActionTests(unittest.TestCase):
    def setUp(self):
        self.f=bound.FeatureAdapterTests('test_phone_initial_script_baseline_uses_actual_native_location_without_staging_files')
        self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.commands,self.fixture,self.files=self.f.script_measurement_boundaries(absent=True)
        # The action coordinator starts from an empty original input scope.
        # The shared fixture helper's host-only reservation created no files.
        self.files.store.discard(self.files.owned())
        self.f.read_only_boundaries(forbid_normal_session=False)
        self.counter=0
        self.flow=self.f.adapter._script_actions(bound.SELECTOR,RUN,self.fixture)

    def call(self,verb,inputs=None,ticket=None):
        self.counter+=1
        return dict(contractVersion=VERSION,runId=RUN,fixtureUrl=self.fixture,
            ticket=ticket or format(self.counter,'032x'),verb=verb,inputs=inputs or {})

    def act(self,verb,inputs=None):
        return self.flow.act(self.call(verb,inputs))

    def test_prepare_observes_actual_absent_location_without_staging_or_product_input(self):
        state=self.flow.prepare()
        self.assertEqual('ready',state['phase']);self.assertFalse(state['staged'])
        self.assertEqual(self.f.script_measurement_storage.root.as_uri(),state['directory'])
        self.assertFalse(self.f.script_measurement_storage.root.exists())
        self.assertEqual([],self.f.native.inputs);self.assertEqual([],self.f.native.lifecycle_inputs)
        self.assertTrue(all(row['operation']=='locate' for row in self.f.script_measurement_storage.commands))

    def test_first_ten_normal_inputs_use_existing_controls_original_files_and_persisted_native_barriers(self):
        self.flow.prepare()
        recipe=[('open',{}),('picker-open',{}),('picker-cancel',{}),('picker-open',{}),
            ('picker-accept',{'resource':'script.js'}),('stop-owned',{}),('picker-open',{}),
            ('picker-cancel',{}),('picker-open',{}),('picker-accept',{'resource':'script-bundle/main.js'})]
        with patch.object(bound.AppiumAdapter,'ensure_session',side_effect=AssertionError('unexpected session repair')):
            for verb,inputs in recipe:self.assertEqual({'performed':True},self.act(verb,inputs))
        state=self.flow.load();self.assertEqual(10,len(state['tickets']))
        self.assertEqual('acknowledged',state['phase']);self.assertTrue(state['staged'])
        self.assertEqual(31,state['current']['barrier']['processId'])
        self.assertEqual('d'*32,state['current']['barrier']['instance'])
        self.assertEqual(1,sum(row['operation']=='stage' for row in self.f.script_measurement_storage.commands))
        self.assertEqual(1,len(self.f.native.rows)) # The second actual SDK import remains active.
        self.assertTrue(self.f.native.rows[0]['url'].endswith('/script-bundle/main.js'))
        self.assertEqual([],self.f.native.lifecycle_inputs)
        # An input ACK is not a claim that this synthetic native source executes.
        self.assertEqual([],state['current']['barrier']['source']['engines'])

    def test_repeated_confirmed_input_returns_delivery_only_without_another_click_or_stage(self):
        self.flow.prepare();call=self.call('open');self.flow.act(call)
        before=(list(self.f.native.inputs),list(self.f.script_measurement_storage.commands))
        self.assertEqual({'performed':True},self.flow.act(call))
        self.assertEqual(before[0],self.f.native.inputs)
        self.assertEqual(1,sum(row['operation']=='stage' for row in self.f.script_measurement_storage.commands))
        self.assertEqual(1,len(self.flow.load()['tickets']))

    def test_changed_input_for_an_existing_ticket_is_not_replayed(self):
        self.flow.prepare();call=self.call('open');self.flow.act(call)
        before=list(self.f.native.inputs)
        with self.assertRaises(NativeUIError):self.flow.act(call|dict(verb='picker-open'))
        self.assertEqual(before,self.f.native.inputs)

    def test_lost_normal_input_return_remains_issued_and_cannot_be_retried_as_a_repair(self):
        self.flow.prepare();call=self.call('open')
        original=self.flow._deliver
        def lost(value):original(value);raise RuntimeError('simulated lost input return')
        with patch.object(self.flow,'_deliver',side_effect=lost):
            with self.assertRaises(NativeUIError):self.flow.act(call)
        before=list(self.f.native.inputs);self.assertEqual('issued',self.flow.load()['phase'])
        again=self.f.adapter._script_actions(bound.SELECTOR,RUN,self.fixture)
        with self.assertRaises(NativeUIError):again.act(call)
        self.assertEqual(before,self.f.native.inputs)
        self.assertEqual(1,sum(row['operation']=='stage' for row in self.f.script_measurement_storage.commands))
        self.assertIsNotNone(self.f.adapter.script_store(bound.SELECTOR).read())

    def test_lost_final_journal_return_resumes_only_the_known_ack_without_input_replay(self):
        self.flow.prepare();call=self.call('open');original=self.flow.store.write
        from overte_phone_script_history import unpack
        def lost(value,previous):
            original(value,previous)
            if unpack(value['payload'])[0]['phase']=='acknowledged':raise OSError('simulated lost private return')
        with patch.object(self.flow.store,'write',side_effect=lost):
            with self.assertRaises(NativeUIError):self.flow.act(call)
        before=list(self.f.native.inputs)
        again=self.f.adapter._script_actions(bound.SELECTOR,RUN,self.fixture)
        self.assertEqual({'performed':True},again.act(call));self.assertEqual(before,self.f.native.inputs)
        self.assertEqual(1,len(again.load()['tickets']))

    def test_ignored_fixture_stage_is_detected_before_any_manager_input(self):
        self.flow.prepare();self.f.script_measurement_storage.fault='ack-only'
        with self.assertRaises(NativeUIError):self.act('open')
        self.assertEqual([],self.f.native.inputs);self.assertEqual('issued',self.flow.load()['phase'])
        self.assertTrue(self.flow.state['current']['stageAttempted'])
        self.assertFalse(self.f.script_measurement_storage.root.exists())
        self.assertIsNotNone(self.f.adapter.script_files_store(bound.SELECTOR).read())

    def test_foreign_run_or_unsupported_input_is_rejected_before_issuing_a_command(self):
        self.flow.prepare();before=len(self.commands)
        for changes in (dict(runId='f'*32),dict(contractVersion=True),dict(inputs={'expected':'running'})):
            with self.subTest(changes=changes),self.assertRaises(NativeUIError):self.flow.act(self.call('open')|changes)
        self.assertEqual(before,len(self.commands));self.assertEqual('ready',self.flow.load()['phase'])

    def test_candidate_change_rejects_even_an_old_confirmed_delivery_without_other_input(self):
        self.flow.prepare();call=self.call('open');self.flow.act(call)
        before=list(self.f.native.inputs);self.f.fixture.adb.digest='f'*64
        with self.assertRaises(NativeUIError):self.flow.act(call)
        self.assertEqual(before,self.f.native.inputs)

    def missing_fixture(self, *, callback=True):
        from self_tests.test_script_ui_inventory import inventory
        from self_tests.test_script_manager_status import observed
        from self_tests.test_native_script_loads import history,event
        original=self.f.fixture.adb.read_debug_app_file.side_effect;events=[]
        def read(device,package,path,**options):
            raw=original(device,package,path,**options)
            if path.endswith('/feature-script-observation.json'):
                packet=json.loads(raw);history(packet,events);return json.dumps(packet)
            if path.endswith('/phone-script-file-ui.json'):
                packet=json.loads(raw)
                if packet['action']=='observe':
                    opened=self.f.native.screen=='scripts'
                    packet['scriptInventory']=inventory([observed(statusText='',labelText='',labelVisible=False)] if opened else [],
                        tabletPresent=self.f.native.screen is not None,tabletShown=self.f.native.screen is not None)
                return json.dumps(packet)
            return raw
        boundary=patch.object(self.f.fixture.adb,'read_debug_app_file',side_effect=read)
        boundary.start();self.addCleanup(boundary.stop)
        def input_event(name):
            if name=='OK' and self.f.native.text.endswith('/missing.js') and callback:
                events.append(event(url=self.f.native.text,callbackEpochMs=20000))
        self.f.native.mutation=input_event
        self.flow.prepare()
        for verb,inputs in [('open',{}),('picker-open',{}),('picker-accept',{'resource':'script.js'}),('stop-owned',{})]:
            self.act(verb,inputs)
        return events

    def test_missing_url_and_close_use_normal_controls_original_failure_callback_and_preserved_files(self):
        events=self.missing_fixture();call=self.call('load-url',{'resource':'missing.js'})
        self.assertEqual({'performed':True},self.flow.act(call));self.assertEqual(1,len(events))
        self.assertEqual(self.fixture+'tickets/'+call['ticket']+'/missing.js',events[0]['url'])
        self.assertEqual({'performed':True},self.act('close'))
        self.assertIsNone(self.f.adapter.script_store(bound.SELECTOR).read())
        self.assertIsNone(self.f.native.screen);self.assertTrue(self.f.script_measurement_storage.root.exists())
        self.assertEqual(1,sum(row['operation']=='stage' for row in self.f.script_measurement_storage.commands))

    def test_missing_url_without_an_actual_failure_callback_cannot_close_or_discard_load_ownership(self):
        self.missing_fixture(callback=False);self.act('load-url',{'resource':'missing.js'})
        with self.assertRaises(NativeUIError):self.act('close')
        self.assertEqual('issued',self.flow.load()['phase'])
        self.assertTrue(self.f.adapter.script_store(bound.SELECTOR).read()['loadAttempted'])
        self.assertIsNotNone(self.f.native.screen)

    def restart_fixture(self):
        # Actual existing SDK/file/native handoff fixture represents the run
        # immediately before its restart checkpoint; no desired result is seeded.
        storage,_ui,_source,_presence,_state=self.f.restart_boundaries(staged_restart=False)
        flow=self.f.adapter._script_actions(bound.SELECTOR,RUN,self.fixture)
        with flow.lock.held(),self.f.adapter.existing_input_session(bound.SELECTOR):
            _ui,_observe,binding,_check,_installed=self.f.adapter.normal_feature_runtime(bound.SELECTOR,read_only=True)
            files=self.f.adapter._script_files(bound.SELECTOR,read_only=True)
            directory=files.verify()
            flow.save(dict(binding=binding,nativeInstance=files.native.instance,fixtureUrl=self.fixture,
                directory=directory,fileOwner=files.owned(),phase='ready',staged=True,tickets=[],current=None,lastRestart=None))
        return flow,storage

    def test_explicit_restart_updates_binding_only_after_original_exit_native_and_file_handoff(self):
        flow,storage=self.restart_fixture();call=self.call('restart-app')
        self.assertEqual({'performed':True},flow.act(call))
        state=flow.load();self.assertEqual('acknowledged',state['phase'])
        self.assertEqual('31:14',state['current']['binding']['processIdentity'])
        self.assertEqual('32:15',state['binding']['processIdentity'])
        self.assertEqual('ESRCH',state['current']['receipt']['handoff']['exit']['errorSymbol'])
        self.assertEqual('observed',state['lastRestart']['phase'])
        self.assertEqual({'performed':True},flow.act(call))
        self.assertEqual(['stop','launch'],self.f.native.lifecycle_inputs)
        self.assertEqual(1,sum(row['operation']=='stage' for row in storage.commands))

    def test_lost_stop_return_resumes_the_same_restart_intent_without_stop_or_stage_replay(self):
        flow,storage=self.restart_fixture();call=self.call('restart-app');self.f.native.lose_stop_ack=True
        with self.assertRaises(NativeUIError):flow.act(call)
        self.assertEqual('issued',flow.load()['phase']);self.assertEqual(['stop'],self.f.native.lifecycle_inputs)
        again=self.f.adapter._script_actions(bound.SELECTOR,RUN,self.fixture)
        self.assertEqual({'performed':True},again.act(call))
        self.assertEqual(['stop','launch'],self.f.native.lifecycle_inputs)
        self.assertEqual('32:15',again.load()['binding']['processIdentity'])
        self.assertEqual(1,sum(row['operation']=='stage' for row in storage.commands))

    def test_ignored_launch_remains_issued_and_is_never_replayed(self):
        flow,storage=self.restart_fixture();call=self.call('restart-app');self.f.native.ignore_app_launch=True
        for _ in range(2):
            with self.assertRaises(NativeUIError):flow.act(call)
        self.assertEqual('issued',flow.load()['phase']);self.assertEqual(['stop','launch'],self.f.native.lifecycle_inputs)
        self.assertEqual('launch-issued',self.f.adapter._script_restart_inputs(bound.SELECTOR).read()['phase'])
        self.assertEqual(1,sum(row['operation']=='stage' for row in storage.commands))

    def test_general_cleanup_cannot_discard_an_input_journal_even_without_other_owners(self):
        self.flow.store.write({'unresolved':True},None)
        with patch.object(bound.AppiumAdapter,'cleanup',return_value={'cleaned':True}) as base:
            with self.assertRaisesRegex((ValueError,RuntimeError),'PHONE_SCRIPT_ACTIONS_CLEANUP_INCOMPLETE'):
                self.f.adapter.cleanup(bound.SELECTOR)
        base.assert_called_once();self.assertIsNotNone(self.flow.store.read())

    def test_foreign_owner_snapshot_or_boolean_version_cannot_adopt_the_prepared_scope(self):
        self.flow.prepare();original=self.flow.store.read()
        from overte_phone_script_history import pack,unpack
        for mutate in (lambda state:state['fileOwner'].update(runId='f'*32),
                       lambda state:state['fileOwner'].update(contractVersion=True),
                       lambda state:state.update(directory='file:///foreign/feature-script-'+('f'*32))):
            value=deepcopy(original);state=unpack(value['payload'])[0];mutate(state);value['payload']=pack([state])
            self.flow.store.write(value,self.flow.store.read());before=list(self.f.native.inputs)
            with self.assertRaises((ValueError,RuntimeError)):self.flow.load()
            self.assertEqual(before,self.f.native.inputs)
        self.flow.store.write(original,self.flow.store.read())

    def test_preparation_deadline_includes_the_reserved_private_owner_write(self):
        clock=[0.0];self.flow.monotonic=lambda:clock[0];original=self.flow.store.write
        def late(value,previous):original(value,previous);clock[0]=31
        with patch.object(self.flow.store,'write',side_effect=late):
            with self.assertRaises(NativeUIError):self.flow.prepare()
        self.assertEqual([],self.f.native.inputs)
        self.assertFalse(self.f.script_measurement_storage.root.exists())
        self.assertIsNotNone(self.flow.store.read())

    def test_whole_input_deadline_includes_persisting_issued_intent(self):
        self.flow.prepare();clock=[0.0];self.flow.monotonic=lambda:clock[0]
        original=self.flow.store.write
        def late(value,previous):original(value,previous);clock[0]=31
        with patch.object(self.flow.store,'write',side_effect=late):
            with self.assertRaises(NativeUIError):self.act('open')
        self.assertEqual([],self.f.native.inputs);self.assertEqual('issued',self.flow.load()['phase'])


if __name__=='__main__':unittest.main()
